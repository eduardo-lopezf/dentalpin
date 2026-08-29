"""What this module answers when a patient exercises their rights.

Citas y lo que se registró en ellas: los tratamientos aplicados y el
rastro de cambios de estado y de gabinete. Forman parte del registro
asistencial — cuándo se atendió al paciente y qué se le hizo — así que se
conservan, y dejan de identificarle al anonimizar su ficha.

See ``app.core.privacy.subject`` and ADR 0026.
"""

from __future__ import annotations

from app.core.privacy import ChildLink, SubjectContributor, patient_keyed_export

from .models import (
    Appointment,
    AppointmentCabinetEvent,
    AppointmentStatusEvent,
    AppointmentTreatment,
)

CLINICAL_RETENTION = (
    "El historial clínico se conserva: la normativa sanitaria fija un "
    "plazo de conservación que no cede ante una solicitud de supresión. "
    "Los datos dejan de identificar al paciente cuando se anonimiza su "
    "ficha de identidad, no borrando el registro asistencial."
)


def get_subject_contributors() -> list[SubjectContributor]:
    return [
        SubjectContributor(
            name="appointments",
            export=patient_keyed_export(
                Appointment,
                ChildLink(AppointmentTreatment, "appointment_id"),
                ChildLink(AppointmentStatusEvent, "appointment_id"),
                ChildLink(AppointmentCabinetEvent, "appointment_id"),
            ),
            retention_reason=CLINICAL_RETENTION,
        ),
    ]
