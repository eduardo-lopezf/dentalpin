"""Correcting a note is an amendment, not an overwrite.

Step 2 of the clinical-record work: [ADR 0032](../../docs/adr/0032-clinical-record-is-append-only.md)
and `docs/features/expediente-clinico.md` §8, phase 0.

`NoteService.update` assigned `note.body = body`. The prior text was gone, so
an amendment and an original were the same thing and "what did the note say on
the day of the procedure" — the question a complaint or an insurance review
turns on — had no answer.

The ADR names the test it wants: *"amend a note, then assert the pre-amendment
body is still retrievable and still attributed to its original professional."*
Attribution here is the account, because attribution by licensed professional
is still blocked (see the feature doc).
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership


async def _seed_patient(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict[str, str]
) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]

    clinic = Clinic(
        id=uuid4(),
        name="Amendment Clinic",
        tax_id="B44444444",
        address={"street": "x", "city": "y"},
        settings={},
        account_tier="clinic",
    )
    db_session.add(clinic)
    await db_session.flush()
    db_session.add(
        ClinicMembership(id=uuid4(), user_id=user_id, clinic_id=clinic.id, role="dentist")
    )
    await db_session.commit()

    patient = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "Ana", "last_name": "García", "phone": "+34699111222"},
    )
    return {"patient_id": patient.json()["data"]["id"], "user_id": user_id}


async def _create_note(
    client: AsyncClient, auth_headers: dict[str, str], patient_id: str, body: str
) -> dict:
    created = await client.post(
        "/api/v1/clinical_notes/notes",
        headers=auth_headers,
        json={
            "note_type": "administrative",
            "owner_type": "patient",
            "owner_id": patient_id,
            "body": body,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["data"]


@pytest.mark.asyncio
async def test_amending_a_note_keeps_what_it_said_before(
    client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
):
    """The round trip ADR 0032 asks for by name."""
    seed = await _seed_patient(db_session, client, auth_headers)
    note = await _create_note(client, auth_headers, seed["patient_id"], "Refiere dolor en el 26.")
    assert note["version"] == 1
    assert note["amended_at"] is None

    amended = await client.patch(
        f"/api/v1/clinical_notes/notes/{note['id']}",
        headers=auth_headers,
        json={"body": "Refiere dolor en el 36.", "reason": "Pieza equivocada"},
    )
    assert amended.status_code == 200
    current = amended.json()["data"]
    assert current["body"] == "Refiere dolor en el 36."
    assert current["version"] == 2
    assert current["amended_at"] is not None
    assert current["author_id"] == seed["user_id"], "amending does not change who wrote it"

    history = await client.get(
        f"/api/v1/clinical_notes/notes/{note['id']}/versions", headers=auth_headers
    )
    assert history.status_code == 200
    versions = history.json()["data"]
    assert len(versions) == 1
    assert versions[0]["body"] == "Refiere dolor en el 26.", "the text before is still there"
    assert versions[0]["version"] == 1
    assert versions[0]["amendment_reason"] == "Pieza equivocada"
    assert versions[0]["superseded_by_user_id"] == seed["user_id"]


@pytest.mark.asyncio
async def test_saving_without_changing_the_text_is_not_an_amendment(
    client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
):
    """Otherwise opening a note and pressing save manufactures history.

    A record full of identical versions says nothing, and worse, it makes the
    real amendments harder to find.
    """
    seed = await _seed_patient(db_session, client, auth_headers)
    note = await _create_note(client, auth_headers, seed["patient_id"], "Sin cambios.")

    unchanged = await client.patch(
        f"/api/v1/clinical_notes/notes/{note['id']}",
        headers=auth_headers,
        json={"body": "Sin cambios."},
    )
    assert unchanged.status_code == 200
    assert unchanged.json()["data"]["version"] == 1
    assert unchanged.json()["data"]["amended_at"] is None

    history = await client.get(
        f"/api/v1/clinical_notes/notes/{note['id']}/versions", headers=auth_headers
    )
    assert history.json()["data"] == []


@pytest.mark.asyncio
async def test_every_amendment_is_kept_in_order(
    client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
):
    """Reconstructing the note at a past instant is walking these in order."""
    seed = await _seed_patient(db_session, client, auth_headers)
    note = await _create_note(client, auth_headers, seed["patient_id"], "Primera.")

    for text in ("Segunda.", "Tercera."):
        response = await client.patch(
            f"/api/v1/clinical_notes/notes/{note['id']}",
            headers=auth_headers,
            json={"body": text},
        )
        assert response.status_code == 200

    history = await client.get(
        f"/api/v1/clinical_notes/notes/{note['id']}/versions", headers=auth_headers
    )
    versions = history.json()["data"]
    assert [v["version"] for v in versions] == [1, 2]
    assert [v["body"] for v in versions] == ["Primera.", "Segunda."]

    listed = await client.get(
        "/api/v1/clinical_notes/notes",
        headers=auth_headers,
        params={"owner_type": "patient", "owner_id": seed["patient_id"]},
    )
    current = next(n for n in listed.json()["data"] if n["id"] == note["id"])
    assert current["body"] == "Tercera."
    assert current["version"] == 3

    # The current text is not duplicated into the history: the note holds it,
    # which is why reading a note still costs no join.
    assert all(v["body"] != "Tercera." for v in versions)


@pytest.mark.asyncio
async def test_a_reason_is_optional(
    client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
):
    """Demanding one would fill the record with the word "correction"."""
    seed = await _seed_patient(db_session, client, auth_headers)
    note = await _create_note(client, auth_headers, seed["patient_id"], "Original.")

    amended = await client.patch(
        f"/api/v1/clinical_notes/notes/{note['id']}",
        headers=auth_headers,
        json={"body": "Corregida."},
    )
    assert amended.status_code == 200

    history = await client.get(
        f"/api/v1/clinical_notes/notes/{note['id']}/versions", headers=auth_headers
    )
    assert history.json()["data"][0]["amendment_reason"] is None


@pytest.mark.asyncio
async def test_a_deleted_note_keeps_its_versions(
    client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
):
    """Deleting a note is already soft, and the history has to follow it.

    A record that loses what a note said the moment someone removes it is the
    hole this work exists to close, one indirection further along.
    """
    seed = await _seed_patient(db_session, client, auth_headers)
    note = await _create_note(client, auth_headers, seed["patient_id"], "Antes.")
    await client.patch(
        f"/api/v1/clinical_notes/notes/{note['id']}",
        headers=auth_headers,
        json={"body": "Después."},
    )

    removed = await client.delete(
        f"/api/v1/clinical_notes/notes/{note['id']}", headers=auth_headers
    )
    assert removed.status_code == 204

    history = await client.get(
        f"/api/v1/clinical_notes/notes/{note['id']}/versions", headers=auth_headers
    )
    assert [v["body"] for v in history.json()["data"]] == ["Antes."]
