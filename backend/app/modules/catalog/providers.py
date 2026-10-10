"""What the catalog offers other modules without being imported (ADR 0039)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contracts import ReferenceSpecialty

from .models import Specialty
from .seed import all_specialties

#: The discipline no clinic is created without: general dentistry is what
#: the Treatments App is, before any speciality is added to it.
REQUIRED_SPECIALTIES = frozenset({"general"})


class CatalogReferenceSpecialties:
    def available(self) -> list[ReferenceSpecialty]:
        return [
            ReferenceSpecialty(
                key=specialty["key"],
                names=specialty["names"],
                required=specialty["key"] in REQUIRED_SPECIALTIES,
            )
            for specialty in all_specialties()
        ]

    async def enabled(self, db: AsyncSession, clinic_id: UUID) -> list[str]:
        rows = await db.scalars(
            select(Specialty.key).where(
                Specialty.clinic_id == clinic_id,
                Specialty.key.is_not(None),
                Specialty.is_active.is_(True),
            )
        )
        active = set(rows)
        return [specialty["key"] for specialty in all_specialties() if specialty["key"] in active]


specialties = CatalogReferenceSpecialties()
