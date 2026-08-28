"""What this module answers when a patient exercises their rights.

Recordatorios de revisión y los intentos de contacto. Es actividad de
seguimiento comercial, no registro asistencial ni contable: nada obliga a
conservarla, así que se borra entera.

Las notas libres (``reason_note``, la nota de cada intento) son el sitio
donde una recepcionista escribe cosas como "no contesta, llamar al móvil
de su hija": texto sobre personas que ninguna clasificación de columna
puede ver, y que se va con la supresión.

See ``app.core.privacy.subject`` and ADR 0026.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.privacy import ChildLink, SubjectContributor, patient_keyed_export

from .models import Recall, RecallContactAttempt

_LINKS = (ChildLink(RecallContactAttempt, "recall_id"),)
_export = patient_keyed_export(Recall, *_LINKS)


async def _anonymize(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> int:
    scrubbed = 0
    recalls = (
        (
            await db.execute(
                select(Recall).where(Recall.clinic_id == clinic_id, Recall.patient_id == patient_id)
            )
        )
        .scalars()
        .all()
    )
    for recall in recalls:
        if recall.reason_note is not None:
            recall.reason_note = None
            scrubbed += 1
    if recalls:
        attempts = (
            (
                await db.execute(
                    select(RecallContactAttempt).where(
                        RecallContactAttempt.recall_id.in_([r.id for r in recalls])
                    )
                )
            )
            .scalars()
            .all()
        )
        for attempt in attempts:
            if attempt.note is not None:
                attempt.note = None
                scrubbed += 1
    return scrubbed


def get_subject_contributors() -> list[SubjectContributor]:
    return [
        SubjectContributor(name="recalls", export=_export, anonymize=_anonymize),
    ]
