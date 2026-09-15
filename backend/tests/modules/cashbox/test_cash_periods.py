"""The weekly, fortnightly and monthly cut.

Two things are worth pinning here and they are unrelated to each other.

The first is the **calendar**, which is pure arithmetic and where this gets
quietly wrong: a Mexican quincena is the 1st-15th and the 16th-to-the-end,
not every fourteen days, and a rolling fortnight drifts off the month by
March. Those tests need no database at all.

The second is that the cut is assembled **from the arqueos** and not
recalculated from `payments`. A fortnight recomputed from payments looks
immaculate with three uncounted days inside it; one built from closings says
which three are missing. `pending_days` is that sentence, and it is the only
reason the phase is worth shipping.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.utils.clinic_time import clinic_date
from app.modules.cashbox.service import period_bounds
from app.modules.patients.models import Patient
from app.modules.payments.models import Payment, PaymentAllocation, Refund

BASE = "/api/v1/cashbox"
TZ = "America/Mexico_City"
TODAY = clinic_date(datetime.now(UTC), TZ)


# --- The calendar, with no database in sight --------------------------


class TestPeriodBounds:
    def test_a_week_runs_monday_to_sunday(self) -> None:
        """Matching `payments`' own `trends`, so the app has one week."""
        # 2026-09-16 is a Wednesday.
        assert period_bounds("week", date(2026, 9, 16)) == (
            date(2026, 9, 14),
            date(2026, 9, 20),
        )

    def test_a_week_anchored_on_its_own_monday_or_sunday_is_the_same_week(self) -> None:
        expected = (date(2026, 9, 14), date(2026, 9, 20))
        assert period_bounds("week", date(2026, 9, 14)) == expected
        assert period_bounds("week", date(2026, 9, 20)) == expected

    def test_a_week_can_straddle_two_months(self) -> None:
        # 2026-10-01 is a Thursday; its Monday is 28 September.
        assert period_bounds("week", date(2026, 10, 1)) == (
            date(2026, 9, 28),
            date(2026, 10, 4),
        )

    def test_the_first_fortnight_is_the_1st_to_the_15th(self) -> None:
        for day in (1, 7, 15):
            assert period_bounds("fortnight", date(2026, 9, day)) == (
                date(2026, 9, 1),
                date(2026, 9, 15),
            )

    def test_the_second_fortnight_runs_to_the_end_of_its_month(self) -> None:
        """Not fourteen days — the second quincena is as long as the month.

        Payroll is paid on the 15th and the last day, so a rolling fortnight
        would stop lining up with the only thing this report is for.
        """
        assert period_bounds("fortnight", date(2026, 9, 16)) == (
            date(2026, 9, 16),
            date(2026, 9, 30),
        )
        assert period_bounds("fortnight", date(2026, 1, 31)) == (
            date(2026, 1, 16),
            date(2026, 1, 31),
        )

    def test_february_keeps_its_own_length(self) -> None:
        assert period_bounds("fortnight", date(2026, 2, 20)) == (
            date(2026, 2, 16),
            date(2026, 2, 28),
        )
        # 2028 is a leap year.
        assert period_bounds("fortnight", date(2028, 2, 20)) == (
            date(2028, 2, 16),
            date(2028, 2, 29),
        )
        assert period_bounds("month", date(2028, 2, 5)) == (
            date(2028, 2, 1),
            date(2028, 2, 29),
        )

    def test_a_month_is_the_first_to_the_last(self) -> None:
        assert period_bounds("month", date(2026, 9, 16)) == (
            date(2026, 9, 1),
            date(2026, 9, 30),
        )
        assert period_bounds("month", date(2026, 12, 31)) == (
            date(2026, 12, 1),
            date(2026, 12, 31),
        )

    def test_an_unknown_kind_is_refused_rather_than_guessed(self) -> None:
        with pytest.raises(ValueError, match="Unknown period kind"):
            period_bounds("quarter", date(2026, 9, 16))


# --- The cut itself ---------------------------------------------------


@pytest.fixture
async def ctx(
    db_session: AsyncSession,
    auth_headers: dict,
    client: AsyncClient,
    test_clinic: Clinic,
) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    patient = Patient(id=uuid4(), clinic_id=test_clinic.id, first_name="Corte", last_name="Prueba")
    db_session.add(patient)
    await db_session.commit()
    return {
        "clinic_id": test_clinic.id,
        "user_id": UUID(me.json()["data"]["user"]["id"]),
        "patient_id": patient.id,
        "currency": test_clinic.currency,
    }


