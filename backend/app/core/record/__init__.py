"""The clinical record as a module contract.

A dental record is spread across every installed module: demographics in
``patients``, history in ``patients_clinical``, evolution notes in
``clinical_notes``, tooth status in ``odontogram``, charting in
``periodontogram``, therapeutic plans in ``treatment_plan``, radiographs in
``media``. The ``record`` module composes it; it does not own any of it.

That is the whole design. See `docs/features/expediente-clinico.md`:

    The temptation is to add an `expediente` table and copy data into it.
    That is the failure this spec exists to prevent. The record is not a new
    place to keep clinical data; it is a *view* of data seven modules already
    own, and the moment it becomes a copy it starts drifting from the source
    and there are two truths about a patient's allergies.

So each module answers for itself: it returns :class:`RecordSection` objects
from ``get_record_sections()``, and the ``record`` module fans a request out
over the modules ``core_module.state`` says are installed (ADR 0018).

**Why the vocabulary lives in core and not in the ``record`` module.** A
contributing module would otherwise have to import from ``record`` and declare
it in ``manifest.depends`` — which inverts the dependency (the record reads
them, not the other way round) and would make an optional module required by
`patients_clinical`, which is not removable. Core owning the types keeps every
arrow pointing inward, exactly as :mod:`app.core.privacy.subject` already does
for subject rights. When ``record`` is not installed nothing calls these hooks
and nothing changes.

**This is a different contract from ``SubjectContributor``, not a reuse of
it.** They answer different questions, for different readers:

================  =============================  ============================
                  ``SubjectContributor``         ``RecordSection``
================  =============================  ============================
Question          "What do you hold about this   "What of yours belongs in a
                  person?"                       clinical record?"
Audience          The data subject, a regulator  Another clinician
Billing data      Yes — it is their data         **No** — a referral is not a
                                                 financial document
Ordering          By module                      Clinically, by section
Erasure           Central to it                  Not applicable (ADR 0032)
================  =============================  ============================

A module may implement both, one, or neither. ``billing``, ``payments``,
``verifactu`` and ``accounting_export`` implement only the subject contract: a
clinical disclosure carrying invoice data is a privacy defect, not a feature.
"""

from .contract import (
    EntryStatus,
    RecordEntry,
    RecordSection,
    SectionCategory,
)

__all__ = [
    "EntryStatus",
    "RecordEntry",
    "RecordSection",
    "SectionCategory",
]
