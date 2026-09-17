"""A reopened session takes its charge with it.

``treatment_plan.item_session_reopened`` is the reverse of
``item_session_completed``. The handler drops the row that completion
booked — and any whole-treatment row, since the treatment is planned again —
and leaves every other session's charge alone.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.patients.models import Patient
from app.modules.payments.events import (
    on_session_completed,
    on_session_reopened,
    on_treatment_performed,
)
from tests.modules.payments.test_earned_no_double_booking import _payload, _total


@pytest.fixture
async def ctx(db_session: AsyncSession, auth_headers: dict, client: AsyncClient) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    clinic = Clinic(
        id=uuid4(),
        name="Reopen Clinic",
        tax_id="A28000998",
        timezone="America/Mexico_City",
        currency="MXN",
        settings={},
        account_tier="clinic",
    )
    db_session.add(clinic)
    await db_session.flush()
    db_session.add(
        ClinicMembership(
            id=uuid4(),
            clinic_id=clinic.id,
            user_id=me.json()["data"]["user"]["id"],
            role="admin",
        )
    )
    patient = Patient(id=uuid4(), clinic_id=clinic.id, first_name="Ana", last_name="Reabre")
    db_session.add(patient)
    await db_session.commit()
    return {
        "clinic_id": str(clinic.id),
        "patient_id": str(patient.id),
        "treatment_id": str(uuid4()),
    }


@pytest.mark.asyncio
async def test_reopening_drops_that_session_only(db_session, ctx):
    first, last = str(uuid4()), str(uuid4())
    await on_session_completed(_payload(ctx, session_id=first, amount="200.00"))
    await on_session_completed(_payload(ctx, session_id=last, amount="600.00"))

    await on_session_reopened(_payload(ctx, session_id=last))

    assert await _total(db_session, ctx) == Decimal("200.00")


@pytest.mark.asyncio
async def test_reopening_drops_a_whole_treatment_row(db_session, ctx):
    """Work booked without sessions is undone by the same event."""
    await on_treatment_performed(_payload(ctx, price_snapshot="60.00"))

    await on_session_reopened(_payload(ctx, session_id=str(uuid4())))

    assert await _total(db_session, ctx) == Decimal("0")


@pytest.mark.asyncio
async def test_replaying_the_reopen_changes_nothing(db_session, ctx):
    session_id = str(uuid4())
    await on_session_completed(_payload(ctx, session_id=session_id, amount="130.00"))

    await on_session_reopened(_payload(ctx, session_id=session_id))
    await on_session_reopened(_payload(ctx, session_id=session_id))

    assert await _total(db_session, ctx) == Decimal("0")


@pytest.mark.asyncio
async def test_reopen_in_another_clinic_touches_nothing(db_session, ctx):
    session_id = str(uuid4())
    await on_session_completed(_payload(ctx, session_id=session_id, amount="130.00"))

    await on_session_reopened({**_payload(ctx, session_id=session_id), "clinic_id": str(uuid4())})

    assert await _total(db_session, ctx) == Decimal("130.00")
