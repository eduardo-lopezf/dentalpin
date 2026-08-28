"""What this module answers when a patient exercises their rights.

See ``app.core.privacy.subject`` and ADR 0026. The identity row is the
one section that always exists, so it is also the one whose absence would
be most obviously wrong in an export.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.privacy import SubjectContributor, anonymize_instance

from .models import Patient

# Columns that are not personal but are worth having in an export: they
# are what lets a patient (or their lawyer) check the record is theirs
# and current.
_CONTEXT_COLUMNS = ("id", "status", "created_at", "updated_at")


async def _export_identity(
    db: AsyncSession, clinic_id: UUID, patient_id: UUID
) -> list[dict[str, Any]]:
    patient = (
        await db.execute(
            select(Patient).where(Patient.clinic_id == clinic_id, Patient.id == patient_id)
        )
    ).scalar_one_or_none()
    if patient is None:
        return []

    row: dict[str, Any] = {}
    for column in Patient.__table__.columns:
        if column.key in _CONTEXT_COLUMNS or column.info.get("pii") is not None:
            row[column.key] = getattr(patient, column.key)
    # Demographics that are personal without being classified: they
    # identify nobody on their own, and a portability export that omitted
    # them would be incomplete.
    for key in ("date_of_birth", "gender", "national_id_type", "address", "profession"):
        row[key] = getattr(patient, key)
    return [row]


async def _anonymize_identity(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> int:
    patient = (
        await db.execute(
            select(Patient).where(Patient.clinic_id == clinic_id, Patient.id == patient_id)
        )
    ).scalar_one_or_none()
    if patient is None:
        return 0

    scrubbed = anonymize_instance(patient)
    # Not classified as PII (a date is not an identifier on its own) but
    # a quasi-identifier that re-identifies a person when combined with
    # the rest of a clinical record, so it goes with the erasure.
    if patient.date_of_birth is not None:
        patient.date_of_birth = None
        scrubbed += 1
    if patient.address is not None:
        patient.address = None
        scrubbed += 1
    # The row itself survives: appointments, invoices and clinical notes
    # reference it, and deleting it would break records that must be
    # kept. Archiving is what marks it as no longer in use.
    patient.status = "archived"
    return scrubbed


def get_subject_contributors() -> list[SubjectContributor]:
    return [
        SubjectContributor(
            name="identity",
            export=_export_identity,
            anonymize=_anonymize_identity,
        )
    ]
