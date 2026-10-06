"""What media offers other modules without being imported (ADR 0039)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contracts import DocumentKindUsage

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

    async def usage_by_kind(self, db: AsyncSession) -> list[DocumentKindUsage]:
        # Deliberately not filtered by clinic: the figure is the tenant's
        # (see the contract). Sizes only, no rows.
        size = func.coalesce(func.sum(Document.file_size), 0)
        result = await db.execute(
            select(Document.media_kind, size, func.count())
            .group_by(Document.media_kind)
            .order_by(size.desc(), Document.media_kind)
        )
        return [
            DocumentKindUsage(kind=kind, bytes=int(total), count=count)
            for kind, total, count in result.all()
        ]


documents = MediaPatientDocuments()
