"""Settling with an associate dentist.

The whole feature turns on two numbers being different: what the associate
**earned** (work performed, priced) and what has been **collected** for it.
On a large case those are months apart, and a clinic paying a percentage of
the first hands out money it has not received.

The expensive tests here are the attribution ones. A patient's payments
cover their oldest charges first, regardless of who did the work, so money
handed over for last year's fillings is not available to pay this month's
surgeon — and a walk restricted to one professional would credit it twice.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.liquidations.models import Liquidation
from app.modules.patients.models import Patient
from app.modules.payments.models import PatientEarnedEntry, Payment, PaymentAllocation
from app.modules.professionals.models import Professional

BASE = "/api/v1/liquidations"
TODAY = date(2026, 9, 10)
FROM, TO = date(2026, 9, 1), date(2026, 9, 15)


@pytest.fixture
async def ctx(
    db_session: AsyncSession,
    auth_headers: dict,
    client: AsyncClient,
    test_clinic: Clinic,
) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    patient = Patient(id=uuid4(), clinic_id=test_clinic.id, first_name="Liq", last_name="Prueba")
    ana = Professional(
        id=uuid4(),
        clinic_id=test_clinic.id,
        first_name="Ana",
        last_name="Asociada",
        professional_type="dentist",
    )
    beto = Professional(
        id=uuid4(),
        clinic_id=test_clinic.id,
        first_name="Beto",
        last_name="Asociado",
        professional_type="dentist",
    )
    db_session.add_all([patient, ana, beto])
    await db_session.commit()
    return {
        "clinic_id": test_clinic.id,
        "user_id": UUID(me.json()["data"]["user"]["id"]),
        "patient_id": patient.id,
        "ana": ana.id,
        "beto": beto.id,
        "currency": test_clinic.currency,
    }


async def _earn(
    db: AsyncSession,
    ctx: dict,
    professional_id: UUID,
    amount: str,
    *,
    at: datetime | None = None,
    description: str = "Trabajo",
    treatment_id: UUID | None = None,
) -> PatientEarnedEntry:
    entry = PatientEarnedEntry(
        id=uuid4(),
        clinic_id=ctx["clinic_id"],
        patient_id=ctx["patient_id"],
        treatment_id=treatment_id or uuid4(),
        description=description,
        amount=Decimal(amount),
        performed_at=at or datetime(2026, 9, 10, 12, 0, tzinfo=UTC),
        professional_id=professional_id,
        source_event="test",
    )
    db.add(entry)
    await db.commit()
    return entry


async def _pay(db: AsyncSession, ctx: dict, amount: str, day: date | None = None) -> None:
    payment = Payment(
        id=uuid4(),
        clinic_id=ctx["clinic_id"],
        patient_id=ctx["patient_id"],
        amount=Decimal(amount),
        currency=ctx["currency"],
        method="cash",
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


async def _commission(
    client: AsyncClient,
    headers: dict,
    professional_id: UUID,
    percent: str,
    basis: str = "collected",
):
    return await client.put(
        f"{BASE}/commissions/{professional_id}",
        json={"basis": basis, "percent": percent},
        headers=headers,
    )


async def _preview(client: AsyncClient, headers: dict, professional_id: UUID) -> dict:
    response = await client.get(
        f"{BASE}/preview",
        params={
            "professional_id": str(professional_id),
            "date_from": FROM.isoformat(),
            "date_to": TO.isoformat(),
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


# --- The two axes -----------------------------------------------------


async def test_earned_and_collected_are_different_numbers(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """The reason the feature exists.

    Ana did 10.000 of work and the patient has paid 4.000. Paying her a
    percentage of the 10.000 hands out money the clinic has not received.
    """
    await _earn(db_session, ctx, ctx["ana"], "10000.00")
    await _pay(db_session, ctx, "4000.00")
    await _commission(client, auth_headers, ctx["ana"], "40.00")

    preview = await _preview(client, auth_headers, ctx["ana"])

    assert Decimal(preview["earned_total"]) == Decimal("10000.00")
    assert Decimal(preview["collected_total"]) == Decimal("4000.00")
    assert preview["basis"] == "collected"
    assert Decimal(preview["base_amount"]) == Decimal("4000.00")
    assert Decimal(preview["amount_due"]) == Decimal("1600.00")


async def test_the_earned_basis_pays_on_work_done(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Offered because some clinics do it; never the default."""
    await _earn(db_session, ctx, ctx["ana"], "10000.00")
    await _pay(db_session, ctx, "4000.00")
    await _commission(client, auth_headers, ctx["ana"], "40.00", basis="earned")

    preview = await _preview(client, auth_headers, ctx["ana"])

    assert Decimal(preview["base_amount"]) == Decimal("10000.00")
    assert Decimal(preview["amount_due"]) == Decimal("4000.00")


