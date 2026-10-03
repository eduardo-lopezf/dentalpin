"""KanbanDayService — per-day operational snapshot for the kanban board.

Produces the payload consumed by the professionals strip:

    {
      date, clinic_id,
      professionals: [{
        id, first_name, last_name,
        state: "free" | "in_treatment" | "on_break" | "off",
        current_appointment_id?: UUID,
        current_cabinet_id?: UUID
      }]
    }

Module-isolation rules: ``schedules`` is optional at runtime. If it's
installed we consult its availability service to distinguish ``on_break``
and ``off`` from plain ``free`` / ``in_treatment``. If it isn't, every
professional outside of an active treatment is simply ``free`` — the
module keeps working without the extra nuance.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import ClinicMembership, User

from .integrations import professionals, working_hours
from .models import Appointment


async def _fetch_professionals(db: AsyncSession, clinic_id: UUID) -> list[tuple[UUID, str, str]]:
    """Return every active, schedulable professional in the clinic.

    None while the Professionals App is off: the directory is theirs to
    offer (ADR 0037).
    """
    directory = professionals()
    if directory is None:
        return []

    pros: list[tuple[UUID, str, str]] = [
        (p.id, p.first_name, p.last_name) for p in await directory.list_bookable(db, clinic_id)
    ]

    # Also include active `User` accounts that have a ClinicMembership with a
    # clinical role (dentist/hygienist) and don't already have a directory
    # Professional row. This keeps the kanban working in test harnesses that
    # seed users+memberships instead of directory professionals.
    existing_ids = {p[0] for p in pros}
    result = await db.execute(
        select(User.id, User.first_name, User.last_name)
        .join(ClinicMembership, ClinicMembership.user_id == User.id)
        .where(
            ClinicMembership.clinic_id == clinic_id,
            ClinicMembership.role.in_(["dentist", "hygienist"]),
            User.is_active.is_(True),
        )
    )
    for r in result.all():
        if r.id in existing_ids:
            continue
        pros.append((r.id, r.first_name, r.last_name))

    return pros


async def _fetch_active_treatments(
    db: AsyncSession, clinic_id: UUID, day_start: datetime, day_end: datetime
) -> dict[UUID, tuple[UUID, UUID | None]]:
    """Map ``professional_id -> (appointment_id, cabinet_id)`` for the
    single appointment each professional is currently treating today."""
    result = await db.execute(
        select(
            Appointment.professional_id,
            Appointment.id,
            Appointment.cabinet_id,
        ).where(
            Appointment.clinic_id == clinic_id,
            Appointment.status == "in_treatment",
            Appointment.professional_id.isnot(None),
            Appointment.start_time >= day_start,
            Appointment.start_time <= day_end,
        )
    )
    out: dict[UUID, tuple[UUID, UUID | None]] = {}
    for prof_id, apt_id, cab_id in result.all():
        # A professional should only have one in-flight appointment at a
        # time — if multiple somehow exist, the first one wins; downstream
        # analytics have the full picture.
        out.setdefault(prof_id, (apt_id, cab_id))
    return out


async def _fetch_schedule_states(
    db: AsyncSession,
    clinic_id: UUID,
    professional_ids: list[UUID],
    target: datetime,
) -> dict[UUID, str]:
    """Return ``professional_id -> state`` where ``state`` is ``"on_break"``
    (the professional has working hours today but this minute is a closed
    block inside them) or ``"off"`` (outside working hours entirely).

    Asks whoever supplies working hours — the ``schedules`` module, when
    it runs. With nobody to ask, every professional defaults to ``free``
    / ``in_treatment``.
    """
    hours = working_hours()
    if hours is None:
        return {}
    return await hours.professional_states(db, clinic_id, professional_ids, target)


class KanbanDayService:
    @staticmethod
    async def snapshot(
        db: AsyncSession,
        clinic_id: UUID,
        target_date: date,
    ) -> dict:
        now = datetime.now(UTC)
        # Day window in UTC (start/end).
        day_start = datetime(
            target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=UTC
        )
        day_end = datetime(
            target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=UTC
        )

        pros = await _fetch_professionals(db, clinic_id)
        active = await _fetch_active_treatments(db, clinic_id, day_start, day_end)
        schedule_states = await _fetch_schedule_states(db, clinic_id, [p[0] for p in pros], now)

        professionals_payload = []
        for pid, first_name, last_name in pros:
            if pid in active:
                apt_id, cab_id = active[pid]
                professionals_payload.append(
                    {
                        "id": str(pid),
                        "first_name": first_name,
                        "last_name": last_name,
                        "state": "in_treatment",
                        "current_appointment_id": str(apt_id),
                        "current_cabinet_id": str(cab_id) if cab_id else None,
                    }
                )
                continue
            state = schedule_states.get(pid, "free")
            professionals_payload.append(
                {
                    "id": str(pid),
                    "first_name": first_name,
                    "last_name": last_name,
                    "state": state,
                    "current_appointment_id": None,
                    "current_cabinet_id": None,
                }
            )

        return {
            "date": target_date,
            "clinic_id": str(clinic_id),
            "professionals": professionals_payload,
        }
