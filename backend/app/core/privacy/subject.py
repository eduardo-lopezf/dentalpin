"""Subject rights as a module contract.

A patient asking for a copy of their record, or for it to be erased, is
asking about data spread across every installed module: demographics in
``patients``, history in ``patients_clinical``, appointments in
``agenda``, invoices in ``billing``. Core cannot answer for them — it
does not know their tables, and by ADR 0001 it must not import them.

So each module answers for itself. A module returns
:class:`SubjectContributor` objects from ``get_subject_contributors()``,
and :class:`SubjectDataService` fans a request out over the modules
``core_module.state`` says are installed (ADR 0018).

**Erasure is not the default and not always legal.** A contributor that
cannot delete its data says so with ``retention_reason`` instead of
supplying an ``anonymize`` callable — an invoice cannot be erased on
request because fiscal law outlives data-protection law. Making that an
explicit, required declaration is the point: a module cannot stay silent
about whether its data is erasable.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from .classification import DataClass, PiiTag

logger = logging.getLogger(__name__)

ExportFn = Callable[[AsyncSession, UUID, UUID], Awaitable[list[dict[str, Any]]]]
"""``(db, clinic_id, patient_id)`` -> the rows this contributor holds."""

AnonymizeFn = Callable[[AsyncSession, UUID, UUID], Awaitable[int]]
"""``(db, clinic_id, patient_id)`` -> how many rows it scrubbed."""

ANONYMIZED = "[anonimizado]"
"""Placeholder for a classified column that cannot be set to NULL."""


@dataclass(frozen=True, slots=True)
class SubjectContributor:
    """One module's answer about one kind of data it holds on a patient.

    A module returns several — one per coherent section of its data —
    because an export reads better as named sections than as one blob,
    and because erasability is decided per section: a clinic's notes may
    be erasable while its invoices are not.
    """

    name: str
    """Section name in the export document, e.g. ``"clinical_history"``.
    The module prefix is added by the registry, so it stays unprefixed
    here — the same convention as permissions (ADR 0005)."""

    export: ExportFn
    """Required. Every module must be able to hand back what it holds;
    portability has no legal exception the way erasure does."""

    anonymize: AnonymizeFn | None = None
    """``None`` when this data cannot be erased on request. Set
    ``retention_reason`` instead."""

    retention_reason: str | None = None
    """Why erasure is refused, in words a clinic can pass to a patient.
    Required when ``anonymize`` is ``None``, forbidden otherwise."""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("SubjectContributor.name cannot be empty")
        if self.anonymize is None and not self.retention_reason:
            raise ValueError(
                f"SubjectContributor {self.name!r} supplies no anonymize callable, so it must "
                "state a retention_reason — silence about erasability is not an option"
            )
        if self.anonymize is not None and self.retention_reason:
            raise ValueError(
                f"SubjectContributor {self.name!r} both anonymizes and claims a "
                "retention_reason; it can only be one"
            )

    @property
    def erasable(self) -> bool:
        return self.anonymize is not None


@dataclass(frozen=True, slots=True)
class SubjectSection:
    """One contributor's answer, tagged with where it came from."""

    module: str
    section: str
    rows: list[dict[str, Any]] = field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        return f"{self.module}.{self.section}"


@dataclass(frozen=True, slots=True)
class RetainedSection:
    """A section that refused erasure, and why."""

    module: str
    section: str
    reason: str

    @property
    def qualified_name(self) -> str:
        return f"{self.module}.{self.section}"


def anonymize_instance(row: DeclarativeBase) -> int:
    """Scrub the classified columns of one row in place.

    Driven by the ``pii()`` classification (ADR 0025), so a module that
    classifies a new column gets it covered here without touching this
    function. ``FINANCIAL`` columns are left intact: they sit on billing
    documents whose retention is fiscal, and erasing them would break the
    record rather than protect the person.

    Returns the number of columns changed. Does not commit.
    """
    table = row.__table__  # type: ignore[attr-defined]
    scrubbed = 0
    for column in table.columns:
        tag = column.info.get("pii")
        if not isinstance(tag, PiiTag) or tag.data_class is DataClass.FINANCIAL:
            continue
        replacement = None if column.nullable else ANONYMIZED
        if getattr(row, column.key) != replacement:
            setattr(row, column.key, replacement)
            scrubbed += 1
    return scrubbed


@dataclass(frozen=True, slots=True)
class ChildLink:
    """A table reached through its parent rather than by ``patient_id``.

    Most modules key their root rows on the patient and hang the detail
    off those: budget items on a budget, periodontal sites on a tooth on
    a snapshot. Those details *are* the record — an export that returned
    the snapshot without its measurements would be a header — so links
    are resolved in order, each step against the ids the previous one
    produced.
    """

    model: type[DeclarativeBase]
    fk: str
    """Attribute on this model holding the parent's id."""


