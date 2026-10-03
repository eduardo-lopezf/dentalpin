"""A clinical entry names the professional responsible for it.

The third defect of [ADR 0032](../../docs/adr/0032-clinical-record-is-append-only.md),
and the one that was blocked rather than merely pending: nothing linked an
account to a directory professional, so "who is clinically responsible for this
entry" had no source. `professionals.user_id` is that link — stated by an
admin, never inferred from a matching email, because clinical authorship in a
document meant to be evidence cannot rest on a coincidence.

What these pin: the link is validated, the attribution is resolved from it, and
an account without a profile leaves it empty instead of guessing.
"""

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.plugins.registry import module_registry
from app.modules.clinical_notes.models import ClinicalNote
from app.modules.patients_clinical.models import Allergy


async def _bootstrap(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict[str, str]
) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]

    clinic = Clinic(
        id=uuid4(),
        name="Attribution Clinic",
        tax_id="B55555555",
        address={"street": "x", "city": "y"},
        settings={},
        account_tier="clinic",
    )
    db_session.add(clinic)
    await db_session.flush()
    db_session.add(
        # admin: managing the directory needs `professionals.write`, which by
        # default only that role holds.
        ClinicMembership(id=uuid4(), user_id=user_id, clinic_id=clinic.id, role="admin")
    )
    await db_session.commit()

    patient = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "Ana", "last_name": "García", "phone": "+34699111222"},
    )
    return {
        "clinic_id": clinic.id,
        "user_id": user_id,
        "patient_id": patient.json()["data"]["id"],
    }


