"""What this module answers when a patient exercises their rights.

La timeline es un **índice derivado**: cada fila resume un hecho que ya
vive en el módulo que lo produjo. Nada obliga a conservarla y borrarla no
pierde información — por eso este módulo sí borra.

``description`` es texto ya renderizado ("Cita con Ana García el 3 de
marzo"), así que lleva el nombre dentro aunque la columna no esté
clasificada. Se va con la supresión.

See ``app.core.privacy.subject`` and ADR 0026.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.privacy import SubjectContributor, patient_keyed_export

from .models import PatientTimeline

_export = patient_keyed_export(PatientTimeline)


async def _anonymize(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> int:
    result = await db.execute(
        select(PatientTimeline).where(
            PatientTimeline.clinic_id == clinic_id,
            PatientTimeline.patient_id == patient_id,
        )
    )
    scrubbed = 0
    for entry in result.scalars().all():
        if entry.description is not None:
            entry.description = None
            scrubbed += 1
    return scrubbed


def get_subject_contributors() -> list[SubjectContributor]:
    return [
        SubjectContributor(name="timeline", export=_export, anonymize=_anonymize),
    ]