async def _root_ids(
    db: AsyncSession,
    model: type[DeclarativeBase],
    clinic_id: UUID,
    patient_id: UUID,
) -> list[UUID]:
    result = await db.execute(
        select(model.id).where(  # type: ignore[attr-defined]
            model.clinic_id == clinic_id,  # type: ignore[attr-defined]
            model.patient_id == patient_id,  # type: ignore[attr-defined]
        )
    )
    return list(result.scalars().all())


async def _collect(
    db: AsyncSession,
    root: type[DeclarativeBase],
    children: tuple[ChildLink, ...],
    clinic_id: UUID,
    patient_id: UUID,
) -> list[DeclarativeBase]:
    """Root rows for this patient, then each linked table in order."""
    rows: list[DeclarativeBase] = []
    result = await db.execute(
        select(root).where(
            root.clinic_id == clinic_id,  # type: ignore[attr-defined]
            root.patient_id == patient_id,  # type: ignore[attr-defined]
        )
    )
    parents = list(result.scalars().all())
    rows.extend(parents)

    parent_ids = [row.id for row in parents]  # type: ignore[attr-defined]
    for link in children:
        if not parent_ids:
            break
        result = await db.execute(
            select(link.model).where(getattr(link.model, link.fk).in_(parent_ids))
        )
        found = list(result.scalars().all())
        rows.extend(found)
        parent_ids = [row.id for row in found]  # type: ignore[attr-defined]
    return rows


def row_to_dict(row: DeclarativeBase) -> dict[str, Any]:
    """One row as a plain dict, tagged with its table.

    ``clinic_id`` is dropped: it identifies the clinic, not the patient,
    and it is the same value on every row of an export.
    """
    table = row.__table__  # type: ignore[attr-defined]
    data: dict[str, Any] = {"record_type": table.name}
    for column in table.columns:
        if column.key != "clinic_id":
            data[column.key] = getattr(row, column.key)
    return data


def patient_keyed_export(root: type[DeclarativeBase], *children: ChildLink) -> ExportFn:
    """Export ``root`` rows for a patient, plus everything hanging off them."""

    async def _export(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> list[dict[str, Any]]:
        rows = await _collect(db, root, children, clinic_id, patient_id)
        return [row_to_dict(row) for row in rows]

    return _export


def patient_keyed_anonymize(root: type[DeclarativeBase], *children: ChildLink) -> AnonymizeFn:
    """Scrub the classified columns of a patient's rows in these tables.

    Returns 0 for a module that classifies none, which is the common and
    correct case: most modules hold clinical facts keyed by
    ``patient_id`` and nothing that identifies anyone on its own. Their
    rows stop identifying a person the moment the identity row is
    scrubbed (ADR 0026).
    """

    async def _anonymize(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> int:
        rows = await _collect(db, root, children, clinic_id, patient_id)
        return sum(anonymize_instance(row) for row in rows)

    return _anonymize


class SubjectDataService:
    """Fans a subject request out over the installed modules."""

    @staticmethod
    def _contributors() -> list[tuple[str, SubjectContributor]]:
        from app.core.plugins.registry import module_registry

        pairs: list[tuple[str, SubjectContributor]] = []
        for module in module_registry.list_modules():
            for contributor in module.get_subject_contributors():
                pairs.append((module.name, contributor))
        return pairs

    @classmethod
    async def export(
        cls, db: AsyncSession, clinic_id: UUID, patient_id: UUID
    ) -> list[SubjectSection]:
        """Everything the installed modules hold on one patient.

        Sections come back even when empty, so the document says "this
        module holds nothing" rather than leaving the reader to wonder
        whether it was asked.
        """
        sections: list[SubjectSection] = []
        for module_name, contributor in cls._contributors():
            rows = await contributor.export(db, clinic_id, patient_id)
            sections.append(SubjectSection(module=module_name, section=contributor.name, rows=rows))
        return sections

    @classmethod
    async def anonymize(
        cls, db: AsyncSession, clinic_id: UUID, patient_id: UUID
    ) -> tuple[dict[str, int], list[RetainedSection]]:
        """Scrub what can be scrubbed; report what legally cannot.

        Returns ``(rows_scrubbed_per_section, retained_sections)``. The
        second half is not an error list — it is the part of the answer a
        clinic owes the patient, so it is returned rather than logged.

        Does not commit: the caller owns the transaction, and a partial
        erasure must roll back whole.
        """
        scrubbed: dict[str, int] = {}
        retained: list[RetainedSection] = []
        for module_name, contributor in cls._contributors():
            qualified = f"{module_name}.{contributor.name}"
            if contributor.anonymize is None:
                assert contributor.retention_reason is not None  # noqa: S101 - enforced above
                retained.append(
                    RetainedSection(
                        module=module_name,
                        section=contributor.name,
                        reason=contributor.retention_reason,
                    )
                )
                continue
            scrubbed[qualified] = await contributor.anonymize(db, clinic_id, patient_id)
        return scrubbed, retained
