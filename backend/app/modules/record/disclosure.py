"""Handing a record over, and keeping the evidence that it was.

The one place a clinical record is turned into a document that can leave
the clinic (ADR 0033, ADR 0029): :meth:`DisclosureService.disclose`. It
takes the purpose, the recipient and the scope, refuses when the evidence
the purpose asks for is missing, renders exactly the sections in scope,
and stores the document with its digest and a manifest of what went in.
There is no other path to a printable record — `render_record_pdf` is
called from here and nowhere else, and
`tests/test_record_disclosure.py` keeps it that way.
"""

from __future__ import annotations

import hashlib
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.core.contracts import ProfessionalDirectory, provider

from .models import Disclosure
from .pdf import render_record_pdf
from .service import ComposedRecord, RecordService


class DisclosureError(ValueError):
    """The disclosure cannot be made as asked (maps to 400)."""


def _require_evidence(data: dict) -> None:
    """The purpose decides what has to be on file before anything leaves."""
    purpose, evidence = data["purpose"], (data.get("evidence") or "").strip()
    if purpose == "patient_copy":
        # The patient is the subject; what is owed is knowing it is them.
        if not data.get("identity_verified"):
            raise DisclosureError("A copy for the patient requires verifying who is asking")
        return
    if not evidence:
        raise DisclosureError(
            {
                "continuity_of_care": "A referral needs its clinical justification",
                "authorised_third_party": (
                    "A third party needs the authorisation the patient signed to be described"
                ),
                "legal_requirement": "A legal requirement needs the order to be identified",
            }[purpose]
        )


def _manifest(record: ComposedRecord) -> dict:
    return {
        "composed_at": record.composed_at.isoformat(),
        "sections": [
            {
                "section": section.qualified_name,
                "entries": [
                    {
                        "source_table": entry.source_table,
                        "source_id": str(entry.source_id) if entry.source_id else None,
                        "occurred_at": entry.occurred_at.isoformat(),
                    }
                    for entry in section.entries
                ],
            }
            for section in record.sections
        ],
    }


class DisclosureService:
    @staticmethod
    async def disclose(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID, user_id: UUID, data: dict
    ) -> Disclosure | None:
        """Produce the document and the record of having produced it.

        ``None`` when the patient is not in this clinic. Retracted entries
        are never disclosed (ADR 0032).
        """
        _require_evidence(data)
        record = await RecordService.compose(db, clinic_id, patient_id)
        if record is None:
            return None

        # Scope is enforced, not advisory: a section that does not exist is
        # a refusal, and what is not asked for is not rendered.
        known = {section.qualified_name for section in record.sections}
        unknown = [name for name in data["scope"] if name not in known]
        if unknown:
            raise DisclosureError(f"Unknown record sections: {', '.join(unknown)}")
        wanted = set(data["scope"])
        scoped = ComposedRecord(
            patient_id=record.patient_id,
            clinic_id=record.clinic_id,
            composed_at=record.composed_at,
            sections=[s for s in record.sections if s.qualified_name in wanted],
            professionals=record.professionals,
        )
        if not any(section.entries for section in scoped.sections):
            raise DisclosureError("Nothing to disclose in the sections chosen")

        directory = provider(ProfessionalDirectory)
        professional_id = await directory.for_account(db, clinic_id, user_id) if directory else None
        professional = (
            (await directory.briefs(db, clinic_id, [professional_id])).get(professional_id)
            if directory and professional_id
            else None
        )

        disclosure = Disclosure(
            clinic_id=clinic_id,
            patient_id=patient_id,
            purpose=data["purpose"],
            recipient_name=data["recipient_name"].strip(),
            evidence=(data.get("evidence") or "").strip() or None,
            identity_verified=bool(data.get("identity_verified")),
            scope=[s.qualified_name for s in scoped.sections],
            manifest=_manifest(scoped),
            locale=data.get("locale", "es"),
            disclosed_by_user_id=user_id,
            disclosed_by_professional_id=professional_id,
        )
        # The id is printed on the document, so it exists before rendering.
        db.add(disclosure)
        disclosure.document = b""
        disclosure.document_sha256 = ""
        await db.flush()

        document = await render_record_pdf(db, scoped, disclosure, professional)
        disclosure.document = document
        disclosure.document_sha256 = hashlib.sha256(document).hexdigest()
        await db.flush()
        return disclosure

    @staticmethod
    async def list_for_patient(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID
    ) -> list[Disclosure]:
        result = await db.execute(
            select(Disclosure)
            .where(Disclosure.clinic_id == clinic_id, Disclosure.patient_id == patient_id)
            .order_by(Disclosure.created_at.desc())
        )
        return list(result.scalars())

    @staticmethod
    async def get(
        db: AsyncSession, clinic_id: UUID, disclosure_id: UUID, *, with_document: bool = False
    ) -> Disclosure | None:
        query = select(Disclosure).where(
            Disclosure.id == disclosure_id, Disclosure.clinic_id == clinic_id
        )
        if with_document:
            query = query.options(undefer(Disclosure.document))
        return (await db.execute(query)).scalar_one_or_none()
