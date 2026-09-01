"""Agenda appointments are assigned to directory profiles, never accounts."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password
from app.modules.agenda.models import Cabinet
from app.modules.professionals.models import Professional


@pytest.fixture
async def directory_clinic(
    db_session: AsyncSession, auth_headers: dict[str, str], client: AsyncClient
) -> dict[str, str]:
    actor_id = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()["data"]["user"][
        "id"
    ]
    clinic = Clinic(
        id=uuid4(),
        name="Directory Agenda Clinic",
        tax_id="B12345678",
        address={"street": "Test St", "city": "Madrid"},
        settings={"slot_duration_min": 15},
        account_tier="clinic",
    )
    dentist_account = User(
        id=uuid4(),
        email="account-dentist@example.com",
        password_hash=hash_password("TestPass123"),
        first_name="Account",
        last_name="Dentist",
        is_active=True,
    )
    dentist = Professional(
        id=uuid4(),
        clinic_id=clinic.id,
        first_name="Directory",
        last_name="Dentist",
        professional_type="dentist",
        email="directory-dentist@example.com",
        is_active=True,
    )
    collaborator = Professional(
        id=uuid4(),
        clinic_id=clinic.id,
        first_name="External",
        last_name="Lab",
        professional_type="collaborator",
        is_active=True,
    )
    db_session.add_all(
        [
            clinic,
            dentist_account,
            dentist,
            collaborator,
            ClinicMembership(user_id=actor_id, clinic_id=clinic.id, role="admin"),
            ClinicMembership(user_id=dentist_account.id, clinic_id=clinic.id, role="dentist"),
            Cabinet(
                clinic_id=clinic.id,
                name="Gabinete 1",
                color="#3B82F6",
                display_order=0,
                is_active=True,
            ),
        ]
    )
    await db_session.commit()
    return {
        "directory_dentist_id": str(dentist.id),
        "account_dentist_id": str(dentist_account.id),
        "collaborator_id": str(collaborator.id),
    }


async def _patient_id(client: AsyncClient, auth_headers: dict[str, str]) -> str:
    response = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "Test", "last_name": "Patient"},
    )
    return response.json()["data"]["id"]


@pytest.mark.asyncio
async def test_appointment_accepts_directory_dentist(
    client: AsyncClient, auth_headers: dict[str, str], directory_clinic: dict[str, str]
) -> None:
    response = await client.post(
        "/api/v1/agenda/appointments",
        headers=auth_headers,
        json={
            "patient_id": await _patient_id(client, auth_headers),
            "professional_id": directory_clinic["directory_dentist_id"],
            "cabinet": "Gabinete 1",
            "start_time": "2026-08-20T10:00:00Z",
            "end_time": "2026-08-20T10:30:00Z",
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["professional_id"] == directory_clinic["directory_dentist_id"]
    assert data["professional"]["first_name"] == "Directory"


@pytest.mark.asyncio
async def test_appointment_rejects_system_account_and_collaborator(
    client: AsyncClient, auth_headers: dict[str, str], directory_clinic: dict[str, str]
) -> None:
    patient_id = await _patient_id(client, auth_headers)
    for professional_id in (
        directory_clinic["account_dentist_id"],
        directory_clinic["collaborator_id"],
    ):
        response = await client.post(
            "/api/v1/agenda/appointments",
            headers=auth_headers,
            json={
                "patient_id": patient_id,
                "professional_id": professional_id,
                "cabinet": "Gabinete 1",
                "start_time": "2026-08-20T11:00:00Z",
                "end_time": "2026-08-20T11:30:00Z",
            },
        )
        assert response.status_code == 400
        assert "Invalid professional" in response.json()["message"]
