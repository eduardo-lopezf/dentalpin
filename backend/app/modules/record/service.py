"""Composing a patient's clinical record out of the installed modules."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.record import EntryStatus, RecordEntry, RecordSection, SectionCategory
from app.modules.patients.models import Patient

logger = logging.getLogger(__name__)

#: Reading order of a composition. The sequence a paper *expediente* follows,
#: and the one both interchange formats expect, so an export is a mapping
#: rather than a rewrite.
CATEGORY_ORDER: tuple[SectionCategory, ...] = (
    SectionCategory.IDENTIFICATION,
    SectionCategory.ANTECEDENTS,
    SectionCategory.ODONTOGRAM,
    SectionCategory.PERIODONTAL,
    SectionCategory.EVOLUTION,
    SectionCategory.THERAPEUTIC_PLAN,
    SectionCategory.IMAGING,
    SectionCategory.CONSENTS,
)


@dataclass(frozen=True, slots=True)
class ComposedSection:
    module: str
    name: str
    title_key: str
    category: SectionCategory
    entries: list[RecordEntry]

    @property
    def qualified_name(self) -> str:
        return f"{self.module}.{self.name}"


@dataclass(frozen=True, slots=True)
class ComposedRecord:
    """A patient's record at one instant: who it is about, and what it says."""

    patient_id: UUID
    clinic_id: UUID
    composed_at: datetime
    sections: list[ComposedSection] = field(default_factory=list)


class RecordService:
    """Fans a record request out over the installed modules."""

    @staticmethod
    def _sections() -> list[tuple[str, RecordSection]]:
        """Every section the installed modules contribute, in reading order.

        ``list_modules()`` is the installed set, not what is on disk
        ([ADR 0018](../../../../docs/adr/0018-install-state-is-the-mount-authority.md)):
        an uninstalled module contributes nothing, and the record is shorter
        rather than broken.
        """
        from app.core.plugins.registry import module_registry

        pairs: list[tuple[str, RecordSection]] = []
        for module in module_registry.list_modules():
            for section in module.get_record_sections():
                pairs.append((module.name, section))

        order = {category: index for index, category in enumerate(CATEGORY_ORDER)}
        pairs.sort(key=lambda pair: (order.get(pair[1].category, len(order)), pair[1].order))
        return pairs

    @classmethod
    async def compose(
        cls,
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        *,
        include_retracted: bool = False,
    ) -> ComposedRecord | None:
        """Build the record of one patient, or None when they are not here.

        Sections come back **even when empty**, the way the subject export
        does: "this module holds nothing about this patient" is an answer,
        while a missing section leaves the reader unable to tell it was asked.

        Retracted entries are left out by default. They are not deleted and
        never were — a record has to stay able to say what the chart said on
        the day of the procedure (ADR 0032) — but an entry that should never
        have been recorded is not part of what a colleague is being handed,
        so asking for it is explicit.
        """
        patient = (
            await db.execute(
                select(Patient).where(
                    Patient.id == patient_id,
                    Patient.clinic_id == clinic_id,
                )
            )
        ).scalar_one_or_none()
        if patient is None:
            return None

        sections: list[ComposedSection] = []
        for module_name, section in cls._sections():
            try:
                entries = await section.collect(db, clinic_id, patient_id)
            except Exception:
                # One module failing must not deny a clinician the rest of the
                # record. It is logged loudly and the section comes back empty
                # rather than absent, so the gap is visible instead of silent.
                logger.exception(
                    "record: section %s.%s failed for patient %s",
                    module_name,
                    section.name,
                    patient_id,
                )
                entries = []

            if not include_retracted:
                entries = [e for e in entries if e.status is not EntryStatus.RETRACTED]

            entries.sort(key=lambda entry: entry.occurred_at)
            sections.append(
                ComposedSection(
                    module=module_name,
                    name=section.name,
                    title_key=section.title_key,
                    category=section.category,
                    entries=entries,
                )
            )

        return ComposedRecord(
            patient_id=patient_id,
            clinic_id=clinic_id,
            composed_at=datetime.now(tz=None).astimezone(),
            sections=sections,
        )
