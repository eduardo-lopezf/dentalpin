"""What agenda offers other modules without being imported (ADR 0039)."""

from __future__ import annotations

from collections.abc import Collection
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contracts import VisitNote

from .models import Appointment, AppointmentTreatment


class AgendaAppointmentBook:
    async def patients_of(
        self, db: AsyncSession, clinic_id: UUID, appointment_ids: Collection[UUID]
    ) -> dict[UUID, UUID | None]:
        if not appointment_ids:
            return {}
        result = await db.execute(
            select(Appointment.id, Appointment.patient_id).where(
                Appointment.clinic_id == clinic_id, Appointment.id.in_(appointment_ids)
            )
        )
        return {row.id: row.patient_id for row in result.all()}

    async def ids_for_patient(
        self, db: AsyncSession, clinic_id: UUID, patient_id: UUID
    ) -> list[UUID]:
        result = await db.execute(
            select(Appointment.id).where(
                Appointment.clinic_id == clinic_id, Appointment.patient_id == patient_id
            )
        )
        return list(result.scalars().all())

    async def visit_notes(
        self, db: AsyncSession, clinic_id: UUID, planned_item_ids: Collection[UUID]
    ) -> list[VisitNote]:
        if not planned_item_ids:
            return []
        result = await db.execute(
            select(AppointmentTreatment, Appointment)
            .join(Appointment, AppointmentTreatment.appointment_id == Appointment.id)
            .where(
                AppointmentTreatment.planned_treatment_item_id.in_(planned_item_ids),
                AppointmentTreatment.notes.is_not(None),
                AppointmentTreatment.notes != "",
                Appointment.clinic_id == clinic_id,
            )
        )
        return [
            VisitNote(
                id=visit.id,
                planned_item_id=visit.planned_treatment_item_id,
                body=visit.notes or "",
                professional_id=appointment.professional_id,
                created_at=visit.created_at or appointment.created_at,
            )
            for visit, appointment in result.all()
        ]


appointment_book = AgendaAppointmentBook()
