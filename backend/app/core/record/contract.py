"""What a module returns when asked what of its data belongs in a record."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


class SectionCategory(StrEnum):
    """Where a section sits in a composition.

    The order is the order a record reads in — the shape of a paper
    *expediente*, and of both interchange formats worth targeting later
    (HL7 CDA R2 and FHIR ``Composition``), which is why the internal model is
    built in it: the export formats become mappings rather than rewrites.
    """

    IDENTIFICATION = "identification"
    ANTECEDENTS = "antecedents"
    ODONTOGRAM = "odontogram"
    PERIODONTAL = "periodontal"
    EVOLUTION = "evolution"
    THERAPEUTIC_PLAN = "therapeutic_plan"
    IMAGING = "imaging"
    CONSENTS = "consents"
    DISCLOSURES = "disclosures"


class EntryStatus(StrEnum):
    """Whether an entry is current, over, or should never have been there.

    The three states ADR 0032 settled on, carried up into the composition so a
    reader of the record sees the same distinction the clinical tables keep.
    """

    ACTIVE = "active"
    ENDED = "ended"
    RETRACTED = "retracted"


@dataclass(frozen=True, slots=True)
class RecordEntry:
    """One dated, attributed clinical fact."""

    occurred_at: datetime
    """**Clinical time, not row-creation time.** A surgery recorded today that
    happened in 2019 sorts into 2019. Getting this wrong turns a record into a
    data-entry log, which is not what a colleague is reading it for."""

    summary: str
    """One line, in the clinic's language. What a reader sees first."""

    detail: dict[str, Any] = field(default_factory=dict)
    """The structured fact. Keys are the owning module's own column names, so
    the PII classification on those columns tokenizes them when a redacted
    path is involved (ADR 0025); an invented key is covered by nothing."""

    status: EntryStatus = EntryStatus.ACTIVE
    """Retracted entries are excluded from disclosures by default and never
    silently dropped from the record (ADR 0032)."""

    authored_by_professional_id: UUID | None = None
    """The professional clinically responsible — through whom an exported
    record names a licence. Distinct from the account that typed it, and None
    when the entry predates the rule or was recorded by an account with no
    directory profile."""

    recorded_by_user_id: UUID | None = None
    """The account that operated the software. The audit trail."""

    source_table: str | None = None
    source_id: UUID | None = None
    """Where the fact lives, so a reader can be taken to it and an export can
    prove it was not invented here."""

    codes: list[dict[str, str]] = field(default_factory=list)
    """Clinical coding — CIE-10, procedure codes. Empty until the coding phase;
    the field exists from the start so adding it is not a migration of every
    section."""


CollectFn = Callable[[AsyncSession, UUID, UUID], Awaitable[list[RecordEntry]]]
"""``(db, clinic_id, patient_id)`` -> this section's entries for that patient."""


@dataclass(frozen=True, slots=True)
class RecordSection:
    """One module's answer about one part of a patient's clinical record."""

    name: str
    """Unprefixed, e.g. ``"allergies"``. The registry adds the module name, so
    two modules can both have an ``imaging`` section without colliding."""

    title_key: str
    """An i18n key, never a literal. A record is read in the clinic's language
    and exported in the patient's; a Spanish string baked in here would be
    wrong in both places the moment either changes."""

    category: SectionCategory
    collect: CollectFn

    order: int = 0
    """Tie-break within a category. Two modules contributing antecedents
    should not depend on registry iteration order to decide which reads first."""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("RecordSection name cannot be empty")
        if not self.title_key:
            raise ValueError(
                f"RecordSection {self.name!r} needs a title_key: a record is "
                "read in one language and exported in another"
            )
