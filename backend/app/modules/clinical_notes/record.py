"""What this module contributes to a clinical record: the evolution notes.

Clinical notes only — diagnosis, treatment, plan and visit notes. The
administrative ones ("prefers mornings", "called to reschedule") are about
running the clinic, and a record handed to a colleague is not the place
for them.

A note hangs from a patient, or from one of their treatments, plans or
appointments; all four are gathered. With the Agenda App off, the notes
left in visits are not offered (ADR 0037) — they are still stored.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contracts import AppointmentBook, provider
from app.core.record import EntryStatus, RecordEntry, RecordSection, SectionCategory
from app.modules.odontogram.models import Treatment
from app.modules.treatment_plan.models import TreatmentPlan

from .models import (
    NOTE_TYPE_ADMINISTRATIVE,
    NOTE_TYPE_APPOINTMENT_ADMINISTRATIVE,
    ClinicalNote,
)
from .service import patient_owner_filter

_NOT_CLINICAL = (NOTE_TYPE_ADMINISTRATIVE, NOTE_TYPE_APPOINTMENT_ADMINISTRATIVE)


async def _ids(db: AsyncSession, model, clinic_id: UUID, patient_id: UUID) -> list[UUID]:
    """Deleted owners included: a note about a withdrawn treatment was
    still written about this patient."""
    result = await db.execute(
        select(model.id).where(model.clinic_id == clinic_id, model.patient_id == patient_id)
    )
    return list(result.scalars())


async def _collect(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> list[RecordEntry]:
    book = provider(AppointmentBook)
    owners = patient_owner_filter(
        patient_id,
        await _ids(db, Treatment, clinic_id, patient_id),
        await _ids(db, TreatmentPlan, clinic_id, patient_id),
        await book.ids_for_patient(db, clinic_id, patient_id) if book else [],
    )
    result = await db.execute(
        select(ClinicalNote).where(
            ClinicalNote.clinic_id == clinic_id,
            ClinicalNote.note_type.notin_(_NOT_CLINICAL),
            owners,
        )
    )
    return [
        RecordEntry(
            occurred_at=note.created_at,
            summary=note.body,
            detail={
                "note_type": note.note_type,
                "tooth_number": note.tooth_number,
                "version": note.version,
                "amended_at": note.amended_at,
                **(note.vitals or {}),
            },
            status=EntryStatus.RETRACTED if note.deleted_at else EntryStatus.ACTIVE,
            authored_by_professional_id=note.authored_by_professional_id,
            recorded_by_user_id=note.author_id,
            source_table="clinical_notes",
            source_id=note.id,
        )
        for note in result.scalars()
    ]


def get_record_sections() -> list[RecordSection]:
    return [
        RecordSection(
            name="notes",
            title_key="record.section.notes",
            category=SectionCategory.EVOLUTION,
            collect=_collect,
            order=10,
        )
    ]
