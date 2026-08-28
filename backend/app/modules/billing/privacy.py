"""What this module answers when a patient exercises their rights.

Billing is the section that **refuses erasure**, and it is here to make
that refusal explicit rather than accidental. An issued invoice is a
fiscal document: its retention is set by tax law, which does not yield to
a data-protection request, and in Spain `verifactu` has already declared
it to the AEAT. Scrubbing the name off it would not protect the patient —
it would break a record the clinic is required to be able to produce.

So this module exports (portability has no such exception) and declines
to anonymize, stating why. The classification carries the same rule from
the other end: `anonymize_instance` skips `DataClass.FINANCIAL` columns,
so even a caller that reached these rows by another path would leave the
billing identity intact.

See ``app.core.privacy.subject`` and ADR 0026.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.privacy import SubjectContributor

from .models import Invoice

RETENTION_REASON = (
    "Las facturas emitidas son documentos fiscales: su conservación la fija la "
    "normativa tributaria, que no cede ante una solicitud de supresión. Los datos "
    "de facturación se conservan durante el plazo legal aplicable."
)


async def _export_invoices(
    db: AsyncSession, clinic_id: UUID, patient_id: UUID
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(Invoice)
        .where(Invoice.clinic_id == clinic_id, Invoice.patient_id == patient_id)
        .order_by(Invoice.created_at)
    )
    return [
        {
            column.key: getattr(invoice, column.key)
            for column in Invoice.__table__.columns
            if column.key != "clinic_id"
        }
        for invoice in result.scalars().all()
    ]


def get_subject_contributors() -> list[SubjectContributor]:
    return [
        SubjectContributor(
            name="invoices",
            export=_export_invoices,
            retention_reason=RETENTION_REASON,
        )
    ]
