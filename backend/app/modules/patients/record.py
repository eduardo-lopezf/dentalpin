"""What this module contributes to a clinical record: who it is about."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.record import RecordEntry, RecordSection, SectionCategory

from .models import Patient


async def _collect(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> list[RecordEntry]:
    patient = (
        await db.execute(
            select(Patient).where(Patient.id == patient_id, Patient.clinic_id == clinic_id)
        )
    ).scalar_one_or_none()
    if patient is None:
        return []
    return [
        RecordEntry(
            occurred_at=patient.created_at,
            summary=f"{patient.first_name} {patient.last_name}".strip(),
            # The identity a record opens with. Billing data is left out: a
            # record is not a financial document.
            detail={
                "first_name": patient.first_name,
                "last_name": patient.last_name,
                "date_of_birth": patient.date_of_birth,
                "gender": patient.gender,
                "national_id": patient.national_id,
                "phone": patient.phone,
                "email": patient.email,
                "address": patient.address,
                "profession": patient.profession,
            },
            source_table="patients",
            source_id=patient.id,
        )
    ]


def get_record_sections() -> list[RecordSection]:
    return [
        RecordSection(
            name="identification",
            title_key="record.section.identification",
            category=SectionCategory.IDENTIFICATION,
            collect=_collect,
        )
    ]