async def _link_professional(
    client: AsyncClient, auth_headers: dict[str, str], user_id: str | None
) -> str:
    created = await client.post(
        "/api/v1/professionals",
        headers=auth_headers,
        json={
            "first_name": "Marta",
            "last_name": "Ruiz",
            "professional_type": "dentist",
            "license_number": "COL-12345",
            "user_id": user_id,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["data"]["id"]


@pytest.mark.asyncio
async def test_an_allergy_records_the_professional_behind_the_account(
    client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
):
    """The common case: a dentist recording their own patient's history."""
    seed = await _bootstrap(db_session, client, auth_headers)
    professional_id = await _link_professional(client, auth_headers, seed["user_id"])

    created = await client.post(
        f"/api/v1/patients_clinical/patients/{seed['patient_id']}/allergies",
        headers=auth_headers,
        json={"name": "Penicilina", "severity": "critical"},
    )
    assert created.status_code == 201

    row = (
        await db_session.execute(
            select(Allergy).where(Allergy.patient_id == UUID(seed["patient_id"]))
        )
    ).scalar_one()
    assert row.recorded_by_user_id == UUID(seed["user_id"]), "who operated the software"
    assert row.recorded_by_professional_id == UUID(professional_id), "who answers for it"


@pytest.mark.asyncio
async def test_an_allergy_is_recorded_while_the_professionals_app_is_off(
    client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
):
    """The directory is an integration (ADR 0037): with it off the entry is
    still written, and names the account and no professional — even for an
    account that has a profile."""
    seed = await _bootstrap(db_session, client, auth_headers)
    await _link_professional(client, auth_headers, seed["user_id"])

    module_registry.deactivate("professionals")
    try:
        created = await client.post(
            f"/api/v1/patients_clinical/patients/{seed['patient_id']}/allergies",
            headers=auth_headers,
            json={"name": "Penicilina", "severity": "critical"},
        )
    finally:
        module_registry.activate("professionals")
    assert created.status_code == 201, created.text

    row = (
        await db_session.execute(
            select(Allergy).where(Allergy.patient_id == UUID(seed["patient_id"]))
        )
    ).scalar_one()
    assert row.recorded_by_user_id == UUID(seed["user_id"])
    assert row.recorded_by_professional_id is None


@pytest.mark.asyncio
async def test_a_note_is_written_while_the_professionals_app_is_off(
    client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
):
    """Same promise for notes: written, attributed to the account alone."""
    seed = await _bootstrap(db_session, client, auth_headers)
    await _link_professional(client, auth_headers, seed["user_id"])

    module_registry.deactivate("professionals")
    try:
        created = await client.post(
            "/api/v1/clinical_notes/notes",
            headers=auth_headers,
            json={
                "note_type": "administrative",
                "owner_type": "patient",
                "owner_id": seed["patient_id"],
                "body": "Refiere dolor.",
            },
        )
    finally:
        module_registry.activate("professionals")
    assert created.status_code == 201, created.text
    assert created.json()["data"]["author_id"] == seed["user_id"]
    assert created.json()["data"]["authored_by_professional_id"] is None


@pytest.mark.asyncio
async def test_a_note_records_both_the_account_and_the_professional(
    client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
):
    """`author_id` is the audit trail and stays as it was; the professional is new."""
    seed = await _bootstrap(db_session, client, auth_headers)
    professional_id = await _link_professional(client, auth_headers, seed["user_id"])

    created = await client.post(
        "/api/v1/clinical_notes/notes",
        headers=auth_headers,
        json={
            "note_type": "administrative",
            "owner_type": "patient",
            "owner_id": seed["patient_id"],
            "body": "Refiere dolor.",
        },
    )
    assert created.status_code == 201
    assert created.json()["data"]["authored_by_professional_id"] == professional_id

    note = (
        await db_session.execute(
            select(ClinicalNote).where(ClinicalNote.id == UUID(created.json()["data"]["id"]))
        )
    ).scalar_one()
    assert note.author_id == UUID(seed["user_id"])
    assert note.authored_by_professional_id == UUID(professional_id)


@pytest.mark.asyncio
async def test_an_amendment_names_who_corrected_it(
    client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
):
    """A correction is part of what the note says, so it is attributed too."""
    seed = await _bootstrap(db_session, client, auth_headers)
    professional_id = await _link_professional(client, auth_headers, seed["user_id"])

    created = await client.post(
        "/api/v1/clinical_notes/notes",
        headers=auth_headers,
        json={
            "note_type": "administrative",
            "owner_type": "patient",
            "owner_id": seed["patient_id"],
            "body": "Dolor en el 26.",
        },
    )
    note_id = created.json()["data"]["id"]
    await client.patch(
        f"/api/v1/clinical_notes/notes/{note_id}",
        headers=auth_headers,
        json={"body": "Dolor en el 36.", "reason": "Pieza equivocada"},
    )

    versions = await client.get(
        f"/api/v1/clinical_notes/notes/{note_id}/versions", headers=auth_headers
    )
    assert versions.json()["data"][0]["superseded_by_professional_id"] == professional_id


@pytest.mark.asyncio
async def test_an_account_with_no_profile_leaves_the_author_empty(
    client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
):
    """The case the ADR describes: an assistant typing what a dentist dictates.

    Nothing asks who is responsible yet, so the entry says the account and
    stays honest about the rest. A professional guessed from a matching email
    would be worse than a blank — it would name someone who never signed it.
    """
    seed = await _bootstrap(db_session, client, auth_headers)
    # A professional exists in the directory, with no account linked to it.
    await _link_professional(client, auth_headers, None)

    created = await client.post(
        f"/api/v1/patients_clinical/patients/{seed['patient_id']}/allergies",
        headers=auth_headers,
        json={"name": "Látex", "severity": "medium"},
    )
    assert created.status_code == 201

    row = (
        await db_session.execute(
            select(Allergy).where(Allergy.patient_id == UUID(seed["patient_id"]))
        )
    ).scalar_one()
    assert row.recorded_by_user_id == UUID(seed["user_id"])
    assert row.recorded_by_professional_id is None


@pytest.mark.asyncio
async def test_the_link_is_refused_for_an_account_outside_the_clinic(
    client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
):
    """Otherwise a clinic could name an outsider as the author of its records."""
    await _bootstrap(db_session, client, auth_headers)

    stranger = User(
        id=uuid4(),
        email="fuera@example.com",
        password_hash="x",
        first_name="Ajeno",
        last_name="Externo",
        is_active=True,
        token_version=0,
    )
    db_session.add(stranger)
    await db_session.commit()

    refused = await client.post(
        "/api/v1/professionals",
        headers=auth_headers,
        json={"first_name": "Otro", "last_name": "Perfil", "user_id": str(stranger.id)},
    )
    assert refused.status_code == 400


@pytest.mark.asyncio
async def test_one_account_is_one_professional_per_clinic(
    client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
):
    """Two profiles sharing an account makes "who is responsible" unanswerable."""
    seed = await _bootstrap(db_session, client, auth_headers)
    await _link_professional(client, auth_headers, seed["user_id"])

    clash = await client.post(
        "/api/v1/professionals",
        headers=auth_headers,
        json={
            "first_name": "Segundo",
            "last_name": "Perfil",
            "user_id": seed["user_id"],
        },
    )
    assert clash.status_code == 409
