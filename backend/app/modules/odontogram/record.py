"""What this module contributes to a clinical record: the dental chart.

Every finding and treatment charted on the patient's teeth, each with the
teeth and surfaces it concerns. A withdrawn one is kept as retracted, so
"what did the chart say that day" stays answerable (ADR 0032).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.record import EntryStatus, RecordEntry, RecordSection, SectionCategory

from .models import Treatment


def _name(treatment: Treatment) -> str:
    names = (treatment.catalog_item.names or {}) if treatment.catalog_item else {}
    return names.get("es") or names.get("en") or treatment.clinical_type


async def _collect(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> list[RecordEntry]:
    result = await db.execute(
        select(Treatment)
        .where(Treatment.clinic_id == clinic_id, Treatment.patient_id == patient_id)
        .options(selectinload(Treatment.teeth), selectinload(Treatment.catalog_item))
    )
    return [
        RecordEntry(
            # When it was done, if it was; otherwise when it was charted.
            occurred_at=treatment.performed_at or treatment.recorded_at,
            summary=_name(treatment),
            detail={
                "clinical_type": treatment.clinical_type,
                "status": treatment.status,
                "scope": treatment.scope,
                "arch": treatment.arch,
                "teeth": [
                    {"tooth_number": tooth.tooth_number, "surfaces": tooth.surfaces}
                    for tooth in treatment.teeth
                ],
                "performed_at": treatment.performed_at,
                "notes": treatment.notes,
            },
            status=EntryStatus.RETRACTED if treatment.deleted_at else EntryStatus.ACTIVE,
            recorded_by_user_id=treatment.performed_by,
            source_table="treatments",
            source_id=treatment.id,
        )
        for treatment in result.scalars()
    ]


def get_record_sections() -> list[RecordSection]:
    return [
        RecordSection(
            name="chart",
            title_key="record.section.chart",
            category=SectionCategory.ODONTOGRAM,
            collect=_collect,
        )
    ]
