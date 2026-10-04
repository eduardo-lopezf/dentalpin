"""What this module contributes to a record: the times it was handed over.

A disclosure is part of the record it discloses (ADR 0033): who received
it, why and when sits next to the acts it concerns, not in a separate log.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.record import RecordEntry, RecordSection, SectionCategory

from .models import Disclosure


async def _collect(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> list[RecordEntry]:
    result = await db.execute(
        select(Disclosure).where(
            Disclosure.clinic_id == clinic_id, Disclosure.patient_id == patient_id
        )
    )
    return [
        RecordEntry(
            occurred_at=row.created_at,
            summary=row.recipient_name,
            detail={
                "purpose": row.purpose,
                "evidence": row.evidence,
                "identity_verified": row.identity_verified or None,
                "document_sha256": row.document_sha256,
            },
            authored_by_professional_id=row.disclosed_by_professional_id,
            recorded_by_user_id=row.disclosed_by_user_id,
            source_table="record_disclosure",
            source_id=row.id,
        )
        for row in result.scalars()
    ]


def get_record_sections() -> list[RecordSection]:
    return [
        RecordSection(
            name="disclosures",
            title_key="record.section.disclosures",
            category=SectionCategory.DISCLOSURES,
            collect=_collect,
        )
    ]
