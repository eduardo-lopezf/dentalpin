"""What professionals offers other modules without being imported (ADR 0039)."""

from __future__ import annotations

from collections.abc import Collection
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import User
from app.core.contracts import PersonBrief

from .models import Professional

BOOKABLE_TYPES = ("dentist", "hygienist")


class ProfessionalsDirectory:
    async def is_bookable(self, db: AsyncSession, clinic_id: UUID, professional_id: UUID) -> bool:
        # Appointments target a directory profile — a bare account id is
        # never valid here, even when a profile happens to share its id
        # with a user (see ``ensure_profile``).
        result = await db.execute(
            select(Professional.id).where(
                Professional.id == professional_id,
                Professional.clinic_id == clinic_id,
                Professional.is_active.is_(True),
                Professional.professional_type.in_(BOOKABLE_TYPES),
            )
        )
        return result.scalar_one_or_none() is not None

    async def briefs(
        self, db: AsyncSession, clinic_id: UUID, professional_ids: Collection[UUID]
    ) -> dict[UUID, PersonBrief]:
        if not professional_ids:
            return {}
        result = await db.execute(
            select(
                Professional.id,
                Professional.first_name,
                Professional.last_name,
                Professional.email,
                Professional.license_number,
            ).where(Professional.clinic_id == clinic_id, Professional.id.in_(professional_ids))
        )
        return {
            row.id: PersonBrief(
                id=row.id,
                first_name=row.first_name,
                last_name=row.last_name,
                email=row.email,
                license_number=row.license_number,
            )
            for row in result.all()
        }

    async def list_bookable(self, db: AsyncSession, clinic_id: UUID) -> list[PersonBrief]:
        result = await db.execute(
            select(Professional.id, Professional.first_name, Professional.last_name).where(
                Professional.clinic_id == clinic_id,
                Professional.professional_type.in_(BOOKABLE_TYPES),
                Professional.is_active.is_(True),
            )
        )
        return [
            PersonBrief(id=row.id, first_name=row.first_name, last_name=row.last_name)
            for row in result.all()
        ]

    async def ensure_profile(self, db: AsyncSession, clinic_id: UUID, account_id: UUID) -> None:
        # Tests and some import paths still pass a ``User`` id where a
        # profile id belongs. Mirror the account into the directory under
        # the same id so the foreign key holds.
        exists = await db.execute(
            select(Professional.id).where(
                Professional.id == account_id, Professional.clinic_id == clinic_id
            )
        )
        if exists.scalar_one_or_none() is not None:
            return
        user = await db.get(User, account_id)
        if user is None:
            return
        db.add(
            Professional(
                id=account_id,
                clinic_id=clinic_id,
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                email=user.email,
            )
        )
        await db.flush()

    async def profile_for_account(
        self, db: AsyncSession, clinic_id: UUID, account_id: UUID, professional_type: str
    ) -> UUID:
        # The account's own id is checked first: it is the id the demo
        # seed gives the profile it creates for each clinical user, and
        # what every appointment, plan item and commission in the demo
        # points at. Deriving without looking made a *second* profile for
        # the same person on every seed — a duplicate in every picker,
        # with the weekly hours hanging off the copy nobody books.
        by_account = await db.get(Professional, account_id)
        if by_account is not None and by_account.clinic_id == clinic_id:
            return by_account.id

        # The derived id is the one the `*_use_directory_professionals`
        # migrations use for an account with no profile yet; keeping it
        # here keeps the two in step.
        # The "dentalpin:" prefix is a frozen hash seed, not branding. Five
        # migrations have already derived profile ids from this exact string
        # on live databases; changing it would make this function compute
        # different ids and stop finding the rows those migrations wrote. It
        # survives the rename to Diente Azul for the same reason a primary
        # key would.
        profile_id = uuid5(NAMESPACE_URL, f"dentalpin:legacy-professional:{clinic_id}:{account_id}")
        if await db.get(Professional, profile_id) is not None:
            return profile_id

        user = await db.get(User, account_id)
        if user is None:
            raise ValueError(f"Demo user {account_id} does not exist")
        db.add(
            Professional(
                id=profile_id,
                clinic_id=clinic_id,
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
                professional_type=professional_type,
                is_active=user.is_active,
            )
        )
        await db.flush()
        return profile_id

    async def for_account(
        self, db: AsyncSession, clinic_id: UUID, account_id: UUID | None
    ) -> UUID | None:
        from .service import ProfessionalService

        return await ProfessionalService.for_user(db, clinic_id, account_id)


professionals_directory = ProfessionalsDirectory()
