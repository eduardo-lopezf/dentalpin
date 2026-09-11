"""A payment lands on the day the clinic took it, not the day before.

``payments.payment_date`` is a DATE: the clinic took the money on a day, not
at a moment. To sit on a timeline beside real instants it has to become one,
and the ledger used to build it at **UTC** midnight. West of Greenwich UTC
midnight is still the previous evening, so every payment in a Mexican or
Chilean clinic read one day early — a cobro on the 10th listed as the 9th.

The fix places it at midnight **in the clinic's own zone**. These tests pin
both directions of the boundary, because a zone-blind implementation passes
whichever single case you happen to write.
"""

from __future__ import annotations

from datetime import UTC, date
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.patients.models import Patient
from app.modules.payments.models import Payment, PaymentAllocation
from app.modules.payments.service import LedgerService

PAID_ON = date(2026, 9, 10)


async def _make_clinic(
    db: AsyncSession, client: AsyncClient, auth_headers: dict, timezone: str
) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = UUID(me.json()["data"]["user"]["id"])
    clinic = Clinic(
        id=uuid4(),
        name=f"Clinic {timezone}",
        tax_id="A28009999",
        timezone=timezone,
        currency="MXN",
        settings={},
        account_tier="clinic",
    )
    db.add(clinic)
    await db.flush()
    db.add(ClinicMembership(id=uuid4(), clinic_id=clinic.id, user_id=user_id, role="admin"))
    patient = Patient(id=uuid4(), clinic_id=clinic.id, first_name="Juan", last_name="Fecha")
    db.add(patient)
    await db.flush()

    payment = Payment(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        amount=Decimal("100.00"),
        currency="MXN",
        method="cash",
        payment_date=PAID_ON,
        recorded_by=user_id,
    )
    db.add(payment)
    await db.flush()
    db.add(
        PaymentAllocation(
            id=uuid4(),
            clinic_id=clinic.id,
            payment_id=payment.id,
            target_type="on_account",
            amount=Decimal("100.00"),
            created_by=user_id,
        )
    )
    await db.commit()
    return {"clinic_id": clinic.id, "patient_id": patient.id, "timezone": timezone}


async def _payment_entry(db: AsyncSession, ctx: dict):
    ledger = await LedgerService.get_patient_ledger(
        db, ctx["clinic_id"], ctx["patient_id"], "MXN", ctx["timezone"]
    )
    entries = [e for e in ledger.timeline if e.entry_type == "payment"]
    assert len(entries) == 1
    return entries[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("timezone", ["America/Mexico_City", "Europe/Madrid", "Pacific/Auckland"])
async def test_payment_reads_as_its_own_day_in_the_clinic_zone(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, timezone: str
) -> None:
    ctx = await _make_clinic(db_session, client, auth_headers, timezone)
    entry = await _payment_entry(db_session, ctx)

    # The only assertion that matters to a receptionist: reading the
    # timestamp back in the clinic's zone gives the day they took the money.
    assert entry.occurred_at.astimezone(ZoneInfo(timezone)).date() == PAID_ON


@pytest.mark.asyncio
async def test_west_of_greenwich_is_not_the_previous_day_in_utc(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict
) -> None:
    ctx = await _make_clinic(db_session, client, auth_headers, "America/Mexico_City")
    entry = await _payment_entry(db_session, ctx)

    # The regression itself: UTC midnight would be exactly 2026-09-10T00:00Z,
    # which is 9 Sept 18:00 in Mexico City. The instant must be later.
    assert entry.occurred_at.astimezone(UTC).date() == PAID_ON
    assert entry.occurred_at.astimezone(UTC).hour == 6


@pytest.mark.asyncio
async def test_unusable_timezone_falls_back_instead_of_failing(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict
) -> None:
    # A ledger that will not load is worse than one whose day boundary is
    # off, so a broken zone id degrades to UTC rather than raising.
    ctx = await _make_clinic(db_session, client, auth_headers, "America/Mexico_City")
    ctx["timezone"] = "Not/A_Zone"
    entry = await _payment_entry(db_session, ctx)
    assert entry.occurred_at.astimezone(UTC).date() == PAID_ON
    assert entry.occurred_at.astimezone(UTC).hour == 0
