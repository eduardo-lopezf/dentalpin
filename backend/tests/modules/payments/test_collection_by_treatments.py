"""Per-treatment / per-session collection state, FIFO.

Powers the money view of a treatment plan: which sessions are charged, which
are still owed, and how much each phase can be billed for today. The rule
under test is that a payment covers the patient's **oldest** charges first,
whatever plan they came from.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.patients.models import Patient
from app.modules.payments.models import PatientEarnedEntry, Payment, PaymentAllocation

BASE = "/api/v1/payments"


@pytest.fixture
async def ctx(db_session: AsyncSession, auth_headers: dict, client: AsyncClient) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = UUID(me.json()["data"]["user"]["id"])
    clinic = Clinic(
        id=uuid4(),
        name="Collections Clinic",
        tax_id="A28001111",
        timezone="Europe/Madrid",
        currency="EUR",
        settings={},
        account_tier="clinic",
    )
    db_session.add(clinic)
    await db_session.flush()
    db_session.add(ClinicMembership(id=uuid4(), clinic_id=clinic.id, user_id=user_id, role="admin"))
    patient = Patient(id=uuid4(), clinic_id=clinic.id, first_name="Eva", last_name="Cobro")
    db_session.add(patient)
    await db_session.commit()
    return {
        "clinic_id": clinic.id,
        "patient_id": patient.id,
        "user_id": user_id,
        "treatment_id": uuid4(),
        "other_treatment_id": uuid4(),
    }


async def _earn(
    db: AsyncSession, ctx: dict, treatment_id: UUID, amount: str, minutes: int, session_id=None
) -> None:
    db.add(
        PatientEarnedEntry(
            id=uuid4(),
            clinic_id=ctx["clinic_id"],
            patient_id=ctx["patient_id"],
            treatment_id=treatment_id,
            source_session_id=session_id,
            amount=Decimal(amount),
            performed_at=datetime.now(UTC) + timedelta(minutes=minutes),
            source_event="test",
        )
    )
    await db.commit()


async def _pay(db: AsyncSession, ctx: dict, amount: str) -> None:
    payment = Payment(
        id=uuid4(),
        clinic_id=ctx["clinic_id"],
        patient_id=ctx["patient_id"],
        amount=Decimal(amount),
        currency="EUR",
        method="cash",
        payment_date=datetime.now(UTC).date(),
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


async def _summary(client: AsyncClient, auth_headers: dict, ctx: dict, ids: list[UUID]) -> dict:
    r = await client.post(
        f"{BASE}/summary/by-treatments",
        headers=auth_headers,
        json={"patient_id": str(ctx["patient_id"]), "treatment_ids": [str(i) for i in ids]},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.asyncio
async def test_payment_covers_the_oldest_sessions_first(client, auth_headers, ctx, db_session):
    """130 + 130 earned, 150 paid: the first session is settled, the second isn't."""
    first, second = uuid4(), uuid4()
    await _earn(db_session, ctx, ctx["treatment_id"], "130.00", 1, first)
    await _earn(db_session, ctx, ctx["treatment_id"], "130.00", 2, second)
    await _pay(db_session, ctx, "150.00")

    data = await _summary(client, auth_headers, ctx, [ctx["treatment_id"]])

    assert data["treatments"][str(ctx["treatment_id"])] == {
        "earned": "260.00",
        "collected": "150.00",
        "pending": "110.00",
    }
    assert data["sessions"][str(first)]["pending"] == "0.00"
    assert data["sessions"][str(second)]["collected"] == "20.00"
    assert data["sessions"][str(second)]["pending"] == "110.00"


@pytest.mark.asyncio
async def test_work_not_performed_is_absent(client, auth_headers, ctx, db_session):
    """Nothing is owed for work nobody has started; the id simply isn't there."""
    await _earn(db_session, ctx, ctx["treatment_id"], "100.00", 1, uuid4())

    data = await _summary(
        client, auth_headers, ctx, [ctx["treatment_id"], ctx["other_treatment_id"]]
    )
    assert str(ctx["other_treatment_id"]) not in data["treatments"]


@pytest.mark.asyncio
async def test_another_plan_consumes_the_same_money(client, auth_headers, ctx, db_session):
    """FIFO is per patient, not per plan.

    An older charge from a different plan eats the payment first. Reporting
    this plan in isolation would show money as collected that is not.
    """
    await _earn(db_session, ctx, ctx["other_treatment_id"], "100.00", 1, uuid4())
    await _earn(db_session, ctx, ctx["treatment_id"], "100.00", 2, uuid4())
    await _pay(db_session, ctx, "100.00")

    data = await _summary(client, auth_headers, ctx, [ctx["treatment_id"]])
    assert data["treatments"][str(ctx["treatment_id"])]["collected"] == "0"
    assert data["treatments"][str(ctx["treatment_id"])]["pending"] == "100.00"


@pytest.mark.asyncio
async def test_a_patient_from_another_clinic_is_refused(client, auth_headers, ctx):
    r = await client.post(
        f"{BASE}/summary/by-treatments",
        headers=auth_headers,
        json={"patient_id": str(uuid4()), "treatment_ids": [str(uuid4())]},
    )
    assert r.status_code == 404
