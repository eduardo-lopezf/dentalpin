"""What this module contributes to a clinical record: the periodontal
chartings, one entry each, with the indices computed when it was closed."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.record import RecordEntry, RecordSection, SectionCategory

from .models import PeriodontogramSnapshot


async def _collect(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> list[RecordEntry]:
    result = await db.execute(
        select(PeriodontogramSnapshot).where(
            PeriodontogramSnapshot.clinic_id == clinic_id,
            PeriodontogramSnapshot.patient_id == patient_id,
        )
    )
    return [
        RecordEntry(
            occurred_at=snapshot.recorded_at,
            summary=snapshot.notes or "",
            detail={
                "status": snapshot.status,
                "closed_at": snapshot.closed_at,
                **(snapshot.indices or {}),
            },
            recorded_by_user_id=snapshot.recorded_by,
            source_table="periodontogram_snapshots",
            source_id=snapshot.id,
        )
        for snapshot in result.scalars()
    ]


def get_record_sections() -> list[RecordSection]:
    return [
        RecordSection(
            name="chartings",
            title_key="record.section.chartings",
            category=SectionCategory.PERIODONTAL,
            collect=_collect,
        )
    ]
