"""Field-level data classification, declared on the column itself.

The PHI boundary used to carry its own list of PII column names, kept in
sync with the schema by hand. It drifted every time: ``billing_tax_id``
was never in it, ``LegalGuardian.dni`` fell out of it during a
jurisdiction refactor, and a Spanish document name was pinned in it while
the schema had moved to Mexican ones. A list that mirrors the schema but
lives away from it will always drift.

So the schema declares instead:

    national_id: Mapped[str | None] = mapped_column(
        String(50), info=pii(PiiKind.NATIONAL_ID)
    )

and :func:`pii_columns` reads the declarations back. Adding a PII column
and forgetting to redact it is now one omission instead of two, and
``tests/test_pii_redaction_contract.py`` fails on that omission.

``DataClass`` is the coarser axis, for the policy questions that are not
about redaction — retention windows, what an export must include, what
an erasure may drop. Its first consumer is ``anonymize_instance`` (ADR
0026), which scrubs classified columns on an erasure request and spares
``FINANCIAL`` ones, because a name on an issued invoice is retained by
tax law. Retention windows still read nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class DataClass(StrEnum):
    """What kind of data a column holds, for policy purposes."""

    IDENTIFIER = "identifier"
    """Identifies a person directly: name, contact, government document.
    Pseudonymisable — an export replaces it, an erasure drops it."""

    CLINICAL = "clinical"
    """Health data. Special category under GDPR art. 9, PHI under HIPAA.
    Retained under the longest clinical obligation, never hard-deleted."""

    FINANCIAL = "financial"
    """Invoices, payments, tax identifiers on a billing document.
    Retention is fiscal, so an erasure request cannot reach it."""

    OPERATIONAL = "operational"
    """Appointments, logs, scheduling. Personal by association only."""


class PiiKind(StrEnum):
    """Token family the redactor uses for a value.

    The values are the token prefixes themselves (``NAME_a1b2c3``), so a
    kind is what the model sees instead of the real value.
    """

    NAME = "NAME"
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    NATIONAL_ID = "NATID"

    CONTACT = "CONTACT"
    """A column that holds an email *or* a phone depending on the row —
    ``CommunicationMessage.to_address`` is one per channel. Neither
    ``EMAIL`` nor ``PHONE`` would be true of every value."""


@dataclass(frozen=True, slots=True)
class PiiTag:
    """The classification attached to one column."""

    kind: PiiKind
    data_class: DataClass


def pii(kind: PiiKind, *, data_class: DataClass = DataClass.IDENTIFIER) -> dict[str, Any]:
    """Classify a column. Pass to ``mapped_column(info=...)``.

    ``data_class`` defaults to ``IDENTIFIER`` because a column worth
    tokenizing is almost always one; billing identifiers are the
    exception and pass ``FINANCIAL`` explicitly.
    """
    return {"pii": PiiTag(kind=kind, data_class=data_class)}


def pii_columns() -> Mapping[str, PiiKind]:
    """Every classified column name currently mapped, to its token kind.

    Reads ``Base.metadata.tables`` rather than the mapper registry:
    metadata is populated when a model class is defined, while touching
    the mappers would force configuration of relationships whose target
    module may not be installed.

    Only the modules mounted in this process contribute — which is the
    right scope, because an uninstalled module exposes no tools and so
    puts none of its columns into an outgoing payload.

    Column *names* collide across tables on purpose: redaction keys on
    the key of a JSON payload, which carries no table. ``name`` is both
    ``LegalGuardian.name`` (a person) and ``Allergy.name`` (a substance);
    only the former is classified, and the cost is that a catalog name
    reaching the model under the key ``name`` is tokenized too.
    """
    from app.database import Base

    found: dict[str, PiiKind] = {}
    for table in Base.metadata.tables.values():
        for column in table.columns:
            tag = column.info.get("pii")
            if isinstance(tag, PiiTag):
                found[column.key] = tag.kind
    return found


def classified_columns() -> Mapping[tuple[str, str], PiiTag]:
    """``(table, column) -> tag`` for every classified column.

    Keyed by table as well, so the contract test can name the offender
    and so a future retention or export pass can act per table.
    """
    from app.database import Base

    found: dict[tuple[str, str], PiiTag] = {}
    for table_name, table in Base.metadata.tables.items():
        for column in table.columns:
            tag = column.info.get("pii")
            if isinstance(tag, PiiTag):
                found[(table_name, column.key)] = tag
    return found