async def test_without_an_agreed_percentage_it_says_so_instead_of_guessing(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    await _earn(db_session, ctx, ctx["ana"], "10000.00")

    preview = await _preview(client, auth_headers, ctx["ana"])

    assert preview["missing_commission"] is True
    assert Decimal(preview["percent"]) == Decimal("0")
    assert Decimal(preview["amount_due"]) == Decimal("0")
    # The work is still reported: the figures are real, only the share is not.
    assert Decimal(preview["earned_total"]) == Decimal("10000.00")


# --- Attribution ------------------------------------------------------


async def test_a_patients_money_covers_their_oldest_work_first(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Beto worked first, so the patient's 5.000 is his before it is Ana's.

    This is the rule the whole attribution rests on, and it is `payments`'
    rule rather than one invented here: a payment has no foreign key to the
    work it pays for, and the order is the only thing that assigns it.
    """
    await _earn(db_session, ctx, ctx["beto"], "6000.00", at=datetime(2026, 9, 2, 10, 0, tzinfo=UTC))
    await _earn(db_session, ctx, ctx["ana"], "4000.00", at=datetime(2026, 9, 9, 10, 0, tzinfo=UTC))
    await _pay(db_session, ctx, "5000.00")
    await _commission(client, auth_headers, ctx["ana"], "50.00")
    await _commission(client, auth_headers, ctx["beto"], "50.00")

    beto = await _preview(client, auth_headers, ctx["beto"])
    ana = await _preview(client, auth_headers, ctx["ana"])

    assert Decimal(beto["collected_total"]) == Decimal("5000.00")
    assert Decimal(ana["collected_total"]) == Decimal("0")
    assert Decimal(ana["earned_total"]) == Decimal("4000.00")


async def test_money_already_consumed_by_older_work_is_not_available_again(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """A walk restricted to one professional would credit it twice.

    The patient owed 6.000 from before the period and paid 6.000. Ana's work
    inside the period is not covered by any of it — the money was already
    spent on the older charge.
    """
    await _earn(db_session, ctx, ctx["beto"], "6000.00", at=datetime(2026, 8, 1, 10, 0, tzinfo=UTC))
    await _earn(db_session, ctx, ctx["ana"], "4000.00", at=datetime(2026, 9, 9, 10, 0, tzinfo=UTC))
    await _pay(db_session, ctx, "6000.00")
    await _commission(client, auth_headers, ctx["ana"], "50.00")

    ana = await _preview(client, auth_headers, ctx["ana"])

    assert Decimal(ana["earned_total"]) == Decimal("4000.00")
    assert Decimal(ana["collected_total"]) == Decimal("0")
    assert Decimal(ana["amount_due"]) == Decimal("0")


async def test_a_partly_paid_treatment_is_partly_settled(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    await _earn(db_session, ctx, ctx["ana"], "10000.00")
    await _pay(db_session, ctx, "2500.00")
    await _commission(client, auth_headers, ctx["ana"], "40.00")

    preview = await _preview(client, auth_headers, ctx["ana"])
    line = preview["lines"][0]

    assert Decimal(line["earned"]) == Decimal("10000.00")
    assert Decimal(line["collected"]) == Decimal("2500.00")
    assert Decimal(preview["amount_due"]) == Decimal("1000.00")


async def test_sessions_of_one_treatment_fold_into_one_line(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """A multi-session treatment earns per session; the associate reads a job."""
    treatment = uuid4()
    for _ in range(3):
        await _earn(db_session, ctx, ctx["ana"], "1000.00", treatment_id=treatment)
    await _pay(db_session, ctx, "2000.00")
    await _commission(client, auth_headers, ctx["ana"], "50.00")

    preview = await _preview(client, auth_headers, ctx["ana"])

    assert len(preview["lines"]) == 1
    assert Decimal(preview["lines"][0]["earned"]) == Decimal("3000.00")
    assert Decimal(preview["lines"][0]["collected"]) == Decimal("2000.00")


async def test_work_outside_the_period_is_not_settled(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    await _earn(db_session, ctx, ctx["ana"], "5000.00", at=datetime(2026, 9, 20, 10, 0, tzinfo=UTC))
    await _commission(client, auth_headers, ctx["ana"], "50.00")

    preview = await _preview(client, auth_headers, ctx["ana"])
    assert Decimal(preview["earned_total"]) == Decimal("0")
    assert preview["lines"] == []


async def test_another_professionals_work_is_never_counted(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    await _earn(db_session, ctx, ctx["beto"], "9000.00")
    await _commission(client, auth_headers, ctx["ana"], "50.00")

    preview = await _preview(client, auth_headers, ctx["ana"])
    assert Decimal(preview["earned_total"]) == Decimal("0")


# --- The document -----------------------------------------------------


async def test_issuing_freezes_the_numbers(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """A patient paying tomorrow must not change what was already paid out."""
    await _earn(db_session, ctx, ctx["ana"], "10000.00")
    await _pay(db_session, ctx, "4000.00")
    await _commission(client, auth_headers, ctx["ana"], "40.00")

    issued = await client.post(
        BASE,
        json={
            "professional_id": str(ctx["ana"]),
            "date_from": FROM.isoformat(),
            "date_to": TO.isoformat(),
        },
        headers=auth_headers,
    )
    assert issued.status_code == 201, issued.text
    liquidation_id = issued.json()["data"]["id"]
    assert Decimal(issued.json()["data"]["amount_due"]) == Decimal("1600.00")

    # The patient pays the rest.
    await _pay(db_session, ctx, "6000.00")

    reread = await client.get(f"{BASE}/{liquidation_id}", headers=auth_headers)
    data = reread.json()["data"]
    assert Decimal(data["collected_total"]) == Decimal("4000.00")
    assert Decimal(data["amount_due"]) == Decimal("1600.00")
    assert Decimal(data["lines"][0]["collected"]) == Decimal("4000.00")


async def test_a_changed_percentage_does_not_reach_an_issued_settlement(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """The arrangement is mutable; the document that used it is not."""
    await _earn(db_session, ctx, ctx["ana"], "10000.00")
    await _pay(db_session, ctx, "10000.00")
    await _commission(client, auth_headers, ctx["ana"], "40.00")
    issued = await client.post(
        BASE,
        json={
            "professional_id": str(ctx["ana"]),
            "date_from": FROM.isoformat(),
            "date_to": TO.isoformat(),
        },
        headers=auth_headers,
    )
    liquidation_id = issued.json()["data"]["id"]

    await _commission(client, auth_headers, ctx["ana"], "50.00")

    reread = await client.get(f"{BASE}/{liquidation_id}", headers=auth_headers)
    assert Decimal(reread.json()["data"]["percent"]) == Decimal("40.00")
    assert Decimal(reread.json()["data"]["amount_due"]) == Decimal("4000.00")


async def test_a_period_cannot_be_settled_twice(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    await _earn(db_session, ctx, ctx["ana"], "1000.00")
    await _commission(client, auth_headers, ctx["ana"], "40.00")
    body = {
        "professional_id": str(ctx["ana"]),
        "date_from": FROM.isoformat(),
        "date_to": TO.isoformat(),
    }
    assert (await client.post(BASE, json=body, headers=auth_headers)).status_code == 201
    second = await client.post(BASE, json=body, headers=auth_headers)
    assert second.status_code == 422
    assert "already been settled" in second.json()["message"]


async def test_the_preview_says_the_period_is_already_settled(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    await _earn(db_session, ctx, ctx["ana"], "1000.00")
    await _commission(client, auth_headers, ctx["ana"], "40.00")
    issued = await client.post(
        BASE,
        json={
            "professional_id": str(ctx["ana"]),
            "date_from": FROM.isoformat(),
            "date_to": TO.isoformat(),
        },
        headers=auth_headers,
    )

    preview = await _preview(client, auth_headers, ctx["ana"])
    assert preview["issued_id"] == issued.json()["data"]["id"]


async def test_settling_without_an_agreed_percentage_is_refused(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Handing somebody a figure of zero is worse than saying it is missing."""
    await _earn(db_session, ctx, ctx["ana"], "1000.00")

    response = await client.post(
        BASE,
        json={
            "professional_id": str(ctx["ana"]),
            "date_from": FROM.isoformat(),
            "date_to": TO.isoformat(),
        },
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "no agreed percentage" in response.json()["message"]


async def test_the_document_names_no_patient(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """It goes to an associate and names the work, not the people.

    The module depends on `payments` and `professionals`, not on `patients`,
    and there is no reason a settlement should carry a patient's identity.
    """
    await _earn(db_session, ctx, ctx["ana"], "1000.00", description="Endodoncia molar")
    await _commission(client, auth_headers, ctx["ana"], "40.00")

    preview = await _preview(client, auth_headers, ctx["ana"])
    assert "patient_id" not in str(preview)
    assert "Liq" not in str(preview)
    assert preview["lines"][0]["description"] == "Endodoncia molar"


# --- Boundaries -------------------------------------------------------


async def test_a_percentage_outside_zero_to_a_hundred_is_refused(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    for percent in ("-1", "101"):
        response = await _commission(client, auth_headers, ctx["ana"], percent)
        assert response.status_code == 422


async def test_a_professional_of_another_clinic_is_refused(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    other = Clinic(id=uuid4(), name="Otra", tax_id="B66666666", settings={}, account_tier="clinic")
    db_session.add(other)
    await db_session.flush()
    stranger = Professional(
        id=uuid4(),
        clinic_id=other.id,
        first_name="Ajeno",
        last_name="Profesional",
        professional_type="dentist",
    )
    db_session.add(stranger)
    await db_session.commit()

    assert (await _commission(client, auth_headers, stranger.id, "40.00")).status_code == 422
    response = await client.get(
        f"{BASE}/preview",
        params={
            "professional_id": str(stranger.id),
            "date_from": FROM.isoformat(),
            "date_to": TO.isoformat(),
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_another_clinics_settlement_is_not_found(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    other = Clinic(id=uuid4(), name="Otra", tax_id="B55555555", settings={}, account_tier="clinic")
    db_session.add(other)
    await db_session.flush()
    stranger_pro = Professional(
        id=uuid4(),
        clinic_id=other.id,
        first_name="Ajeno",
        last_name="Profesional",
        professional_type="dentist",
    )
    db_session.add(stranger_pro)
    await db_session.flush()
    stranger = Liquidation(
        id=uuid4(),
        clinic_id=other.id,
        professional_id=stranger_pro.id,
        date_from=FROM,
        date_to=TO,
        currency="MXN",
        basis="collected",
        percent=Decimal("40.00"),
        earned_total=Decimal("0"),
        collected_total=Decimal("0"),
        base_amount=Decimal("0"),
        amount_due=Decimal("0"),
        lines=[],
        issued_at=datetime.now(UTC),
        issued_by=ctx["user_id"],
    )
    db_session.add(stranger)
    await db_session.commit()

    assert (await client.get(f"{BASE}/{stranger.id}", headers=auth_headers)).status_code == 404
    listed = await client.get(BASE, headers=auth_headers)
    assert all(row["id"] != str(stranger.id) for row in listed.json()["data"])


async def test_a_backwards_period_is_refused(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    response = await client.get(
        f"{BASE}/preview",
        params={
            "professional_id": str(ctx["ana"]),
            "date_from": TO.isoformat(),
            "date_to": (FROM - timedelta(days=1)).isoformat(),
        },
        headers=auth_headers,
    )
    assert response.status_code == 422
