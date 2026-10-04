"""What this module contributes to a clinical record: the consent letters.

NOM-004 expects the *cartas de consentimiento informado* to live in the
record, so every consent that became a fact about the patient is an entry:
signed ones, the ones the patient declined, and the ones later revoked.
Drafts and discarded drafts never bound anybody and are left out.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.record import EntryStatus, RecordEntry, RecordSection, SectionCategory

from .models import Consent

_IN_THE_RECORD = ("signed", "declined", "revoked")


async def _collect(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> list[RecordEntry]:
    result = await db.execute(
        select(Consent).where(
            Consent.clinic_id == clinic_id,
            Consent.patient_id == patient_id,
            Consent.status.in_(_IN_THE_RECORD),
        )
    )
    return [
        RecordEntry(
            occurred_at=row.signed_at or row.declined_at or row.created_at,
            summary=row.title,
            detail={
                "kind": row.kind,
                "status": row.status,
                "procedure_label": row.procedure_label,
                "explained_by_name": row.explained_by_name,
                "explained_by_license": row.explained_by_license,
                "signed_by_name": row.signed_by_name,
                "signer_capacity": row.signer_capacity,
                "signature_method": row.signature_method,
                "scan_document_id": (row.signature_data or {}).get("document_id"),
                "signed_at": row.signed_at,
                "declined_at": row.declined_at,
                "revoked_at": row.revoked_at,
            },
            # A revoked consent was true and stopped being so — "ended", not
            # "should never have existed".
            status=EntryStatus.ENDED if row.status == "revoked" else EntryStatus.ACTIVE,
            authored_by_professional_id=row.explained_by_professional_id,
            recorded_by_user_id=row.recorded_by_user_id,
            source_table="consents_consent",
            source_id=row.id,
        )
        for row in result.scalars()
    ]


def get_record_sections() -> list[RecordSection]:
    return [
        RecordSection(
            name="consents",
            title_key="record.section.consents",
            category=SectionCategory.CONSENTS,
            collect=_collect,
            order=10,
        )
    ]
