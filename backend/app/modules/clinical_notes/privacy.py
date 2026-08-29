"""What this module answers when a patient exercises their rights.

Notas clínicas y administrativas. Registro asistencial: se conservan.

**Hueco conocido.** Este módulo enlaza por ``owner_type`` / ``owner_id``
(ADR 0007), no por ``patient_id``. Una nota cuyo owner es el paciente se
encuentra; una nota colgada de una *cita* o de un *plan de tratamiento*
de ese mismo paciente no, porque resolver esos owners exigiría que este
módulo importara ``agenda`` o ``treatment_plan``, que es justo lo que
ADR 0001 prohíbe. El export queda incompleto en ese caso y conviene
saberlo antes de entregárselo a nadie.

See ``app.core.privacy.subject`` and ADR 0026.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.privacy import SubjectContributor, row_to_dict

from .models import ClinicalNote

CLINICAL_RETENTION = (
    "El historial clínico se conserva: la normativa sanitaria fija un "
    "plazo de conservación que no cede ante una solicitud de supresión. "
    "Los datos dejan de identificar al paciente cuando se anonimiza su "
    "ficha de identidad, no borrando el registro asistencial."
)


async def _export_notes(
    db: AsyncSession, clinic_id: UUID, patient_id: UUID
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(ClinicalNote).where(
            ClinicalNote.clinic_id == clinic_id,
            ClinicalNote.owner_type == "patient",
            ClinicalNote.owner_id == patient_id,
        )
    )
    return [row_to_dict(note) for note in result.scalars().all()]


def get_subject_contributors() -> list[SubjectContributor]:
    return [
        SubjectContributor(
            name="notes",
            export=_export_notes,
            retention_reason=CLINICAL_RETENTION,
        ),
    ]
