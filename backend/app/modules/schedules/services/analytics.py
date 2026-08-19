"""Occupancy + utilization analytics.

Reads from the agenda module (``appointments``, ``cabinets``) — this is
why ``schedules.depends = ["agenda"]``. The analytics endpoints are the
only place the schedules module touches agenda code, and the direction
is deliberately one-way: agenda never imports from schedules.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agenda.models import Appointment, Cabinet
from app.modules.professionals.models import Professional

from .availability import AvailabilityService


class AnalyticsService:
    @staticmethod
    async def occupancy(
        db: AsyncSession,
        clinic_id: UUID,
        start: date,
        end: date,
        cabinet_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        tz_name, ranges = await AvailabilityService.resolve(db, clinic_id, start, end)
        tz = ZoneInfo(tz_name)
        available_minutes = sum(
            int((r.end - r.start).total_seconds() / 60) for r in ranges if r.state == "open"
        )

        query = (
            select(
                Cabinet.id,
                Cabinet.name,
                func.coalesce(
                    func.sum(
                        func.extract("epoch", Appointment.end_time - Appointment.start_time) / 60
                    ),
                    0,
                ).label("booked_minutes"),
            )
            .select_from(Cabinet)
            .join(
                Appointment,
                (Appointment.cabinet_id == Cabinet.id)
                & (Appointment.status != "cancelled")
                & (Appointment.start_time >= _bound(start, "lo", tz))
                & (Appointment.start_time <= _bound(end, "hi", tz)),
                isouter=True,
            )
            .where(Cabinet.clinic_id == clinic_id)
            .group_by(Cabinet.id, Cabinet.name)
            .order_by(Cabinet.name)
        )
        if cabinet_id is not None:
            query = query.where(Cabinet.id == cabinet_id)

        result = await db.execute(query)
        rows: list[dict[str, Any]] = []
        for row in result.all():
            booked = int(row.booked_minutes or 0)
            rate = (booked / available_minutes) if available_minutes else 0.0
            rows.append(
                {
                    "cabinet_id": row.id,
                    "cabinet_name": row.name,
                    "booked_minutes": booked,
                    "available_minutes": available_minutes,
                    "occupancy_rate": min(rate, 1.0),
                }
            )
        return rows

    @staticmethod
    async def utilization(
        db: AsyncSession,
        clinic_id: UUID,
        start: date,
        end: date,
        professional_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        professionals_query = (
            select(Professional.id, Professional.first_name, Professional.last_name)
            .where(
                Professional.clinic_id == clinic_id,
                Professional.is_active.is_(True),
                Professional.professional_type.in_(["dentist", "hygienist"]),
            )
            .order_by(Professional.last_name, Professional.first_name)
        )
        if professional_id is not None:
            professionals_query = professionals_query.where(Professional.id == professional_id)
        professionals = (await db.execute(professionals_query)).all()
        if not professionals:
            return []

        tz_name, _ = await AvailabilityService.resolve(db, clinic_id, start, end)
        tz = ZoneInfo(tz_name)
        result_rows: list[dict[str, Any]] = []
        for professional in professionals:
            _, ranges = await AvailabilityService.resolve(db, clinic_id, start, end, professional.id)
            working_minutes = sum(
                int((r.end - r.start).total_seconds() / 60) for r in ranges if r.state == "open"
            )

            booked = (
                await db.execute(
                    select(
                        func.coalesce(
                            func.sum(
                                func.extract(
                                    "epoch",
                                    Appointment.end_time - Appointment.start_time,
                                )
                                / 60
                            ),
                            0,
                        )
                    ).where(
                        Appointment.clinic_id == clinic_id,
                        Appointment.professional_id == professional.id,
                        Appointment.status != "cancelled",
                        Appointment.start_time >= _bound(start, "lo", tz),
                        Appointment.start_time <= _bound(end, "hi", tz),
                    )
                )
            ).scalar() or 0
            booked = int(booked)
            rate = (booked / working_minutes) if working_minutes else 0.0
            result_rows.append(
                {
                    "professional_id": professional.id,
                    "professional_name": (
                        f"{professional.first_name} {professional.last_name}".strip()
                    ),
                    "booked_minutes": booked,
                    "working_minutes": working_minutes,
                    "utilization_rate": min(rate, 1.0),
                }
            )
        return result_rows

    @staticmethod
    async def peak_hours(
        db: AsyncSession, clinic_id: UUID, start: date, end: date
    ) -> list[dict[str, int]]:
        tz_name = await _tz_name(db, clinic_id)
        tz = ZoneInfo(tz_name)

        query = (
            select(
                func.extract("hour", Appointment.start_time.op("AT TIME ZONE")(tz_name)).label(
                    "hour"
                ),
                func.count().label("count"),
            )
            .where(
                Appointment.clinic_id == clinic_id,
                Appointment.status != "cancelled",
                Appointment.start_time >= _bound(start, "lo", tz),
                Appointment.start_time <= _bound(end, "hi", tz),
            )
            .group_by("hour")
            .order_by("hour")
        )
        result = await db.execute(query)
        return [
            {"hour": int(row.hour), "appointment_count": int(row.count)} for row in result.all()
        ]


async def _tz_name(db: AsyncSession, clinic_id: UUID) -> str:
    from .clinic_hours import ClinicHoursService

    return await ClinicHoursService.get_clinic_timezone(db, clinic_id)


def _bound(day: date, side: str, tz: ZoneInfo) -> datetime:
    if side == "lo":
        return datetime.combine(day, time(0, 0), tzinfo=tz)
    return datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=tz)
