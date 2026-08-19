"""Demo data seed for the schedules module.

Only invoked by ``backend/scripts/seed_demo.py`` and only when the
``schedules`` module is ``installed`` in ``core_module``. Lives inside
the module so uninstalling schedules also removes this seed code —
preserving the optional-module story.
"""

from __future__ import annotations

from datetime import date, time
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.professionals.models import Professional

from .models import (
    ClinicOverride,
    ClinicWeeklySchedule,
    ProfessionalOverride,
    ProfessionalWeeklySchedule,
    ScheduleShift,
)


async def seed_schedules_demo(
    db: AsyncSession,
    clinic_id: UUID,
    dentist_id: UUID,
    hygienist_id: UUID,
) -> dict[str, int]:
    """Seed a realistic weekly schedule for the demo clinic + professionals.

    Idempotent: wipes and recreates the clinic + professional weekly
    templates so re-running the demo seeder gives predictable data.
    Leaves overrides untouched on re-run so manually-created overrides
    during a demo session survive.

    Returns a stats dict for the seed-demo summary.
    """
    stats = {"clinic_shifts": 0, "professional_shifts": 0, "overrides": 0}

    # --- Clinic weekly: Mon–Fri 09:00–14:00 + 16:00–20:00, weekends closed.
    await db.execute(
        delete(ClinicWeeklySchedule).where(ClinicWeeklySchedule.clinic_id == clinic_id)
    )
    clinic_weekly = ClinicWeeklySchedule(clinic_id=clinic_id, is_active=True)
    db.add(clinic_weekly)
    await db.flush()

    for weekday in range(5):  # Mon..Fri
        db.add(
            ScheduleShift(
                clinic_weekly_id=clinic_weekly.id,
                weekday=weekday,
                start_time=time(9, 0),
                end_time=time(14, 0),
            )
        )
        db.add(
            ScheduleShift(
                clinic_weekly_id=clinic_weekly.id,
                weekday=weekday,
                start_time=time(16, 0),
                end_time=time(20, 0),
            )
        )
        stats["clinic_shifts"] += 2
    await db.flush()

    dentist_id = await _ensure_demo_professional(db, clinic_id, dentist_id, "dentist")
    hygienist_id = await _ensure_demo_professional(db, clinic_id, hygienist_id, "hygienist")

    # --- Dentist (Sarah / Dra.): Mon–Fri 09–14 + 16–19.
    await _seed_professional_weekly(
        db,
        clinic_id,
        dentist_id,
        {
            0: [(time(9, 0), time(14, 0)), (time(16, 0), time(19, 0))],
            1: [(time(9, 0), time(14, 0)), (time(16, 0), time(19, 0))],
            2: [(time(9, 0), time(14, 0)), (time(16, 0), time(19, 0))],
            3: [(time(9, 0), time(14, 0)), (time(16, 0), time(19, 0))],
            4: [(time(9, 0), time(14, 0))],  # Friday morning only.
        },
    )
    stats["professional_shifts"] += 9

    # --- Hygienist (Michael): split weeks, Mon/Wed/Fri mornings, Tue/Thu afternoons.
    await _seed_professional_weekly(
        db,
        clinic_id,
        hygienist_id,
        {
            0: [(time(9, 0), time(14, 0))],
            1: [(time(16, 0), time(20, 0))],
            2: [(time(9, 0), time(14, 0))],
            3: [(time(16, 0), time(20, 0))],
            4: [(time(10, 0), time(14, 0))],
        },
    )
    stats["professional_shifts"] += 5

    # --- Sample overrides: clinic closed on Christmas, dentist on vacation
    # the first week of August. Only added when not already present so
    # re-seed doesn't duplicate them.
    stats["overrides"] += await _ensure_clinic_override(
        db,
        clinic_id,
        start=date(2026, 12, 25),
        end=date(2026, 12, 26),
        reason="Christmas holiday",
    )
    stats["overrides"] += await _ensure_professional_override(
        db,
        clinic_id,
        dentist_id,
        start=date(2026, 8, 3),
        end=date(2026, 8, 14),
        reason="Summer vacation",
    )

    return stats


async def _seed_professional_weekly(
    db: AsyncSession,
    clinic_id: UUID,
    professional_id: UUID,
    shifts_by_weekday: dict[int, list[tuple[time, time]]],
) -> None:
    await db.execute(
        delete(ProfessionalWeeklySchedule).where(
            ProfessionalWeeklySchedule.clinic_id == clinic_id,
            ProfessionalWeeklySchedule.professional_id == professional_id,
        )
    )
    weekly = ProfessionalWeeklySchedule(
        clinic_id=clinic_id, professional_id=professional_id, is_active=True
    )
    db.add(weekly)
    await db.flush()

    for weekday, ranges in shifts_by_weekday.items():
        for start, end in ranges:
            db.add(
                ScheduleShift(
                    professional_weekly_id=weekly.id,
                    weekday=weekday,
                    start_time=start,
                    end_time=end,
                )
            )
    await db.flush()


async def _ensure_clinic_override(
    db: AsyncSession,
    clinic_id: UUID,
    *,
    start: date,
    end: date,
    reason: str,
) -> int:

    existing = (
        await db.execute(
            select(ClinicOverride).where(
                ClinicOverride.clinic_id == clinic_id,
                ClinicOverride.start_date == start,
                ClinicOverride.end_date == end,
                ClinicOverride.reason == reason,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return 0
    db.add(
        ClinicOverride(
            clinic_id=clinic_id,
            start_date=start,
            end_date=end,
            kind="closed",
            reason=reason,
        )
    )
    await db.flush()
    return 1


async def _ensure_professional_override(
    db: AsyncSession,
    clinic_id: UUID,
    professional_id: UUID,
    *,
    start: date,
    end: date,
    reason: str,
) -> int:

    existing = (
        await db.execute(
            select(ProfessionalOverride).where(
                ProfessionalOverride.clinic_id == clinic_id,
                ProfessionalOverride.professional_id == professional_id,
                ProfessionalOverride.start_date == start,
                ProfessionalOverride.end_date == end,
                ProfessionalOverride.reason == reason,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return 0
    db.add(
        ProfessionalOverride(
            clinic_id=clinic_id,
            professional_id=professional_id,
            start_date=start,
            end_date=end,
            kind="unavailable",
            reason=reason,
        )
    )
    await db.flush()
    return 1


async def _ensure_demo_professional(
    db: AsyncSession, clinic_id: UUID, legacy_user_id: UUID, professional_type: str
) -> UUID:
    """Return the seeded directory record associated with a demo account.

    The demo input still exposes account IDs, so use a deterministic UUID to
    keep the record stable while all scheduling data points to the directory.
    """
    from uuid import NAMESPACE_URL, uuid5

    professional_id = uuid5(
        NAMESPACE_URL, f"dentalpin:legacy-professional:{clinic_id}:{legacy_user_id}"
    )
    existing = await db.get(Professional, professional_id)
    if existing is not None:
        return existing.id

    from app.core.auth.models import User

    user = await db.get(User, legacy_user_id)
    if user is None:
        raise ValueError(f"Demo user {legacy_user_id} does not exist")
    db.add(
        Professional(
            id=professional_id,
            clinic_id=clinic_id,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            professional_type=professional_type,
            is_active=user.is_active,
        )
    )
    await db.flush()
    return professional_id
