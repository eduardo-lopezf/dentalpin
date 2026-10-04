"""What media offers other modules without being imported (ADR 0039)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Document


class MediaPatientDocuments:
    async def belongs_to(
        self, db: AsyncSession, clinic_id: UUID, patient_id: UUID, document_id: UUID
    ) -> bool:
        result = await db.execute(
            select(Document.id).where(
                Document.id == document_id,
                Document.clinic_id == clinic_id,
                Document.patient_id == patient_id,
                Document.status == "active",
            )
        )
        return result.scalar_one_or_none() is not None


documents = MediaPatientDocuments()