async def _pay(db: AsyncSession, ctx: dict, amount: str, day: date, *, method: str = "cash"):
    payment = Payment(
        id=uuid4(),
        clinic_id=ctx["clinic_id"],
        patient_id=ctx["patient_id"],
        amount=Decimal(amount),
        currency=ctx["currency"],
        method=method,
        payment_date=day,
        recorded_by=ctx["user_id"],
    )
    db.add(payment)
    await db.flush()
    db.add(
        PaymentAllocation(
            id=uuid4(),
            clinic_id=ctx["clinic_id"],
            payment_id=payment.id,
            target_type="on_account",
            amount=Decimal(amount),
            created_by=ctx["user_id"],
        )
    )
    await db.commit()
    return payment


async def _close(client: AsyncClient, headers: dict, day: date, counted: str, **overrides):
    body = {
        "business_date": day.isoformat(),
        "counted_cash": counted,
        "opening_float": "0",
        "closing_float": "0",
    }
    body.update(overrides)
    return await client.post(f"{BASE}/closings", json=body, headers=headers)


async def _period(client: AsyncClient, headers: dict, kind: str, day: date) -> dict:
    response = await client.get(
        f"{BASE}/periods",
        params={"kind": kind, "day": day.isoformat()},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_the_cut_sums_the_counted_days(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    a, b = TODAY - timedelta(days=2), TODAY - timedelta(days=1)
    await _pay(db_session, ctx, "300.00", a)
    await _pay(db_session, ctx, "500.00", b)
    assert (await _close(client, auth_headers, a, "300.00")).status_code == 201
    assert (await _close(client, auth_headers, b, "500.00")).status_code == 201

    period = await _period(client, auth_headers, "month", TODAY)

    assert period["counted_days"] == 2
    assert Decimal(period["cash_collected"]) == Decimal("800.00")
    assert Decimal(period["difference_total"]) == Decimal("0")
    assert period["days_off"] == 0
    assert len(period["closings"]) == 2


async def test_a_day_that_moved_money_and_was_not_counted_is_named(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """The sentence the whole phase exists for.

    Recomputed from `payments` this period would read as 800 collected and
    look immaculate. Built from the arqueos it reads 300 and says which day
    is missing.
    """
    counted_day, uncounted = TODAY - timedelta(days=2), TODAY - timedelta(days=1)
    await _pay(db_session, ctx, "300.00", counted_day)
    await _pay(db_session, ctx, "500.00", uncounted)
    await _close(client, auth_headers, counted_day, "300.00")

    period = await _period(client, auth_headers, "month", TODAY)

    assert period["counted_days"] == 1
    assert Decimal(period["cash_collected"]) == Decimal("300.00")
    assert uncounted.isoformat() in period["pending_days"]
    assert counted_day.isoformat() not in period["pending_days"]


async def test_a_quiet_day_is_not_a_pending_day(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """A clinic that shuts on Sunday is not four days behind every month.

    Only days where something actually moved in the drawer can be pending.
    Warn about every calendar day and the warning is wrong every time, which
    is the same as not having one.
    """
    quiet = TODAY - timedelta(days=3)
    busy = TODAY - timedelta(days=2)
    await _pay(db_session, ctx, "100.00", busy)

    period = await _period(client, auth_headers, "month", TODAY)

    assert busy.isoformat() in period["pending_days"]
    assert quiet.isoformat() not in period["pending_days"]


async def test_a_card_only_day_does_not_go_pending(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Nothing entered the drawer, so there is nothing to count."""
    card_day = TODAY - timedelta(days=2)
    await _pay(db_session, ctx, "900.00", card_day, method="card")

    period = await _period(client, auth_headers, "month", TODAY)
    assert card_day.isoformat() not in period["pending_days"]


async def test_a_movement_alone_makes_a_day_pending(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Money left the drawer even though nobody paid anything in."""
    day = TODAY - timedelta(days=2)
    await client.post(
        f"{BASE}/movements",
        json={
            "business_date": day.isoformat(),
            "direction": "out",
            "amount": "80.00",
            "category": "supplies",
            "concept": "Guantes",
        },
        headers=auth_headers,
    )

    period = await _period(client, auth_headers, "month", TODAY)
    assert day.isoformat() in period["pending_days"]


async def test_differences_net_but_the_days_that_were_off_are_counted(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """50 short one day and 50 over the next is a period that balances.

    Saying so is honest; letting it read as "nothing happened" is not, and
    `days_off` is what stops it.
    """
    a, b = TODAY - timedelta(days=2), TODAY - timedelta(days=1)
    await _pay(db_session, ctx, "300.00", a)
    await _pay(db_session, ctx, "300.00", b)
    await _close(client, auth_headers, a, "250.00", notes="Faltan 50.")
    await _close(client, auth_headers, b, "350.00", notes="Sobran 50.")

    period = await _period(client, auth_headers, "month", TODAY)

    assert Decimal(period["difference_total"]) == Decimal("0")
    assert period["days_off"] == 2


async def test_the_cut_reads_the_frozen_snapshot_not_the_live_rows(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """A payment back-dated into a counted day does not move the period.

    Reception writes Friday's cash on Monday; Friday was counted. The
    period keeps reading the day as it was counted, and the late payment is
    phase 4's business.
    """
    day = TODAY - timedelta(days=2)
    await _pay(db_session, ctx, "300.00", day)
    await _close(client, auth_headers, day, "300.00")

    await _pay(db_session, ctx, "400.00", day)

    period = await _period(client, auth_headers, "month", TODAY)
    assert Decimal(period["cash_collected"]) == Decimal("300.00")


async def test_every_channel_shows_but_only_cash_is_counted(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    day = TODAY - timedelta(days=2)
    await _pay(db_session, ctx, "300.00", day, method="cash")
    await _pay(db_session, ctx, "900.00", day, method="card")
    await _close(client, auth_headers, day, "300.00")

    period = await _period(client, auth_headers, "month", TODAY)

    assert Decimal(period["cash_collected"]) == Decimal("300.00")
    methods = {m["method"]: Decimal(m["amount"]) for m in period["collected_by_method"]}
    assert methods == {"cash": Decimal("300.00"), "card": Decimal("900.00")}


async def test_a_reopened_count_leaves_its_day_pending_again(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Reopening puts the day back among the ones still to do."""
    day = TODAY - timedelta(days=2)
    await _pay(db_session, ctx, "300.00", day)
    closed = await _close(client, auth_headers, day, "300.00")
    closing_id = closed.json()["data"]["id"]

    before = await _period(client, auth_headers, "month", TODAY)
    assert before["counted_days"] == 1

    await client.post(
        f"{BASE}/closings/{closing_id}/reopen",
        json={"reason": "Mal contado."},
        headers=auth_headers,
    )

    after = await _period(client, auth_headers, "month", TODAY)
    assert after["counted_days"] == 0
    assert Decimal(after["cash_collected"]) == Decimal("0")
    assert day.isoformat() in after["pending_days"]


async def test_an_empty_period_is_zero_rather_than_an_error(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    period = await _period(client, auth_headers, "month", TODAY - timedelta(days=400))
    assert period["counted_days"] == 0
    assert period["pending_days"] == []
    assert Decimal(period["cash_collected"]) == Decimal("0")


async def test_the_endpoint_takes_any_day_of_the_period(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """The caller should not have to know where a quincena starts."""
    mid = await _period(client, auth_headers, "fortnight", date(2026, 9, 20))
    edge = await _period(client, auth_headers, "fortnight", date(2026, 9, 30))
    assert mid["date_from"] == edge["date_from"] == "2026-09-16"
    assert mid["date_to"] == edge["date_to"] == "2026-09-30"


async def test_a_refund_is_placed_on_the_clinics_day(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """The same asymmetry the arqueo lives with, now deciding a pending day.

    20:00 on the 14th in Mexico City is 02:00 on the 15th in UTC. Read off
    the timestamp, the clinic would be told to count a day it had already
    closed and left alone one it had not.
    """
    db_session.add(
        Refund(
            id=uuid4(),
            clinic_id=ctx["clinic_id"],
            payment_id=(await _pay(db_session, ctx, "500.00", date(2026, 9, 14))).id,
            amount=Decimal("100.00"),
            method="cash",
            reason_code="overpaid",
            refunded_at=datetime(2026, 9, 15, 2, 0, tzinfo=UTC),
            refunded_by=ctx["user_id"],
        )
    )
    await db_session.commit()

    period = await _period(client, auth_headers, "fortnight", date(2026, 9, 14))
    assert "2026-09-14" in period["pending_days"]
    assert "2026-09-15" not in period["pending_days"]
