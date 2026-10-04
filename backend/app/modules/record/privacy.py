"""What this module answers when a patient exercises their rights.

The record owns no clinical data, but it does own the evidence of every
time the record was handed over. A patient may know who received it; the
clinic may not erase that it happened.

See ``app.core.privacy.subject`` and ADR 0026.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.privacy import SubjectContributor

from .models import Disclosure

DISCLOSURE_RETENTION = (
    "El registro de cada entrega del expediente —a quién, por qué y qué contenía— "
    "es la constancia de la clínica y parte del propio expediente: se conserva "
    "durante el plazo que fija la normativa sanitaria."
)


async def _export(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> list[dict[str, Any]]:
    result = await db.execute(
        select(Disclosure).where(
            Disclosure.clinic_id == clinic_id, Disclosure.patient_id == patient_id
        )
    )
    # The document itself is the record the patient is already receiving.
    return [
        {
            "id": row.id,
            "purpose": row.purpose,
            "recipient_name": row.recipient_name,
            "evidence": row.evidence,
            "scope": row.scope,
            "document_sha256": row.document_sha256,
            "created_at": row.created_at,
        }
        for row in result.scalars()
    ]


def get_subject_contributors() -> list[SubjectContributor]:
    return [
        SubjectContributor(
            name="disclosures", export=_export, retention_reason=DISCLOSURE_RETENTION
        )
    ]
