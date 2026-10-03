"""Agenda does its whole job under every combination of integrations (ADR 0037).

``agenda.depends`` is empty, so nothing it links to may be required for
booking, moving, progressing or cancelling an appointment. This drives
the HTTP surface end to end with each subset of its six integrations
switched off — 64 combinations — and reports every one that breaks.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from itertools import combinations
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.plugins.registry import module_registry
from app.modules.agenda import AgendaModule
from app.modules.agenda.models import Cabinet
from app.modules.patients.models import Patient
from app.modules.professionals.models import Professional

# Everything the agenda links to: the four modules its foreign keys point
# at, plus the two it reaches through contracts alone.
INTEGRATIONS = ["patients", "professionals", "catalog", "odontogram", "treatment_plan", "schedules"]
BASE = "/api/v1/agenda"
DAY = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)


def test_the_matrix_covers_every_integration_agenda_declares() -> None:
    assert AgendaModule.manifest["depends"] == []
    assert set(AgendaModule.manifest["integrates"]) <= set(INTEGRATIONS)


async def _run_flow(
    client: AsyncClient,
    headers: dict,
    off: tuple[str, ...],
    slot: int,
    world: dict,
) -> None:
    """Book, read, move, seat, treat, complete and cancel — over HTTP."""
    start = DAY + timedelta(days=slot // 16, minutes=30 * (slot % 16))
    body: dict = {
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(minutes=30)).isoformat(),
    }
    with_patient = "patients" not in off
    with_professional = "professionals" not in off
    if with_patient:
        body["patient_id"] = str(world["patient_id"])
    else:
        body["title"] = f"Sin paciente {slot}"
    if with_professional:
        body["professional_id"] = str(world["professional_id"])

    created = await client.post(f"{BASE}/appointments", json=body, headers=headers)
    assert created.status_code == 201, created.text
    appointment = created.json()["data"]
    appointment_id = appointment["id"]
    assert (appointment["patient_id"] is not None) == with_patient
    assert (appointment["professional_id"] is not None) == with_professional

    listed = await client.get(
        f"{BASE}/appointments",
        params={"start_date": start.isoformat(), "end_date": start.isoformat()},
        headers=headers,
    )
    assert listed.status_code == 200, listed.text
    assert appointment_id in [a["id"] for a in listed.json()["data"]]

    fetched = await client.get(f"{BASE}/appointments/{appointment_id}", headers=headers)
    assert fetched.status_code == 200, fetched.text

    moved = await client.put(
        f"{BASE}/appointments/{appointment_id}",
        json={"end_time": (start + timedelta(minutes=25)).isoformat()},
        headers=headers,
    )
    assert moved.status_code == 200, moved.text

    for to_status in ("confirmed", "checked_in"):
        step = await client.post(
            f"{BASE}/appointments/{appointment_id}/transitions",
            json={"to_status": to_status},
            headers=headers,
        )
        assert step.status_code == 200, f"{to_status}: {step.text}"

    seated = await client.patch(
        f"{BASE}/appointments/{appointment_id}/cabinet",
        json={"cabinet_id": str(world["cabinet_id"])},
        headers=headers,
    )
    assert seated.status_code == 200, seated.text

    for to_status in ("in_treatment", "completed"):
        step = await client.post(
            f"{BASE}/appointments/{appointment_id}/transitions",
            json={"to_status": to_status},
            headers=headers,
        )
        assert step.status_code == 200, f"{to_status}: {step.text}"

    kanban = await client.get(
        f"{BASE}/kanban/day", params={"date": start.date().isoformat()}, headers=headers
    )
    assert kanban.status_code == 200, kanban.text
    if not with_professional:
        assert kanban.json()["data"]["professionals"] == []

    # A second appointment, cancelled: the other way out of the flow.
    body["start_time"] = (start + timedelta(hours=10)).isoformat()
    body["end_time"] = (start + timedelta(hours=10, minutes=30)).isoformat()
    second = await client.post(f"{BASE}/appointments", json=body, headers=headers)
    assert second.status_code == 201, second.text
    cancelled = await client.delete(
        f"{BASE}/appointments/{second.json()['data']['id']}", headers=headers
    )
    assert cancelled.status_code == 204, cancelled.text


@pytest.mark.asyncio
async def test_agenda_works_under_every_combination_of_integrations(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    cabinet = Cabinet(id=uuid4(), clinic_id=test_clinic.id, name="Sillón matriz", color="#3B82F6")
    patient = Patient(id=uuid4(), clinic_id=test_clinic.id, first_name="Ana", last_name="Ruiz")
    professional = Professional(
        id=uuid4(),
        clinic_id=test_clinic.id,
        first_name="Dra",
        last_name="Soto",
        professional_type="dentist",
        is_active=True,
    )
    db_session.add_all([cabinet, patient, professional])
    await db_session.commit()
    world = {
        "cabinet_id": cabinet.id,
        "patient_id": patient.id,
        "professional_id": professional.id,
    }

    subsets = [
        subset
        for size in range(len(INTEGRATIONS) + 1)
        for subset in combinations(INTEGRATIONS, size)
    ]
    assert len(subsets) == 64

    broken: list[str] = []
    for slot, off in enumerate(subsets):
        was_active = [name for name in off if module_registry.is_installed(name)]
        for name in off:
            module_registry.deactivate(name)
        try:
            await _run_flow(client, auth_headers, off, slot, world)
        except AssertionError as exc:
            broken.append(f"off={list(off) or 'nothing'}: {str(exc)[:300]}")
        finally:
            for name in was_active:
                module_registry.activate(name)

    assert not broken, f"{len(broken)} of 64 combinations broke:\n" + "\n".join(broken)
