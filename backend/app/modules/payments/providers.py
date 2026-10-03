"""What payments offers other modules without being imported (ADR 0039)."""

from __future__ import annotations

from collections.abc import Collection
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .service import LedgerService


class PaymentsCollections:
    async def plan_has_collections(
        self,
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        budget_ids: Collection[UUID],
        treatment_ids: Collection[UUID],
    ) -> bool:
        return await LedgerService.plan_has_collections(
            db, clinic_id, patient_id, list(budget_ids), list(treatment_ids)
        )


collections = PaymentsCollections()
