"""What this module answers when a patient exercises their rights.

Mediciones periodontales. Cada snapshot cuelga sus dientes y cada diente
sus sitios: sin ellos el export sería una cabecera sin datos, así que la
cadena se recorre entera.

See ``app.core.privacy.subject`` and ADR 0026.
"""

from __future__ import annotations

from app.core.privacy import ChildLink, SubjectContributor, patient_keyed_export

from .models import PeriodontogramSite, PeriodontogramSnapshot, PeriodontogramTooth

CLINICAL_RETENTION = (
    "El historial clínico se conserva: la normativa sanitaria fija un "
    "plazo de conservación que no cede ante una solicitud de supresión. "
    "Los datos dejan de identificar al paciente cuando se anonimiza su "
    "ficha de identidad, no borrando el registro asistencial."
)


def get_subject_contributors() -> list[SubjectContributor]:
    return [
        SubjectContributor(
            name="periodontal_charts",
            export=patient_keyed_export(
                PeriodontogramSnapshot,
                ChildLink(PeriodontogramTooth, "snapshot_id"),
                ChildLink(PeriodontogramSite, "tooth_id"),
            ),
            retention_reason=CLINICAL_RETENTION,
        ),
    ]
