"""The list a clinic works through: who owes money, oldest debt first.

The aging report could say "seven patients owe 12.400 at 90+" and gave no
way to learn which seven, so it was a report and never a worklist. This is
the same money, per patient, with the age measured from the entry the
payments did not reach.

That last part is the whole point, and it is what
`test_a_long_standing_patient_is_aged_by_the_debt_not_by_their_history`
pins: the report used to bucket a patient by their **oldest entry**, so a
patient of three years who owed last week's filling was filed under 90+
next to genuine bad debt. A queue that is wrong about the clinic's most
loyal patients is a queue nobody opens twice.
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
        name="Receivables Clinic",
        tax_id="A28002222",
        timezone="Europe/Madrid",
        currency="EUR",
        settings={},
        account_tier="clinic",
    )
    db_session.add(clinic)
    await db_session.flush()
    db_session.add(ClinicMembership(id=uuid4(), clinic_id=clinic.id, user_id=user_id, role="admin"))
    await db_session.commit()
    return {"clinic_id": clinic.id, "user_id": user_id}


async def _patient(db: AsyncSession, ctx: dict, name: str) -> UUID:
    patient = Patient(id=uuid4(), clinic_id=ctx["clinic_id"], first_name=name, last_name="Deudor")
    db.add(patient)
    await db.commit()
    return patient.id


async def _earn(db: AsyncSession, ctx: dict, patient_id: UUID, amount: str, days_ago: int) -> None:
    db.add(
        PatientEarnedEntry(
            id=uuid4(),
            clinic_id=ctx["clinic_id"],
            patient_id=patient_id,
            treatment_id=uuid4(),
            amount=Decimal(amount),
            performed_at=datetime.now(UTC) - timedelta(days=days_ago),
            source_event="test",
        )
    )
    await db.commit()


async def _pay(
    db: AsyncSession, ctx: dict, patient_id: UUID, amount: str, days_ago: int = 0
) -> None:
    payment = Payment(
        id=uuid4(),
        clinic_id=ctx["clinic_id"],
        patient_id=patient_id,
        amount=Decimal(amount),
        currency="EUR",
        method="cash",
        payment_date=(datetime.now(UTC) - timedelta(days=days_ago)).date(),
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


async def _list(client: AsyncClient, headers: dict, **params) -> dict:
    response = await client.get(f"{BASE}/receivables", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_a_patient_who_owes_nothing_is_not_on_the_list(
    client: AsyncClient, auth_headers: dict, ctx: dict, db_session: AsyncSession
) -> None:
    settled = await _patient(db_session, ctx, "Saldada")
    await _earn(db_session, ctx, settled, "200.00", days_ago=40)
    await _pay(db_session, ctx, settled, "200.00")

    listed = await _list(client, auth_headers)
    assert [r["patient"]["id"] for r in listed["data"]] == []


@pytest.mark.asyncio
async def test_a_long_standing_patient_is_aged_by_the_debt_not_by_their_history(
    client: AsyncClient, auth_headers: dict, ctx: dict, db_session: AsyncSession
) -> None:
    """The bug this list exists to avoid.

    Two years of settled work and one unpaid filling from last week. Aging
    on the oldest *entry* files them under 90+; aging on the oldest entry
    the money did not reach says 0-30, which is the truth.
    """
    loyal = await _patient(db_session, ctx, "Fiel")
    await _earn(db_session, ctx, loyal, "500.00", days_ago=730)
    await _earn(db_session, ctx, loyal, "300.00", days_ago=365)
    await _pay(db_session, ctx, loyal, "800.00", days_ago=360)
    await _earn(db_session, ctx, loyal, "60.00", days_ago=7)

    row = (await _list(client, auth_headers))["data"][0]
    assert row["patient"]["id"] == str(loyal)
    assert Decimal(row["receivable"]) == Decimal("60.00")
    assert row["age_days"] == 7
    assert row["bucket"] == "0-30"


@pytest.mark.asyncio
async def test_the_oldest_debt_comes_first(
    client: AsyncClient, auth_headers: dict, ctx: dict, db_session: AsyncSession
) -> None:
    """The order somebody would work in: the money most at risk on top."""
    recent = await _patient(db_session, ctx, "Reciente")
    await _earn(db_session, ctx, recent, "100.00", days_ago=5)
    old = await _patient(db_session, ctx, "Antigua")
    await _earn(db_session, ctx, old, "50.00", days_ago=200)

    listed = await _list(client, auth_headers)
    assert [r["patient"]["first_name"] for r in listed["data"]] == ["Antigua", "Reciente"]
    assert listed["data"][0]["bucket"] == "90+"


@pytest.mark.asyncio
async def test_the_bucket_filter_narrows_the_queue(
    client: AsyncClient, auth_headers: dict, ctx: dict, db_session: AsyncSession
) -> None:
    recent = await _patient(db_session, ctx, "Reciente")
    await _earn(db_session, ctx, recent, "100.00", days_ago=5)
    old = await _patient(db_session, ctx, "Antigua")
    await _earn(db_session, ctx, old, "50.00", days_ago=200)

    listed = await _list(client, auth_headers, bucket="90+")
    assert [r["patient"]["first_name"] for r in listed["data"]] == ["Antigua"]
    assert listed["total"] == 1


@pytest.mark.asyncio
async def test_a_part_payment_leaves_only_what_is_left(
    client: AsyncClient, auth_headers: dict, ctx: dict, db_session: AsyncSession
) -> None:
    """FIFO: the payment settles the older entry and part of the newer one."""
    patient = await _patient(db_session, ctx, "Parcial")
    await _earn(db_session, ctx, patient, "100.00", days_ago=60)
    await _earn(db_session, ctx, patient, "100.00", days_ago=10)
    await _pay(db_session, ctx, patient, "150.00", days_ago=2)

    row = (await _list(client, auth_headers))["data"][0]
    assert Decimal(row["receivable"]) == Decimal("50.00")
    # The 60-day entry is covered, so the debt is the 10-day one.
    assert row["bucket"] == "0-30"
    assert row["last_payment_at"] is not None


@pytest.mark.asyncio
async def test_the_report_and_the_queue_never_disagree(
    client: AsyncClient, auth_headers: dict, ctx: dict, db_session: AsyncSession
) -> None:
    """Both read the same rows, so a dashboard and a list cannot diverge."""
    for name, days in (("Uno", 5), ("Dos", 45), ("Tres", 200)):
        patient = await _patient(db_session, ctx, name)
        await _earn(db_session, ctx, patient, "100.00", days_ago=days)

    listed = await _list(client, auth_headers, page_size=100)
    report = await client.get(f"{BASE}/reports/aging-receivables", headers=auth_headers)
    assert report.status_code == 200, report.text
    buckets = report.json()["data"]["buckets"]

    assert sum(Decimal(r["receivable"]) for r in listed["data"]) == sum(
        Decimal(b["total"]) for b in buckets
    )
    assert listed["total"] == sum(b["patient_count"] for b in buckets)
