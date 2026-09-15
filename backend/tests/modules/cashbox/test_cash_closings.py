"""The arqueo — the act the whole module exists for.

`payments` can already say what came in. Only a person can say what is
actually in the drawer, and the gap between the two is the one number here
no query could produce. These tests pin the arithmetic that produces it and
the rules that keep it honest once it is signed.

The expensive one is `test_a_refund_just_after_midnight_belongs_to_its_own
_clinic_day`: `payment_date` is a DATE and needs no conversion while
`refunded_at` is an instant that must be resolved through the clinic's
zone, and getting that wrong is invisible until a clinic west of Greenwich
is a few hundred pesos short every morning.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.utils.clinic_time import clinic_date
from app.modules.cashbox.models import CashClosing, CashMovement
from app.modules.patients.models import Patient
from app.modules.payments.models import Payment, PaymentAllocation, Refund

BASE = "/api/v1/cashbox"

# The clinic's own day, not the container's. The default clinic timezone is
# America/Mexico_City (UTC-6), so for six hours every evening `date.today()`
# in a UTC container is already tomorrow as far as the clinic is concerned —
# and a test built on it asks the API to count a day that has not happened.
# That is the service refusing correctly, not a bug to paper over.
TODAY = clinic_date(datetime.now(UTC), "America/Mexico_City")


@pytest.fixture
async def ctx(
    db_session: AsyncSession,
    auth_headers: dict,
    client: AsyncClient,
    test_clinic: Clinic,
) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = UUID(me.json()["data"]["user"]["id"])
    patient = Patient(id=uuid4(), clinic_id=test_clinic.id, first_name="Caja", last_name="Prueba")
    db_session.add(patient)
    await db_session.commit()
    return {
        "clinic_id": test_clinic.id,
        "user_id": user_id,
        "patient_id": patient.id,
        "currency": test_clinic.currency,
        "timezone": test_clinic.timezone,
    }


async def _pay(
    db: AsyncSession,
    ctx: dict,
    amount: str,
    *,
    method: str = "cash",
    day: date | None = None,
) -> Payment:
    payment = Payment(
        id=uuid4(),
        clinic_id=ctx["clinic_id"],
        patient_id=ctx["patient_id"],
        amount=Decimal(amount),
        currency=ctx["currency"],
        method=method,
        payment_date=day or TODAY,
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


async def _refund(
    db: AsyncSession,
    ctx: dict,
    payment: Payment,
    amount: str,
    *,
    method: str = "cash",
    at: datetime | None = None,
) -> None:
    db.add(
        Refund(
            id=uuid4(),
            clinic_id=ctx["clinic_id"],
            payment_id=payment.id,
            amount=Decimal(amount),
            method=method,
            reason_code="overpaid",
            refunded_at=at or datetime.now(UTC),
            refunded_by=ctx["user_id"],
        )
    )
    await db.commit()


async def _movement(client: AsyncClient, headers: dict, direction: str, amount: str) -> None:
    response = await client.post(
        f"{BASE}/movements",
        json={
            "business_date": TODAY.isoformat(),
            "direction": direction,
            "amount": amount,
            "category": "lab",
            "concept": "Mensajero",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text


async def _position(client: AsyncClient, headers: dict, day: date | None = None) -> dict:
    response = await client.get(
        f"{BASE}/position",
        params={"business_date": (day or TODAY).isoformat()},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def _close(client: AsyncClient, headers: dict, **overrides):
    body = {
        "business_date": TODAY.isoformat(),
        "counted_cash": "0",
        "opening_float": "0",
        "closing_float": "0",
    }
    body.update(overrides)
    return await client.post(f"{BASE}/closings", json=body, headers=headers)


# --- What the drawer should hold --------------------------------------


async def test_expected_cash_is_float_plus_cash_minus_refunds_and_movements(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    payment = await _pay(db_session, ctx, "1000.00")
    await _refund(db_session, ctx, payment, "100.00")
    await _movement(client, auth_headers, "in", "50.00")
    await _movement(client, auth_headers, "out", "200.00")

    position = await _position(client, auth_headers)

    assert Decimal(position["cash_collected"]) == Decimal("1000.00")
    assert Decimal(position["cash_refunded"]) == Decimal("100.00")
    assert Decimal(position["movements_in"]) == Decimal("50.00")
    assert Decimal(position["movements_out"]) == Decimal("200.00")
    # 0 float + 1000 − 100 + 50 − 200
    assert Decimal(position["expected_cash"]) == Decimal("750.00")


async def test_only_cash_is_counted(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """A card batch settles itself; a transfer is not till money at all.

    Both still show under `collected_by_method`, because the person closing
    wants to see the day — but neither is part of anything to count.
    """
    await _pay(db_session, ctx, "300.00", method="cash")
    await _pay(db_session, ctx, "900.00", method="card")
    await _pay(db_session, ctx, "500.00", method="bank_transfer")

    position = await _position(client, auth_headers)

    assert Decimal(position["cash_collected"]) == Decimal("300.00")
    assert Decimal(position["expected_cash"]) == Decimal("300.00")
    methods = {m["method"]: Decimal(m["amount"]) for m in position["collected_by_method"]}
    assert methods == {
        "cash": Decimal("300.00"),
        "card": Decimal("900.00"),
        "bank_transfer": Decimal("500.00"),
    }


async def test_a_card_payment_refunded_in_cash_still_empties_the_drawer(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """A refund's method can differ from its payment's, and only its own says."""
    await _pay(db_session, ctx, "400.00", method="cash")
    card = await _pay(db_session, ctx, "900.00", method="card")
    await _refund(db_session, ctx, card, "150.00", method="cash")

    position = await _position(client, auth_headers)

    assert Decimal(position["cash_collected"]) == Decimal("400.00")
    assert Decimal(position["cash_refunded"]) == Decimal("150.00")
    assert Decimal(position["expected_cash"]) == Decimal("250.00")


async def test_a_cash_payment_refunded_by_transfer_does_not_touch_the_drawer(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    cash = await _pay(db_session, ctx, "400.00", method="cash")
    await _refund(db_session, ctx, cash, "150.00", method="bank_transfer")

    position = await _position(client, auth_headers)

    assert Decimal(position["cash_refunded"]) == Decimal("0")
    assert Decimal(position["expected_cash"]) == Decimal("400.00")


async def test_an_evening_refund_belongs_to_the_clinics_day_not_utcs(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """The asymmetry that makes `clinic_time` exist.

    The clinic is on America/Mexico_City (UTC-6). A refund handed back at
    20:00 on the 14th, local, is 02:00 on the **15th** in UTC — so a window
    built from UTC midnights files it on the wrong day, and the drawer comes
    up short by whatever was handed back after six in the evening.

    `payment_date` needs none of this: it is already a DATE in the clinic's
    calendar. Only the instants do.
    """
    payment = await _pay(db_session, ctx, "1000.00", day=date(2026, 9, 14))
    # 20:00 on the 14th in Mexico City.
    that_evening = datetime(2026, 9, 15, 2, 0, tzinfo=UTC)
    await _refund(db_session, ctx, payment, "100.00", at=that_evening)

    on_the_14th = await _position(client, auth_headers, day=date(2026, 9, 14))
    on_the_15th = await _position(client, auth_headers, day=date(2026, 9, 15))

    assert Decimal(on_the_14th["cash_refunded"]) == Decimal("100.00")
    assert Decimal(on_the_15th["cash_refunded"]) == Decimal("0")


# --- Counting ---------------------------------------------------------


async def test_a_matching_count_closes_the_day(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    await _pay(db_session, ctx, "1000.00")

    response = await _close(
        client,
        auth_headers,
        opening_float="500.00",
        counted_cash="1500.00",
        closing_float="500.00",
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]

    assert Decimal(data["expected_cash"]) == Decimal("1500.00")
    assert Decimal(data["difference"]) == Decimal("0")
    assert data["status"] == "closed"
    assert data["closer"]["id"] == str(ctx["user_id"])
    # The breakdown is frozen with it: a period view reads this, never a
    # fresh query over rows that may have changed since.
    assert data["snapshot"]["cash_collected"] == "1000.00"


async def test_a_short_count_must_say_what_happened(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """A difference nobody explained is a number nobody can act on."""
    await _pay(db_session, ctx, "1000.00")

    refused = await _close(client, auth_headers, counted_cash="950.00")
    assert refused.status_code == 422
    assert "what happened" in refused.json()["message"]

    accepted = await _close(
        client,
        auth_headers,
        counted_cash="950.00",
        notes="Faltan 50: se pagó un taxi y no se apuntó.",
    )
    assert accepted.status_code == 201, accepted.text
    assert Decimal(accepted.json()["data"]["difference"]) == Decimal("-50.00")


async def test_a_blank_note_does_not_count_as_an_explanation(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    await _pay(db_session, ctx, "1000.00")
    refused = await _close(client, auth_headers, counted_cash="950.00", notes="   ")
    assert refused.status_code == 422


async def test_a_surplus_is_a_difference_too(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Money over is as much a sign of a problem as money short."""
    await _pay(db_session, ctx, "1000.00")
    response = await _close(
        client, auth_headers, counted_cash="1080.00", notes="Sobran 80, sin explicar."
    )
    assert response.status_code == 201
    assert Decimal(response.json()["data"]["difference"]) == Decimal("80.00")


