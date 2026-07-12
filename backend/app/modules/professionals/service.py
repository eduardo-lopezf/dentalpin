"""Business logic for clinic professional profiles."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Professional


class ProfessionalService:
    @staticmethod
    async def list(
        db: AsyncSession,
        clinic_id: UUID,
        *,
        search: str | None = None,
        professional_type: str | None = None,
        include_inactive: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Professional], int]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        conditions = [Professional.clinic_id == clinic_id]

        if not include_inactive:
            conditions.append(Professional.is_active.is_(True))
        if professional_type:
            conditions.append(Professional.professional_type == professional_type)
        if search and search.strip():
            terms = search.split()
            full_name = func.concat(Professional.first_name, " ", Professional.last_name)
            conditions.append(
                and_(
                    *(
                        or_(
                            Professional.first_name.ilike(f"%{term}%"),
                            Professional.last_name.ilike(f"%{term}%"),
                            full_name.ilike(f"%{term}%"),
                            Professional.specialty.ilike(f"%{term}%"),
                            Professional.license_number.ilike(f"%{term}%"),
                        )
                        for term in terms
                    )
                )
            )

        total = (
            await db.execute(select(func.count(Professional.id)).where(*conditions))
        ).scalar() or 0
        result = await db.execute(
            select(Professional)
            .where(*conditions)
            .order_by(Professional.last_name, Professional.first_name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    @staticmethod
    async def get(db: AsyncSession, clinic_id: UUID, professional_id: UUID) -> Professional | None:
        result = await db.execute(
            select(Professional).where(
                Professional.id == professional_id,
                Professional.clinic_id == clinic_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, clinic_id: UUID, data: dict) -> Professional:
        professional = Professional(clinic_id=clinic_id, **data)
        db.add(professional)
        await db.flush()
        return professional

    @staticmethod
    async def update(db: AsyncSession, professional: Professional, data: dict) -> Professional:
        for field, value in data.items():
            setattr(professional, field, value)
        await db.flush()
        return professional
