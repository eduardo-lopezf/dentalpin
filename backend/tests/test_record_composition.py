"""The clinical record is composed from the modules, not stored.

Phase 1 of `docs/features/expediente-clinico.md`. What these pin is the
property the whole design rests on: the record owns no clinical data, so it
cannot drift from the source — and the contract that makes that possible,
`get_record_sections()`, behaves like its sibling `get_subject_contributors()`
without being it.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.core.record import EntryStatus, RecordSection, SectionCategory
from app.modules.patients_clinical.service import PatientsClinicalService
from app.modules.record.service import RecordService


async def _bootstrap(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict[str, str]
) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]

    clinic = Clinic(
        id=uuid4(),
        name="Record Clinic",
        tax_id="B66666666",
        address={"street": "x", "city": "y"},
        settings={},
        account_tier="clinic",
    )
    db_session.add(clinic)
    await db_session.flush()
    db_session.add(ClinicMembership(id=uuid4(), user_id=user_id, clinic_id=clinic.id, role="admin"))
    await db_session.commit()

    patient = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "Ana", "last_name": "García", "phone": "+34699111222"},
    )
    return {
        "clinic_id": clinic.id,
        "patient_id": UUID(patient.json()["data"]["id"]),
        "user_id": UUID(user_id),
    }


class TestTheContract:
    def test_a_section_must_say_where_its_title_comes_from(self) -> None:
        """A record is read in one language and exported in another.

        A Spanish literal baked into a section would be wrong in both places
        the moment either changes, so the key is required rather than
        encouraged.
        """
        with pytest.raises(ValueError, match="title_key"):
            RecordSection(
                name="allergies",
                title_key="",
                category=SectionCategory.ANTECEDENTS,
                collect=lambda db, c, p: [],
            )

    def test_a_section_must_be_named(self) -> None:
        with pytest.raises(ValueError, match="name cannot be empty"):
            RecordSection(
                name="",
                title_key="record.section.x",
                category=SectionCategory.ANTECEDENTS,
                collect=lambda db, c, p: [],
            )


@pytest.mark.asyncio
class TestComposition:
    async def test_the_record_is_built_from_the_modules_that_own_the_data(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
    ) -> None:
        """No table of its own: the allergy is read where the allergy lives."""
        seed = await _bootstrap(db_session, client, auth_headers)
        await PatientsClinicalService.create_allergy(
            db_session,
            seed["clinic_id"],
            seed["patient_id"],
            {"name": "Penicilina", "severity": "critical"},
            user_id=seed["user_id"],
        )
        await db_session.commit()

        record = await RecordService.compose(db_session, seed["clinic_id"], seed["patient_id"])
        assert record is not None

        by_name = {section.qualified_name: section for section in record.sections}
        assert "patients_clinical.allergies" in by_name
        entries = by_name["patients_clinical.allergies"].entries
        assert [entry.summary for entry in entries] == ["Penicilina"]
        assert entries[0].source_table == "patients_clinical_allergy"
        assert entries[0].recorded_by_user_id == seed["user_id"]

    async def test_empty_sections_still_come_back(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
    ) -> None:
        """ "This module holds nothing" is an answer; a missing section is not.

        A reader of a record has to be able to tell the difference between a
        patient with no known allergies and a record that never asked.
        """
        seed = await _bootstrap(db_session, client, auth_headers)

        record = await RecordService.compose(db_session, seed["clinic_id"], seed["patient_id"])
        assert record is not None
        names = {section.qualified_name for section in record.sections}
        assert "patients_clinical.allergies" in names
        assert all(section.entries == [] for section in record.sections)

    async def test_retracted_entries_are_left_out_unless_asked_for(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
    ) -> None:
        """Never deleted, not handed over by default.

        An entry that should never have been recorded is not part of what a
        colleague receives — but "what did the chart say that day" has to stay
        answerable, so it is one explicit flag away (ADR 0032).
        """
        seed = await _bootstrap(db_session, client, auth_headers)
        allergy = await PatientsClinicalService.create_allergy(
            db_session,
            seed["clinic_id"],
            seed["patient_id"],
            {"name": "Paciente equivocado", "severity": "high"},
            user_id=seed["user_id"],
        )
        await PatientsClinicalService.retract_entry(db_session, allergy, reason="wrong patient")
        await db_session.commit()

        default = await RecordService.compose(db_session, seed["clinic_id"], seed["patient_id"])
        allergies = next(
            s for s in default.sections if s.qualified_name == "patients_clinical.allergies"
        )
        assert allergies.entries == []

        full = await RecordService.compose(
            db_session, seed["clinic_id"], seed["patient_id"], include_retracted=True
        )
        allergies = next(
            s for s in full.sections if s.qualified_name == "patients_clinical.allergies"
        )
        assert [e.status for e in allergies.entries] == [EntryStatus.RETRACTED]

    async def test_a_discontinued_entry_stays_in_the_record(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
    ) -> None:
        """ "No longer true" is part of the history a colleague reads."""
        seed = await _bootstrap(db_session, client, auth_headers)
        med = await PatientsClinicalService.create_medication(
            db_session,
            seed["clinic_id"],
            seed["patient_id"],
            {"name": "Sintrom"},
            user_id=seed["user_id"],
        )
        med.ended_at = datetime.now(UTC)
        await db_session.commit()

        record = await RecordService.compose(db_session, seed["clinic_id"], seed["patient_id"])
        meds = next(
            s for s in record.sections if s.qualified_name == "patients_clinical.medications"
        )
        assert [(e.summary, e.status) for e in meds.entries] == [("Sintrom", EntryStatus.ENDED)]

    async def test_entries_sort_by_clinical_time_not_by_when_they_were_typed(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
    ) -> None:
        """A surgery recorded today that happened in 2019 sorts into 2019.

        Getting this wrong turns a record into a data-entry log, which is not
        what a colleague is reading it for.
        """
        seed = await _bootstrap(db_session, client, auth_headers)
        for name, year in (("Reciente", 2024), ("Antigua", 2019)):
            await PatientsClinicalService.create_surgical_history(
                db_session,
                seed["clinic_id"],
                seed["patient_id"],
                {"procedure": name, "surgery_date": datetime(year, 5, 1).date()},
                user_id=seed["user_id"],
            )
        await db_session.commit()

        record = await RecordService.compose(db_session, seed["clinic_id"], seed["patient_id"])
        surgeries = next(
            s for s in record.sections if s.qualified_name == "patients_clinical.surgical_history"
        )
        assert [e.summary for e in surgeries.entries] == ["Antigua", "Reciente"]

    async def test_a_patient_of_another_clinic_has_no_record_here(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
    ) -> None:
        seed = await _bootstrap(db_session, client, auth_headers)
        assert await RecordService.compose(db_session, uuid4(), seed["patient_id"]) is None


@pytest.mark.asyncio
async def test_billing_contributes_nothing_to_a_clinical_record(
    db_session: AsyncSession,
) -> None:
    """A referral is not a financial document.

    The fiscal modules answer the subject-rights question — it is the
    patient's data — and stay out of the clinical one. A disclosure carrying
    invoice data is a privacy defect, not a feature.
    """
    from app.core.plugins.registry import module_registry

    financial = {"billing", "payments", "verifactu", "accounting_export", "cashbox"}
    for module in module_registry.list_modules():
        if module.name in financial:
            assert module.get_record_sections() == [], module.name
