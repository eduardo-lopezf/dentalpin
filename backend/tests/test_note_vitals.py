"""Vital signs on an evolution note."""

import pytest
from httpx import AsyncClient

from app.modules.patients.models import Patient

NOTES = "/api/v1/clinical_notes/notes"


def _note(patient: Patient, **extra) -> dict:
    return {
        "note_type": "diagnosis",
        "owner_type": "patient",
        "owner_id": str(patient.id),
        "body": "Paciente estable, se inicia tratamiento.",
        **extra,
    }


@pytest.mark.asyncio
async def test_a_clinical_note_carries_the_readings_taken_and_only_those(
    client: AsyncClient, auth_headers: dict, test_patient: Patient
) -> None:
    made = await client.post(
        NOTES,
        headers=auth_headers,
        json=_note(test_patient, vitals={"systolic": 128, "diastolic": 82, "heart_rate": 72}),
    )
    assert made.status_code == 201, made.text
    vitals = made.json()["data"]["vitals"]
    assert (vitals["systolic"], vitals["diastolic"], vitals["heart_rate"]) == (128, 82, 72)
    # What was not measured is absent, not zero.
    assert vitals["temperature_c"] is None

    record = await client.get(f"/api/v1/record/patients/{test_patient.id}", headers=auth_headers)
    sections = {(s["module"], s["name"]): s for s in record.json()["data"]["sections"]}
    [entry] = sections[("clinical_notes", "notes")]["entries"]
    assert entry["detail"]["systolic"] == 128 and "temperature_c" not in entry["detail"]

    # Rewording the note leaves the readings as they were taken.
    amended = await client.patch(
        f"{NOTES}/{made.json()['data']['id']}", headers=auth_headers, json={"body": "Corregida."}
    )
    assert amended.status_code == 200, amended.text
    assert amended.json()["data"]["vitals"]["systolic"] == 128


@pytest.mark.asyncio
async def test_a_note_without_readings_has_none(
    client: AsyncClient, auth_headers: dict, test_patient: Patient
) -> None:
    plain = await client.post(NOTES, headers=auth_headers, json=_note(test_patient))
    assert plain.json()["data"]["vitals"] is None
    empty = await client.post(NOTES, headers=auth_headers, json=_note(test_patient, vitals={}))
    assert empty.json()["data"]["vitals"] is None


@pytest.mark.asyncio
async def test_an_administrative_note_is_not_a_clinical_act(
    client: AsyncClient, auth_headers: dict, test_patient: Patient
) -> None:
    made = await client.post(
        NOTES,
        headers=auth_headers,
        json=_note(test_patient, note_type="administrative", vitals={"systolic": 120}),
    )
    assert made.status_code == 201, made.text
    assert made.json()["data"]["vitals"] is None


@pytest.mark.asyncio
async def test_an_impossible_reading_is_refused(
    client: AsyncClient, auth_headers: dict, test_patient: Patient
) -> None:
    refused = await client.post(
        NOTES, headers=auth_headers, json=_note(test_patient, vitals={"temperature_c": 98.6})
    )
    assert refused.status_code == 422, refused.text
