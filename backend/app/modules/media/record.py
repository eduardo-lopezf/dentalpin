"""What this module contributes to a clinical record: radiographs and
clinical photographs.

The entry says that the image exists, what it is and when it was taken;
the file itself stays where it is. Administrative documents — an identity
scan, an insurance card — are not imaging and are left out.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.record import EntryStatus, RecordEntry, RecordSection, SectionCategory

from .models import Document

_IMAGING = ("photo", "xray")


async def _collect(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> list[RecordEntry]:
    result = await db.execute(
        select(Document).where(
            Document.clinic_id == clinic_id,
            Document.patient_id == patient_id,
            Document.media_kind.in_(_IMAGING),
        )
    )
    return [
        RecordEntry(
            occurred_at=document.captured_at or document.created_at,
            summary=document.title,
            detail={
                "media_kind": document.media_kind,
                "media_category": document.media_category,
                "media_subtype": document.media_subtype,
                "description": document.description,
            },
            # An archived image was taken out of the gallery, not destroyed.
            status=EntryStatus.ACTIVE if document.status == "active" else EntryStatus.RETRACTED,
            recorded_by_user_id=document.uploaded_by,
            source_table="documents",
            source_id=document.id,
        )
        for document in result.scalars()
    ]


def get_record_sections() -> list[RecordSection]:
    return [
        RecordSection(
            name="imaging",
            title_key="record.section.imaging",
            category=SectionCategory.IMAGING,
            collect=_collect,
        )
    ]
