"""What this module answers when a patient exercises their rights.

Planes de tratamiento, sus partidas, las sesiones de cada partida y las
recetas escritas desde ellas.
Documento asistencial: recoge diagnóstico y decisiones clínicas.

See ``app.core.privacy.subject`` and ADR 0026.
"""

from __future__ import annotations

from app.core.privacy import ChildLink, SubjectContributor, patient_keyed_export

from .models import (
    PlannedTreatmentItem,
    PlannedTreatmentItemSession,
    TreatmentPlan,
    TreatmentPrescription,
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
            name="treatment_plans",
            export=patient_keyed_export(
                TreatmentPlan,
                ChildLink(PlannedTreatmentItem, "treatment_plan_id"),
                ChildLink(PlannedTreatmentItemSession, "plan_item_id"),
            ),
            retention_reason=CLINICAL_RETENTION,
        ),
        SubjectContributor(
            name="treatment_prescriptions",
            export=patient_keyed_export(TreatmentPrescription),
            retention_reason=CLINICAL_RETENTION,
        ),
    ]
