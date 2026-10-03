"""The medical history is corrected by appending, never by deleting.

Step 1 of the clinical-record work: [ADR 0032](../../docs/adr/0032-clinical-record-is-append-only.md)
and `docs/features/expediente-clinico.md` §8, phase 0.

What these pin is the property that turns stored data into a record — that
what the chart said on the day of the medical act stays answerable — plus the
distinction the ADR spends a paragraph on: *no longer true* and *never was
true* are different states, and collapsing them destroys clinical meaning.
"""

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.patients_clinical.models import Allergy, Medication


async def _seed_clinic_and_patient(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict[str, str]
) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]

    clinic = Clinic(
        id=uuid4(),
        name="History Clinic",
        tax_id="B33333333",
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
    return {
        "clinic_id": clinic.id,
        "patient_id": patient.json()["data"]["id"],
        "user_id": user_id,
    }


async def _rows(db_session: AsyncSession, model, patient_id: str) -> list:
    result = await db_session.execute(
        select(model).where(model.patient_id == UUID(patient_id)).order_by(model.created_at)
    )
    return list(result.scalars())


@pytest.mark.asyncio
async def test_deleting_an_allergy_retracts_it_and_keeps_the_row(
    client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
):
    """A penicillin allergy removed on a mistaken tap left no trace at all.

    It is a patient-safety defect before it is a compliance one. The row now
    survives the deletion, marked as taken back and attributed to the account
    that did it.
    """
    seed = await _seed_clinic_and_patient(db_session, client, auth_headers)
    patient_id = seed["patient_id"]

    created = await client.post(
        f"/api/v1/patients_clinical/patients/{patient_id}/allergies",
        headers=auth_headers,
        json={"name": "Penicilina", "severity": "critical", "type": "drug"},
    )
    assert created.status_code == 201
    allergy_id = created.json()["data"]["id"]

    removed = await client.delete(
        f"/api/v1/patients_clinical/patients/{patient_id}/allergies/{allergy_id}",
        headers=auth_headers,
    )
    assert removed.status_code == 204

    rows = await _rows(db_session, Allergy, patient_id)
    assert len(rows) == 1, "the row is retracted, not destroyed"
    assert rows[0].retracted_at is not None
    assert rows[0].recorded_by_user_id == UUID(seed["user_id"])

    # And it is out of sight for everything that reads the live history.
    listed = await client.get(
        f"/api/v1/patients_clinical/patients/{patient_id}/allergies", headers=auth_headers
    )
    assert listed.json()["data"] == []


@pytest.mark.asyncio
async def test_a_retracted_allergy_stops_driving_alerts(
    client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
):
    """The whole reason retraction is not the same as "ended".

    An entry recorded on the wrong patient must stop warning about a drug the
    patient tolerates — while a discontinued medication stays in the history.
    """
    seed = await _seed_clinic_and_patient(db_session, client, auth_headers)
    patient_id = seed["patient_id"]

    created = await client.post(
        f"/api/v1/patients_clinical/patients/{patient_id}/allergies",
        headers=auth_headers,
        json={"name": "Penicilina", "severity": "critical", "type": "drug"},
    )
    allergy_id = created.json()["data"]["id"]

    with_alert = await client.get(
        f"/api/v1/patients_clinical/patients/{patient_id}/alerts", headers=auth_headers
    )
    assert any("Penicilina" in str(alert) for alert in with_alert.json()["data"]["alerts"])

    await client.delete(
        f"/api/v1/patients_clinical/patients/{patient_id}/allergies/{allergy_id}",
        headers=auth_headers,
    )

    after = await client.get(
        f"/api/v1/patients_clinical/patients/{patient_id}/alerts", headers=auth_headers
    )
    assert not any("Penicilina" in str(alert) for alert in after.json()["data"]["alerts"])


@pytest.mark.asyncio
async def test_saving_the_history_form_does_not_rewrite_the_history(
    client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
):
    """The bulk save used to delete every row and insert new ones.

    Not a hazard reserved for a mistaken tap: the normal path destroyed the
    history on every visit, so an allergy lost the date it was first recorded
    and nobody could say since when it was known. The row must survive a save
    that does not touch it — same id, same `created_at`.
    """
    seed = await _seed_clinic_and_patient(db_session, client, auth_headers)
    patient_id = seed["patient_id"]

    first = await client.put(
        f"/api/v1/patients_clinical/patients/{patient_id}/medical-history",
        headers=auth_headers,
        json={
            "allergies": [{"name": "Penicilina", "severity": "critical"}],
            "medications": [{"name": "Sintrom", "dosage": "4mg"}],
        },
    )
    assert first.status_code == 200
    stored = await _rows(db_session, Allergy, patient_id)
    assert len(stored) == 1
    original_id, original_created = stored[0].id, stored[0].created_at

    # The form comes back carrying the ids it was given, with one edit and one
    # addition — exactly what the screen submits.
    history = first.json()["data"]
    history["allergies"][0]["severity"] = "high"
    history["allergies"].append({"name": "Látex", "severity": "medium"})

    second = await client.put(
        f"/api/v1/patients_clinical/patients/{patient_id}/medical-history",
        headers=auth_headers,
        json=history,
    )
    assert second.status_code == 200

    await db_session.commit()
    rows = await _rows(db_session, Allergy, patient_id)
    assert len(rows) == 2
    kept = next(row for row in rows if row.id == original_id)
    assert kept.created_at == original_created, "the row was preserved, not recreated"
    assert kept.severity == "high", "and it was updated in place"
    assert all(row.retracted_at is None for row in rows)


@pytest.mark.asyncio
async def test_a_line_dropped_from_the_form_is_retracted_not_deleted(
    client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
):
    """Removing a line is the user taking the entry back.

    It is recorded as a retraction rather than an end date, because the form
    has no field for "when did this stop being true" and inventing one would
    put a clinical claim in the record that nobody made. The reason says where
    it came from.
    """
    seed = await _seed_clinic_and_patient(db_session, client, auth_headers)
    patient_id = seed["patient_id"]

    first = await client.put(
        f"/api/v1/patients_clinical/patients/{patient_id}/medical-history",
        headers=auth_headers,
        json={"medications": [{"name": "Sintrom", "dosage": "4mg"}]},
    )
    history = first.json()["data"]
    assert len(history["medications"]) == 1

    history["medications"] = []
    dropped = await client.put(
        f"/api/v1/patients_clinical/patients/{patient_id}/medical-history",
        headers=auth_headers,
        json=history,
    )
    assert dropped.status_code == 200
    assert dropped.json()["data"]["medications"] == []

    await db_session.commit()
    rows = await _rows(db_session, Medication, patient_id)
    assert len(rows) == 1
    assert rows[0].retracted_at is not None
    assert rows[0].ended_at is None, "dropped from a form is not a clinical end date"
    assert rows[0].retraction_reason == "removed_from_history_form"


@pytest.mark.asyncio
async def test_a_discontinued_medication_stays_readable_as_history(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict[str, str]
):
    """ "No longer true" is not "never was true".

    A medication the patient stopped taking is a clinical fact with an end
    date: out of the live list, still part of the record a colleague reads.
    """
    from app.modules.patients_clinical.service import PatientsClinicalService

    seed = await _seed_clinic_and_patient(db_session, client, auth_headers)
    patient_id = UUID(seed["patient_id"])

    med = await PatientsClinicalService.create_medication(
        db_session, seed["clinic_id"], patient_id, {"name": "Sintrom", "dosage": "4mg"}
    )
    from datetime import UTC, datetime

    med.ended_at = datetime.now(UTC)
    await db_session.commit()

    live = await PatientsClinicalService.list_medications(db_session, patient_id)
    assert live == []

    everything = await PatientsClinicalService.list_medications(
        db_session, patient_id, include_history=True
    )
    assert [row.name for row in everything] == ["Sintrom"]
    assert everything[0].retracted_at is None, "ending is not retracting"


@pytest.mark.asyncio
async def test_retracting_twice_keeps_the_first_retraction(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict[str, str]
):
    """The first retraction is the one that happened; a second is not an event."""
    from app.modules.patients_clinical.service import PatientsClinicalService

    seed = await _seed_clinic_and_patient(db_session, client, auth_headers)
    patient_id = UUID(seed["patient_id"])

    allergy = await PatientsClinicalService.create_allergy(
        db_session, seed["clinic_id"], patient_id, {"name": "Penicilina", "severity": "high"}
    )
    await PatientsClinicalService.retract_entry(db_session, allergy, reason="first")
    stamped = allergy.retracted_at

    await PatientsClinicalService.retract_entry(db_session, allergy, reason="second")
    assert allergy.retracted_at == stamped
    assert allergy.retraction_reason == "first"
