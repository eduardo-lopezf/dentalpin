"""The two earned paths must never book the same treatment twice.

Completing a plan item fires both events: the last session publishes
``treatment_plan.item_session_completed``, then the item finalizes, performs
the Treatment and publishes ``odontogram.treatment.performed``. The unique
constraint does not stop them landing together — NULL and a session id are
different keys — so every treatment completed through a plan was booked
twice, at double the money. An endodontics of 380,00 showed up as 760,00.

These tests exercise the handlers directly, which is where the rule lives.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.patients.models import Patient
from app.modules.payments.events import on_session_completed, on_treatment_performed
from app.modules.payments.models import PatientEarnedEntry


@pytest.fixture
async def ctx(db_session: AsyncSession, auth_headers: dict, client: AsyncClient) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    clinic = Clinic(
        id=uuid4(),
        name="Double Booking Clinic",
        tax_id="A28000999",
        timezone="Europe/Madrid",
        currency="EUR",
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
    patient = Patient(id=uuid4(), clinic_id=clinic.id, first_name="Eva", last_name="Doble")
    db_session.add(patient)
    await db_session.commit()
    return {
        "clinic_id": str(clinic.id),
        "patient_id": str(patient.id),
        "treatment_id": str(uuid4()),
    }


def _payload(ctx: dict, **extra) -> dict:
    return {
        "clinic_id": ctx["clinic_id"],
        "patient_id": ctx["patient_id"],
        "treatment_id": ctx["treatment_id"],
        "occurred_at": datetime.now(UTC).isoformat(),
        **extra,
    }


async def _total(db: AsyncSession, ctx: dict) -> Decimal:
    rows = (
        (
            await db.execute(
                select(PatientEarnedEntry).where(
                    PatientEarnedEntry.treatment_id == ctx["treatment_id"]
                )
            )
        )
        .scalars()
        .all()
    )
    return sum((r.amount for r in rows), Decimal("0"))


@pytest.mark.asyncio
async def test_sessions_then_treatment_books_the_price_once(db_session, ctx):
    """The real order: sessions complete, then the item performs the treatment."""
    for label, amount in (
        ("Apertura", "130.00"),
        ("Conformación", "130.00"),
        ("Obturación", "120.00"),
    ):
        await on_session_completed(
            _payload(ctx, session_id=str(uuid4()), label=label, amount=amount)
        )

    await on_treatment_performed(_payload(ctx, price_snapshot="380.00"))

    assert await _total(db_session, ctx) == Decimal("380.00")


@pytest.mark.asyncio
async def test_treatment_then_sessions_supersedes_the_whole_row(db_session, ctx):
    """The other arrival order must land on the same total, not add to it."""
    await on_treatment_performed(_payload(ctx, price_snapshot="380.00"))
    assert await _total(db_session, ctx) == Decimal("380.00")

    for label, amount in (
        ("Apertura", "130.00"),
        ("Conformación", "130.00"),
        ("Obturación", "120.00"),
    ):
        await on_session_completed(
            _payload(ctx, session_id=str(uuid4()), label=label, amount=amount)
        )

    # The per-session breakdown is the truth; the whole-treatment row is gone.
    assert await _total(db_session, ctx) == Decimal("380.00")
    rows = (
        (
            await db_session.execute(
                select(PatientEarnedEntry).where(
                    PatientEarnedEntry.treatment_id == ctx["treatment_id"]
                )
            )
        )
        .scalars()
        .all()
    )
    assert all(r.source_session_id is not None for r in rows)


@pytest.mark.asyncio
async def test_treatment_without_sessions_still_books(db_session, ctx):
    """Work charted straight on the odontogram never had sessions."""
    await on_treatment_performed(_payload(ctx, price_snapshot="60.00"))
    assert await _total(db_session, ctx) == Decimal("60.00")


@pytest.mark.asyncio
async def test_replaying_either_event_changes_nothing(db_session, ctx):
    session_id = str(uuid4())
    await on_session_completed(_payload(ctx, session_id=session_id, amount="130.00"))
    await on_session_completed(_payload(ctx, session_id=session_id, amount="130.00"))
    await on_treatment_performed(_payload(ctx, price_snapshot="380.00"))
    await on_treatment_performed(_payload(ctx, price_snapshot="380.00"))

    assert await _total(db_session, ctx) == Decimal("130.00")
