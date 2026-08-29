"""What this module answers when a patient exercises their rights.

El punto ciego más fácil de olvidar: ``migration_import_raw_entities``
guarda el registro **tal como venía del sistema de origen**, en JSON. Ahí
está el nombre, el teléfono y el documento del paciente en crudo, y no
hay ninguna columna ``patient_id`` que lo delate — el enlace pasa por
``migration_import_entity_mappings``, que traduce el identificador
canónico del origen al id de DentalPin.

Un export que ignorara esta tabla devolvería la ficha migrada del
paciente y dejaría fuera la copia literal de la que salió. Una supresión
que la ignorara dejaría esa copia intacta.

Por eso este módulo **sí borra**: el staging de una migración ya
ejecutada no es registro asistencial ni contable, es material de
trabajo.

See ``app.core.privacy.subject`` and ADR 0026.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.privacy import SubjectContributor, row_to_dict

from .models import EntityMapping, RawEntity


async def _canonical_uuids(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> list[str]:
    result = await db.execute(
        select(EntityMapping.source_canonical_uuid).where(
            EntityMapping.clinic_id == clinic_id,
            EntityMapping.entity_type == "patient",
            EntityMapping.dentalpin_id == patient_id,
        )
    )
    return list(result.scalars().all())


async def _raw_rows(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> list[RawEntity]:
    canonical = await _canonical_uuids(db, clinic_id, patient_id)
    if not canonical:
        return []
    result = await db.execute(
        select(RawEntity).where(
            RawEntity.clinic_id == clinic_id,
            RawEntity.canonical_uuid.in_(canonical),
        )
    )
    return list(result.scalars().all())


async def _export_raw(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> list[dict[str, Any]]:
    return [row_to_dict(row) for row in await _raw_rows(db, clinic_id, patient_id)]


async def _anonymize_raw(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> int:
    scrubbed = 0
    for row in await _raw_rows(db, clinic_id, patient_id):
        # Both blobs: ``payload`` is the normalised parse, ``raw_source_data``
        # the untouched original. Clearing one and not the other would
        # leave the copy that is hardest to notice.
        if row.payload:
            row.payload = {}
            scrubbed += 1
        if row.raw_source_data:
            row.raw_source_data = {}
            scrubbed += 1
    return scrubbed


def get_subject_contributors() -> list[SubjectContributor]:
    return [
        SubjectContributor(
            name="source_records",
            export=_export_raw,
            anonymize=_anonymize_raw,
        ),
    ]
