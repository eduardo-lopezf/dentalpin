"""What this module answers when a patient exercises their rights.

Los registros de facturación declarados a la AEAT. No enlazan con el
paciente: enlazan con la factura, y es ``billing`` —declarado en
``manifest.depends``— quien sabe de quién es cada una.

``xml_payload`` es el asiento tal como se envió, con el nombre y el NIF
del destinatario dentro. Es exactamente por eso que aparece en el export:
un paciente que pide copia de sus datos tiene derecho a ver lo que se
declaró sobre él. Y es exactamente por eso que **no se borra**: un
registro remitido a la Agencia Tributaria no se puede reescribir a
posteriori sin romper la cadena de huellas que lo encadena al siguiente.

See ``app.core.privacy.subject`` and ADR 0026.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.privacy import SubjectContributor, row_to_dict
from app.modules.billing.models import Invoice

from .models import VerifactuRecord

AEAT_RETENTION = (
    "Los registros de facturación remitidos a la AEAT forman una cadena "
    "encadenada por huella: alterarlos o suprimirlos rompería la "
    "integridad del sistema de facturación verificable. Se conservan "
    "durante el plazo que fija la normativa tributaria."
)


async def _export_records(
    db: AsyncSession, clinic_id: UUID, patient_id: UUID
) -> list[dict[str, Any]]:
    invoice_ids = (
        (
            await db.execute(
                select(Invoice.id).where(
                    Invoice.clinic_id == clinic_id, Invoice.patient_id == patient_id
                )
            )
        )
        .scalars()
        .all()
    )
    if not invoice_ids:
        return []
    result = await db.execute(
        select(VerifactuRecord).where(VerifactuRecord.invoice_id.in_(invoice_ids))
    )
    return [row_to_dict(record) for record in result.scalars().all()]


def get_subject_contributors() -> list[SubjectContributor]:
    return [
        SubjectContributor(
            name="aeat_records",
            export=_export_records,
            retention_reason=AEAT_RETENTION,
        ),
    ]
