"""The health questionnaire a patient answers at a visit.

What these pin: it is a dated declaration, kept as given; only what the
form asks can be answered; a sheet filled in by hand is filed as a scan of
this same patient; a mistaken one is retracted, never deleted; and it
reaches the clinical record.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.media.models import Document
from app.modules.patients.models import Patient
from app.modules.patients_clinical.questionnaire import CONDITION_GROUPS, CONDITIONS, QUESTIONS

ANSWERED = {
    "chief_complaint": "Dolor en molar inferior derecho",
    "blood_type": "O+",
    "answers": {
        "taking_medication": {"answer": True, "detail": "Losartán 50 mg"},
        "major_bleeding": {"answer": False},
    },
    # Out of the form's order on purpose.
    "conditions": ["diabetes", "hypertension"],
}


def _url(patient: Patient) -> str:
    return f"/api/v1/patients_clinical/patients/{patient.id}/questionnaires"


def test_the_form_asks_what_the_paper_form_asks() -> None:
    assert len(QUESTIONS) == 12 and len(CONDITIONS) == 67
    # No condition is listed twice across the blocks.
    assert sum(len(group) for group in CONDITION_GROUPS.values()) == len(CONDITIONS)


@pytest.mark.asyncio
async def test_what_the_patient_declared_is_kept_and_reaches_the_record(
    client: AsyncClient, auth_headers: dict, test_patient: Patient
) -> None:
    made = await client.post(_url(test_patient), headers=auth_headers, json=ANSWERED)
    assert made.status_code == 201, made.text
    saved = made.json()["data"]
    assert saved["conditions"] == ["hypertension", "diabetes"]  # the form's order
    assert saved["answers"]["taking_medication"]["detail"] == "Losartán 50 mg"

    record = await client.get(f"/api/v1/record/patients/{test_patient.id}", headers=auth_headers)
    data = record.json()["data"]
    sections = {(s["module"], s["name"]): s for s in data["sections"]}
    [entry] = sections[("patients_clinical", "health_questionnaires")]["entries"]
    assert entry["summary"] == "Dolor en molar inferior derecho"
    # Only what was answered "yes" is what a reader scans for.
    assert entry["detail"]["affirmative_answers"] == [
        {"question": "taking_medication", "detail": "Losartán 50 mg"}
    ]
    coverage = {item["key"]: item["met"] for item in data["coverage"]}
    assert coverage["chief_complaint"] and coverage["personal_history"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"answers": {"favourite_colour": {"answer": True}}},
        {"conditions": ["lycanthropy"]},
        {},
    ],
)
async def test_only_what_the_form_asks_can_be_answered(
    client: AsyncClient, auth_headers: dict, test_patient: Patient, body: dict
) -> None:
    refused = await client.post(_url(test_patient), headers=auth_headers, json=body)
    assert refused.status_code == 400, refused.text


@pytest.mark.asyncio
async def test_a_sheet_filled_in_by_hand_is_filed_as_a_scan_of_the_same_patient(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
) -> None:
    other = Patient(id=uuid4(), clinic_id=test_clinic.id, first_name="Otra", last_name="Persona")
    db_session.add(other)
    uploader = (await db_session.execute(select(User))).scalars().first()

    def scan(patient: Patient) -> Document:
        return Document(
            clinic_id=test_clinic.id,
            patient_id=patient.id,
            document_type="report",
            title="Cuestionario",
            original_filename="cuestionario.pdf",
            storage_path=f"test/{uuid4()}.pdf",
            mime_type="application/pdf",
            file_size=1,
            uploaded_by=uploader.id,
        )

    mine, theirs = scan(test_patient), scan(other)
    db_session.add_all([mine, theirs])
    await db_session.commit()

    refused = await client.post(
        _url(test_patient), headers=auth_headers, json={"scan_document_id": str(theirs.id)}
    )
    assert refused.status_code == 400, refused.text

    filed = await client.post(
        _url(test_patient),
        headers=auth_headers,
        json={"chief_complaint": "Revisión", "scan_document_id": str(mine.id)},
    )
    assert filed.status_code == 201, filed.text
    assert filed.json()["data"]["scan_document_id"] == str(mine.id)


@pytest.mark.asyncio
async def test_a_mistaken_questionnaire_is_retracted_not_deleted(
    client: AsyncClient, auth_headers: dict, test_patient: Patient
) -> None:
    made = (await client.post(_url(test_patient), headers=auth_headers, json=ANSWERED)).json()
    retracted = await client.post(
        f"{_url(test_patient)}/{made['data']['id']}/retract",
        headers=auth_headers,
        json={"reason": "Paciente equivocado"},
    )
    assert retracted.status_code == 200, retracted.text

    listed = await client.get(_url(test_patient), headers=auth_headers)
    assert listed.json()["data"] == []
    full = await client.get(
        f"/api/v1/record/patients/{test_patient.id}?include_retracted=true", headers=auth_headers
    )
    sections = {(s["module"], s["name"]): s for s in full.json()["data"]["sections"]}
    [entry] = sections[("patients_clinical", "health_questionnaires")]["entries"]
    assert entry["status"] == "retracted"


@pytest.mark.asyncio
async def test_the_blank_form_prints(
    client: AsyncClient, auth_headers: dict, test_patient: Patient
) -> None:
    for locale in ("es", "en"):
        form = await client.get(
            f"/api/v1/patients_clinical/patients/{test_patient.id}/questionnaire-form?locale={locale}",
            headers=auth_headers,
        )
        assert form.status_code == 200, form.text
        assert form.headers["content-type"] == "application/pdf"
        assert form.content.startswith(b"%PDF")