async def test_a_day_cannot_be_counted_twice(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    assert (await _close(client, auth_headers)).status_code == 201
    second = await _close(client, auth_headers)
    assert second.status_code == 422
    assert "already counted" in second.json()["message"]


async def test_a_future_day_cannot_be_counted(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    response = await _close(
        client, auth_headers, business_date=(TODAY + timedelta(days=1)).isoformat()
    )
    assert response.status_code == 422


async def test_more_cannot_be_left_for_tomorrow_than_was_counted(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    response = await _close(client, auth_headers, counted_cash="100.00", closing_float="500.00")
    assert response.status_code == 422


async def test_closing_freezes_the_movements_it_counted(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """The rule phase 1 pinned against a hand-stamped id, now for real."""
    await _movement(client, auth_headers, "out", "200.00")
    listed = await client.get(
        f"{BASE}/movements",
        params={"date_from": TODAY.isoformat(), "date_to": TODAY.isoformat()},
        headers=auth_headers,
    )
    movement_id = listed.json()["data"][0]["id"]

    closed = await _close(
        client, auth_headers, counted_cash="0", notes="Solo salió el pago del mensajero."
    )
    assert closed.status_code == 201, closed.text

    edit = await client.put(
        f"{BASE}/movements/{movement_id}", json={"amount": "1.00"}, headers=auth_headers
    )
    assert edit.status_code == 422
    assert "closed day" in edit.json()["message"]


async def test_the_opening_float_chains_from_the_last_count(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Yesterday's closing float is today's opening, without anyone retyping it.

    Looked up as "the most recent count before this day", not literally
    yesterday: clinics close on Sundays, and a Monday whose float reset to
    zero would report the whole drawer as missing.
    """
    friday = TODAY - timedelta(days=3)
    # 1.200 collected in cash against a zero float: the count matches, so
    # the day closes clean and 800 of it stays in the drawer.
    await _pay(db_session, ctx, "1200.00", day=friday)
    response = await client.post(
        f"{BASE}/closings",
        json={
            "business_date": friday.isoformat(),
            "counted_cash": "1200.00",
            "opening_float": "0",
            "closing_float": "800.00",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    assert Decimal(response.json()["data"]["difference"]) == Decimal("0")

    position = await _position(client, auth_headers)
    assert Decimal(position["opening_float"]) == Decimal("800.00")


# --- Reopening --------------------------------------------------------


async def test_reopening_supersedes_the_count_and_releases_its_movements(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    await _movement(client, auth_headers, "out", "200.00")
    closed = await _close(
        client, auth_headers, counted_cash="0", notes="Solo la salida del mensajero."
    )
    closing_id = closed.json()["data"]["id"]

    reopened = await client.post(
        f"{BASE}/closings/{closing_id}/reopen",
        json={"reason": "El conteo se hizo antes de vaciar el cajón."},
        headers=auth_headers,
    )
    assert reopened.status_code == 200, reopened.text
    data = reopened.json()["data"]
    assert data["status"] == "reopened"
    assert data["reopener"]["id"] == str(ctx["user_id"])
    assert data["reopen_reason"].startswith("El conteo")

    # The movements are editable again...
    listed = await client.get(
        f"{BASE}/movements",
        params={"date_from": TODAY.isoformat(), "date_to": TODAY.isoformat()},
        headers=auth_headers,
    )
    movement_id = listed.json()["data"][0]["id"]
    assert listed.json()["data"][0]["closing_id"] is None
    edit = await client.put(
        f"{BASE}/movements/{movement_id}", json={"amount": "250.00"}, headers=auth_headers
    )
    assert edit.status_code == 200

    # ...and the day takes a fresh count, which the partial unique index
    # allows precisely because the old row is no longer `closed`.
    again = await _close(client, auth_headers, counted_cash="0", notes="Recontado.")
    assert again.status_code == 201, again.text


async def test_a_superseded_count_survives_as_history(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """20 short on a Tuesday is noise; 500 short every Friday is a signal.

    Deleting the superseded row would erase exactly the evidence that
    answers the question an owner actually has.
    """
    # Nothing came in and the float was zero, so 70 in the drawer is a
    # surplus of 70 — money over is as much a sign as money short.
    first = await _close(client, auth_headers, counted_cash="70.00", notes="Sobran 70.")
    closing_id = first.json()["data"]["id"]
    await client.post(
        f"{BASE}/closings/{closing_id}/reopen",
        json={"reason": "Mal contado."},
        headers=auth_headers,
    )
    await _close(client, auth_headers, counted_cash="0")

    standing = await client.get(f"{BASE}/closings", headers=auth_headers)
    assert len(standing.json()["data"]) == 1

    everything = await client.get(
        f"{BASE}/closings", params={"include_superseded": "true"}, headers=auth_headers
    )
    rows = everything.json()["data"]
    assert len(rows) == 2
    assert {r["status"] for r in rows} == {"closed", "reopened"}
    superseded = next(r for r in rows if r["status"] == "reopened")
    assert Decimal(superseded["difference"]) == Decimal("70.00")


async def test_reopening_twice_is_refused(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    closed = await _close(client, auth_headers)
    closing_id = closed.json()["data"]["id"]
    body = {"reason": "Motivo."}
    assert (
        await client.post(f"{BASE}/closings/{closing_id}/reopen", json=body, headers=auth_headers)
    ).status_code == 200
    second = await client.post(
        f"{BASE}/closings/{closing_id}/reopen", json=body, headers=auth_headers
    )
    assert second.status_code == 422


async def test_reopening_states_a_reason(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    closed = await _close(client, auth_headers)
    closing_id = closed.json()["data"]["id"]
    for reason in ("", "   "):
        response = await client.post(
            f"{BASE}/closings/{closing_id}/reopen",
            json={"reason": reason},
            headers=auth_headers,
        )
        assert response.status_code == 422


# --- Immutability and tenancy -----------------------------------------


async def test_a_payment_back_dated_into_a_closed_day_does_not_move_its_numbers(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """The whole point of a signed count is that it stops moving.

    Reception writes Friday's cash on Monday; Friday was already counted.
    The stored figures stay as they were counted, and the snapshot with
    them. Surfacing the late payment is phase 4's job, not this one's.
    """
    await _pay(db_session, ctx, "1000.00")
    closed = await _close(client, auth_headers, counted_cash="1000.00")
    closing_id = closed.json()["data"]["id"]

    await _pay(db_session, ctx, "400.00")

    reread = await client.get(f"{BASE}/closings/{closing_id}", headers=auth_headers)
    data = reread.json()["data"]
    assert Decimal(data["expected_cash"]) == Decimal("1000.00")
    assert Decimal(data["difference"]) == Decimal("0")
    assert data["snapshot"]["cash_collected"] == "1000.00"


async def test_another_clinics_closing_is_not_found(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    other = Clinic(
        id=uuid4(),
        name="Otra Clínica",
        tax_id="B88888888",
        settings={},
        account_tier="clinic",
    )
    db_session.add(other)
    await db_session.flush()
    stranger = CashClosing(
        id=uuid4(),
        clinic_id=other.id,
        business_date=TODAY,
        status="closed",
        currency="MXN",
        opening_float=Decimal("0"),
        expected_cash=Decimal("0"),
        counted_cash=Decimal("0"),
        difference=Decimal("0"),
        closing_float=Decimal("0"),
        snapshot={},
        closed_at=datetime.now(UTC),
        closed_by=ctx["user_id"],
    )
    db_session.add(stranger)
    await db_session.commit()

    assert (
        await client.get(f"{BASE}/closings/{stranger.id}", headers=auth_headers)
    ).status_code == 404
    listed = await client.get(f"{BASE}/closings", headers=auth_headers)
    assert all(row["id"] != str(stranger.id) for row in listed.json()["data"])


async def test_the_movements_of_another_day_are_not_frozen(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Closing Monday must not stamp Tuesday's rows."""
    tomorrow_ish = TODAY - timedelta(days=1)
    await client.post(
        f"{BASE}/movements",
        json={
            "business_date": tomorrow_ish.isoformat(),
            "direction": "out",
            "amount": "10.00",
            "category": "other",
            "concept": "Otro día",
        },
        headers=auth_headers,
    )
    await _movement(client, auth_headers, "out", "200.00")
    assert (
        await _close(client, auth_headers, counted_cash="0", notes="Salida del mensajero.")
    ).status_code == 201

    other_day = await db_session.execute(
        select(CashMovement).where(CashMovement.business_date == tomorrow_ish)
    )
    assert other_day.scalar_one().closing_id is None
