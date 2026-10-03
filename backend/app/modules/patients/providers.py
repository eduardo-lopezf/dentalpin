"""What patients offers other modules without being imported (ADR 0039)."""

from __future__ import annotations

from collections.abc import Collection
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contracts import PersonBrief

from .models import Patient


class PatientsDirectory:
    async def is_bookable(self, db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> bool:
        result = await db.execute(
            select(Patient.id).where(
                Patient.id == patient_id,
                Patient.clinic_id == clinic_id,
                Patient.status != "archived",
            )
        )
        return result.scalar_one_or_none() is not None

    async def briefs(
        self, db: AsyncSession, clinic_id: UUID, patient_ids: Collection[UUID]
    ) -> dict[UUID, PersonBrief]:
        if not patient_ids:
            return {}
        result = await db.execute(
            select(
                Patient.id, Patient.first_name, Patient.last_name, Patient.phone, Patient.email
            ).where(Patient.clinic_id == clinic_id, Patient.id.in_(patient_ids))
        )
        return {
            row.id: PersonBrief(
                id=row.id,
                first_name=row.first_name,
                last_name=row.last_name,
                phone=row.phone,
                email=row.email,
            )
            for row in result.all()
        }


patients_directory = PatientsDirectory()
