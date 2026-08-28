"""The document type the importer writes must be one the API accepts.

``PatientMapper`` labels every imported identifier ``nif`` — Gesdén is
Spanish software and that is the Spanish individual tax identifier. The
patients schema accepted only ``curp``/``ine``/``passport``, so the value
was written straight to the model (bypassing the schema) and then
rejected the first time anyone saved that patient: the edit modal loads
``national_id_type`` into its form and sends it back untouched, so the
demographics of every imported patient 422'd until the user happened to
change the dropdown.

The two ends are pinned together here rather than in either module alone,
because neither module is wrong on its own — the bug only exists in the
gap between them.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.auth.models import Clinic, User
from app.modules.migration_import.mappers.base import MapperContext, MappingResolver
from app.modules.migration_import.mappers.patient import PatientMapper
from app.modules.migration_import.models import ImportJob
from app.modules.patients.models import Patient
from app.modules.patients.schemas import (
    NATIONAL_ID_TYPES,
    NATIONAL_ID_TYPES_BY_JURISDICTION,
    PatientExtendedUpdate,
)


@pytest.mark.asyncio
async def test_imported_patient_survives_a_demographics_save(db_session) -> None:
    clinic, admin = await _bootstrap(db_session)
    ctx = await _ctx(db_session, clinic.id, admin.id)

    await PatientMapper().apply(
        ctx,
        entity_type="patient",
        payload={
            "given_name": "Ana",
            "family_name": "García",
            "national_id": "12345678Z",
        },
        raw={},
        canonical_uuid=str(uuid4()),
        source_id="1",
        source_system="gesden",
    )
    await db_session.flush()

    patient = (
        await db_session.execute(select(Patient).where(Patient.clinic_id == clinic.id))
    ).scalar_one()
    assert patient.national_id_type is not None

    # What the edit modal does: load the stored value, send it back.
    echoed = PatientExtendedUpdate(national_id_type=patient.national_id_type)
    assert echoed.national_id_type == patient.national_id_type


class TestAcceptedDocumentTypes:
    def test_every_jurisdiction_document_is_accepted(self) -> None:
        for documents in NATIONAL_ID_TYPES_BY_JURISDICTION.values():
            for document in documents:
                assert PatientExtendedUpdate(national_id_type=document)

    def test_both_markets_are_represented(self) -> None:
        # The deployment serves both: verifactu files with the Spanish
        # AEAT while the default currency is MXN.
        assert {"MX", "ES"} <= set(NATIONAL_ID_TYPES_BY_JURISDICTION)
        assert {"curp", "ine", "nif", "passport"} <= NATIONAL_ID_TYPES

    def test_unknown_document_still_rejected(self) -> None:
        # Widening the set must not turn the field into free text.
        with pytest.raises(ValueError, match="national_id_type must be one of"):
            PatientExtendedUpdate(national_id_type="drivers_license")

    def test_none_is_allowed(self) -> None:
        assert PatientExtendedUpdate(national_id_type=None).national_id_type is None


async def _bootstrap(db_session):
    clinic = Clinic(id=uuid4(), name="C", tax_id="B1")
    admin = User(
        id=uuid4(),
        email=f"admin-{uuid4().hex[:8]}@test.local",
        password_hash="x",
        first_name="A",
        last_name="A",
    )
    db_session.add_all([clinic, admin])
    await db_session.flush()
    return clinic, admin


async def _ctx(db_session, clinic_id, admin_id):
    job = ImportJob(
        clinic_id=clinic_id,
        created_by=admin_id,
        status="executing",
        original_filename="t.dpm",
        file_path="/tmp/t.dpm",
        file_size=0,
    )
    db_session.add(job)
    await db_session.flush()
    return MapperContext(
        db=db_session,
        clinic_id=clinic_id,
        job_id=job.id,
        resolver=MappingResolver(db=db_session, clinic_id=clinic_id, job_id=job.id),
        import_fiscal_compliance=False,
        created_by=admin_id,
    )
