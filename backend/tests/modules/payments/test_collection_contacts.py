"""A record of chasing a patient for money.

The receivables queue works without it right up to the moment two people
work it on the same morning and the patient is called twice before lunch.
These pin what the queue then shows, and the line the log must not cross:
**a contact is a note about an attempt and never moves money**.
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
from app.modules.payments.models import PatientEarnedEntry

BASE = "/api/v1/payments"


@pytest.fixture
async def ctx(db_session: AsyncSession, auth_headers: dict, client: AsyncClient) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = UUID(me.json()["data"]["user"]["id"])
    clinic = Clinic(
        id=uuid4(),
        name="Contacts Clinic",
        tax_id="A28003333",
        timezone="Europe/Madrid",
        currency="EUR",
        settings={},
        account_tier="clinic",
    )
    db_session.add(clinic)
    await db_session.flush()
    db_session.add(ClinicMembership(id=uuid4(), clinic_id=clinic.id, user_id=user_id, role="admin"))
    patient = Patient(id=uuid4(), clinic_id=clinic.id, first_name="Ana", last_name="Moro")
    db_session.add(patient)
    await db_session.flush()
    db_session.add(
        PatientEarnedEntry(
            id=uuid4(),
            clinic_id=clinic.id,
            patient_id=patient.id,
            treatment_id=uuid4(),
            amount=Decimal("120.00"),
            performed_at=datetime.now(UTC) - timedelta(days=45),
            source_event="test",
        )
    )
    await db_session.commit()
    return {"clinic_id": clinic.id, "patient_id": patient.id, "user_id": user_id}


async def _log(client: AsyncClient, headers: dict, patient_id, **body):
    return await client.post(
        f"{BASE}/receivables/{patient_id}/contacts",
        headers=headers,
        json={"channel": "call", **body},
    )


async def _row(client: AsyncClient, headers: dict) -> dict:
    response = await client.get(f"{BASE}/receivables", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"][0]


@pytest.mark.asyncio
async def test_a_patient_nobody_has_chased_says_so(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    row = await _row(client, auth_headers)
    assert row["last_contact_at"] is None
    assert row["last_contact_channel"] is None


@pytest.mark.asyncio
async def test_logging_a_contact_shows_up_on_the_queue(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    logged = await _log(
        client, auth_headers, ctx["patient_id"], channel="whatsapp", note="Le escribo"
    )
    assert logged.status_code == 201, logged.text

    row = await _row(client, auth_headers)
    assert row["last_contact_channel"] == "whatsapp"
    assert row["last_contact_at"] is not None


@pytest.mark.asyncio
async def test_the_row_carries_the_most_recent_attempt(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Chasing twice is normal; the row answers "when did we last try"."""
    await _log(client, auth_headers, ctx["patient_id"], channel="call")
    await _log(client, auth_headers, ctx["patient_id"], channel="in_person")

    row = await _row(client, auth_headers)
    assert row["last_contact_channel"] == "in_person"


@pytest.mark.asyncio
async def test_a_contact_never_moves_money(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """The line the log must not cross.

    An attempt to collect is not a collection. If the call worked there is
    a payment to show for it, and keeping the two apart is what lets the
    row say "called yesterday, still owes 120".
    """
    before = await _row(client, auth_headers)
    await _log(client, auth_headers, ctx["patient_id"], channel="call", note="No contesta")
    after = await _row(client, auth_headers)

    assert Decimal(after["receivable"]) == Decimal(before["receivable"]) == Decimal("120.00")
    assert after["age_days"] == before["age_days"]
    assert after["last_payment_at"] == before["last_payment_at"]


@pytest.mark.asyncio
async def test_the_history_reads_newest_first(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    await _log(client, auth_headers, ctx["patient_id"], channel="call", note="Primera")
    await _log(client, auth_headers, ctx["patient_id"], channel="email", note="Segunda")

    response = await client.get(
        f"{BASE}/receivables/{ctx['patient_id']}/contacts", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    notes = [c["note"] for c in response.json()["data"]]
    assert notes == ["Segunda", "Primera"]


@pytest.mark.asyncio
async def test_another_clinics_patient_is_not_found(
    client: AsyncClient, auth_headers: dict, ctx: dict, db_session: AsyncSession
) -> None:
    """Scoped like every other patient-addressed route (ADR 0029)."""
    stranger = Patient(id=uuid4(), clinic_id=uuid4(), first_name="Aje", last_name="No")
    refused = await _log(client, auth_headers, stranger.id, channel="call")
    assert refused.status_code == 404, refused.text
