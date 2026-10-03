"""Turn appointments into the API response.

An appointment row knows the ids of its patient, its professional and
its planned treatments; what those look like belongs to other modules.
This is where the agenda asks for it — once per page, through the core
contracts (ADR 0039) — instead of loading other modules' rows through
ORM relationships.

A link whose App is off is left out, ids included: it stays in the
database and shows again when the App returns (ADR 0037).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contracts import TreatmentLink

from .integrations import patients, planned_treatments, professionals
from .models import Appointment
from .schemas import (
    AppointmentResponse,
    AppointmentTreatmentBrief,
    PatientBrief,
    ProfessionalBrief,
)


async def present(
    db: AsyncSession, clinic_id: UUID, appointments: Sequence[Appointment]
) -> list[AppointmentResponse]:
    """``appointments`` must have ``treatments`` loaded."""
    patient_directory = patients()
    professional_directory = professionals()
    treatment_provider = planned_treatments()

    patient_briefs = (
        await patient_directory.briefs(
            db, clinic_id, {a.patient_id for a in appointments if a.patient_id}
        )
        if patient_directory
        else {}
    )
    professional_briefs = (
        await professional_directory.briefs(
            db, clinic_id, {a.professional_id for a in appointments if a.professional_id}
        )
        if professional_directory
        else {}
    )
    treatment_briefs = (
        await treatment_provider.briefs(
            db,
            clinic_id,
            [
                TreatmentLink(
                    id=link.id,
                    planned_item_id=link.planned_treatment_item_id,
                    catalog_item_id=link.catalog_item_id,
                )
                for appointment in appointments
                for link in appointment.treatments
            ],
        )
        if treatment_provider
        else {}
    )

    responses: list[AppointmentResponse] = []
    for a in appointments:
        patient = patient_briefs.get(a.patient_id) if a.patient_id else None
        professional = professional_briefs.get(a.professional_id) if a.professional_id else None
        responses.append(
            AppointmentResponse(
                id=a.id,
                clinic_id=a.clinic_id,
                patient_id=a.patient_id if patient_directory else None,
                professional_id=a.professional_id if professional_directory else None,
                title=a.title,
                cabinet=a.cabinet,
                cabinet_id=a.cabinet_id,
                cabinet_assigned_at=a.cabinet_assigned_at,
                cabinet_assigned_by=a.cabinet_assigned_by,
                start_time=a.start_time,
                end_time=a.end_time,
                treatment_type=a.treatment_type,
                status=a.status,
                current_status_since=a.current_status_since,
                color=a.color,
                created_at=a.created_at,
                updated_at=a.updated_at,
                patient=PatientBrief.model_validate(patient) if patient else None,
                professional=(
                    ProfessionalBrief.model_validate(professional) if professional else None
                ),
                treatments=[
                    AppointmentTreatmentBrief(
                        id=link.id,
                        planned_item_id=link.planned_treatment_item_id,
                        completed_in_appointment=link.completed_in_appointment,
                        **asdict(treatment_briefs[link.id]),
                    )
                    for link in a.treatments
                    if link.id in treatment_briefs
                ],
            )
        )
    return responses


async def present_one(db: AsyncSession, appointment: Appointment) -> AppointmentResponse:
    return (await present(db, appointment.clinic_id, [appointment]))[0]
