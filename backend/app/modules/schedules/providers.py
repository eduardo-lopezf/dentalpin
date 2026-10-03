"""What schedules offers other modules without being imported (ADR 0039)."""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .services.availability import AvailabilityService


class SchedulesWorkingHours:
    async def professional_states(
        self,
        db: AsyncSession,
        clinic_id: UUID,
        professional_ids: Collection[UUID],
        at: datetime,
    ) -> dict[UUID, str]:
        day = at.date()
        out: dict[UUID, str] = {}
        for pid in professional_ids:
            try:
                _, ranges = await AvailabilityService.resolve(
                    db, clinic_id, day, day, professional_id=pid
                )
            except Exception:
                continue

            # Find the range containing ``at``. Inside an "open" range the
            # professional is working and is left out; "closed" with open
            # hours elsewhere today is a break; otherwise off.
            state = "off"
            any_open_today = any(r.state == "open" for r in ranges)
            for r in ranges:
                if r.start <= at <= r.end:
                    if r.state == "open":
                        state = "free"
                    elif r.state == "closed" and any_open_today:
                        state = "on_break"
                    else:
                        state = "off"
                    break
            if state != "free":
                out[pid] = state
        return out


working_hours = SchedulesWorkingHours()
