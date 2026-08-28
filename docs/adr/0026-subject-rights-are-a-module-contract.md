# 0026 — Subject rights are a module contract, and erasure must be justified

- **Status:** accepted
- **Date:** 2026-08-29
- **Deciders:** Eduardo
- **Tags:** privacy, modules, compliance

## Context

A patient asking for a copy of their record — or for it to be erased —
is asking about data spread across every installed module: demographics
in `patients`, history and contacts in `patients_clinical`, appointments
in `agenda`, invoices in `billing`, photos in `media`. There are 22
modules and the architecture invites more.

Core cannot answer for them. ADR 0001 forbids it from importing module
code, and it does not know their tables. Nor can one module answer for
another: `patients` has no business reading `billing`'s rows.

The obvious shortcuts are both wrong. A central registry mapping
`table.column` to a rule is a third place to forget, and it breaks when a
module is renamed or moved (the argument that already settled ADR 0025).
Writing the export by hand in a core service means core importing every
module, which is the dependency inversion the plugin architecture exists
to prevent.

There is also a legal shape the naive design gets wrong. **Erasure is not
universal.** An issued invoice is a fiscal document whose retention is
set by tax law, which does not yield to a data-protection request; in
Spain `verifactu` has already declared it to the AEAT. A model where
every module implements `delete()` would either break the fiscal record
or leave each module to quietly skip erasure with nothing recording that
it did.

## Decision

**Each module answers for itself, through
`BaseModule.get_subject_contributors()`. A contributor exports
unconditionally, and either anonymizes or states why it legally cannot.**

```python
SubjectContributor(
    name="invoices",
    export=_export_invoices,
    retention_reason="Las facturas emitidas son documentos fiscales: ...",
)
```

Four parts:

1. **Export is required; erasure is not.** Portability has no legal
   exception the way erasure does, so every contributor supplies
   `export`. `anonymize` is optional — but a contributor that omits it
   **must** supply `retention_reason`, and one that supplies both is
   refused at construction. Silence about erasability is not a state the
   type system allows.

2. **`retention_reason` is written for the patient, not the developer.**
   It is the sentence a clinic passes on when it declines part of a
   request, so it is prose in the product's language, and it is returned
   from the erasure call rather than logged. What a clinic owes the
   patient is part of the answer, not a side effect.

3. **Anonymization is driven by the classification, not by hand.**
   `anonymize_instance(row)` scrubs the columns that ADR 0025 already
   marked with `pii()` — nullable ones to `NULL`, non-nullable ones to a
   placeholder — and **skips `DataClass.FINANCIAL`**. So the fiscal
   exception is enforced from both ends: `billing` declines to anonymize,
   and even a caller reaching a billing column by another path leaves it
   intact. This is `DataClass`'s first enforcer; until now nothing read
   it.

4. **The fan-out follows install state.** `SubjectDataService` iterates
   `module_registry.list_modules()` (ADR 0018), so an uninstalled module
   is not asked, and an installed one cannot be skipped. Sections come
   back even when empty: "this module holds nothing" is an answer, while
   a missing section leaves the reader unable to tell it was asked.

Rows are **not deleted**. A patient row is referenced by invoices,
appointments and clinical notes; erasure scrubs the identifying columns
and archives the row, which is what makes the remaining records
non-identifying without breaking them.

### The principle that decides each module's answer

**Identity is erased; the record is retained and thereby becomes
pseudonymous.**

Almost no module holds a column that identifies a person on its own —
they hold clinical or financial facts keyed by `patient_id`. Once the
identity row is scrubbed, those rows point at nobody. That is what lets
the clinical modules retain their data (health-record retention is a
legal obligation that outlives an erasure request) while the request is
still honoured.

So the answer splits three ways:

| Kind | Modules | Erasure |
|---|---|---|
| Clinical record | `agenda`, `odontogram`, `periodontogram`, `treatment_plan`, `clinical_notes`, `media`, `patients_clinical` | Retained — sanitary retention |
| Fiscal record | `billing`, `payments`, `verifactu` | Retained — tax law; `verifactu` additionally cannot be rewritten without breaking its hash chain |
| Outreach and working data | `recalls`, `notifications`, `patient_timeline`, `budget`, `migration_import` | Erased — nothing obliges a clinic to keep a reminder it sent, a derived index, an unbilled quote, or the staging copy of a finished migration |

`patients` itself is the identity, and is always erased.

The reasons are **prose, not periods**: they say a record is retained,
never for how long, because nothing in the system holds a window. Giving
them numbers — NOM-004-SSA3-2012 for the clinical record, CFF art. 30 for
accounting — is tracked as pending retention policy in
[`docs/technical/todos.md`](../technical/todos.md#retention-policies--pending--p1).

**These are first-pass legal calls, not settled law.** Which records a
dental clinic must retain, and for how long, varies by jurisdiction —
which is exactly what `PrivacyPolicy.regulations` (ADR 0023) exists to
carry once something reads it. They are recorded in code, in the
`retention_reason` of each contributor, so that reviewing them is reading
19 sentences rather than auditing 22 modules.

### The HTTP surface

`/api/v1/privacy` turns the contract into a procedure a clinic can
follow:

| Endpoint | Permission | Notes |
|---|---|---|
| `GET /subjects/{patient_id}/export` | `privacy.subject.export` | Requires a `reason`. Each section reports whether an erasure would reach it, and the retention reason when it would not. |
| `POST /subjects/{patient_id}/erasure` | `privacy.subject.erase` | Requires a `reason` of at least 10 characters. One transaction. |
| `GET /subjects/requests` | `privacy.subject.read` | The log of exercised rights. |

Three decisions worth stating:

1. **Its own permissions, not `patients.read`.** An export hands out
   every module's data on one patient in a single response and an erasure
   is irreversible; neither should ride on the grant that opens a chart.
2. **A reason is required on both.** For the erasure it is the *only*
   record of the request that survives it, so it has a minimum length —
   a field that accepts one keystroke is a field people press through.
3. **`core_subject_request` holds no personal data of its own.** It
   records who acted, when, why, and the per-section counts — not what
   the data said — so it survives the erasure it documents. Without it,
   an erasure is indistinguishable from a bug that emptied the columns.

## Consequences

### Good

- A module that holds patient data can no longer stay silent about it,
  and the omission is visible in one place per module rather than
  discovered during a request.
- The fiscal retention exception is modelled instead of improvised, and
  the words a clinic gives the patient live next to the code that
  enforces the refusal.
- `DataClass` acquires its first consumer, so classifying a column now
  buys redaction *and* erasure behaviour from one annotation.
- Adding a module means answering the question once, at the moment the
  author still remembers what the tables hold.

### Bad / accepted trade-offs

- **Nothing verifies the requester is who they say.** The endpoints check
  that an authenticated staff member holds the permission, not that a
  patient actually made the request. Identity verification is the
  clinic's procedure, and the `reason` field is where it is recorded.
- **`copilot` is a known gap.** Conversation transcripts hold patient
  names in cleartext, and a conversation's `context` is a client-supplied
  JSONB blob with no guaranteed shape — there is no reliable way to find
  the conversations about one patient. A best-effort match would look
  like coverage while missing rows, which is worse than an honest gap, so
  the module contributes nothing and `test_subject_rights.py` records why.
- **Free text is not scrubbed where the record is retained.** A clinical
  note or an appointment note reading "su hija Ana la trae los martes"
  survives an erasure. Catching that needs NER, the same gap the PHI
  boundary documents (ADR 0025). Where the record is *not* retained —
  recalls, timeline, notification bodies, budget notes — the free text is
  cleared explicitly.
- **`media` erases metadata, not bytes.** The stored object survives; ADR
  0008 left storage retention documented and unenforced.
- **The default is still `[]`.** A module can be added without answering,
  and `test_subject_rights.py` now catches it — but through a test, not
  through the type system or an install-time refusal.
- The erasure endpoint has **no dry-run and no undo**. It reports what it
  did, not what it would do, and the only thing that survives it is the
  `core_subject_request` row.
- The request log records the outcome, not the data. That is deliberate —
  a log that kept a copy of the export would defeat the erasure it
  documents — but it means an export cannot be reproduced from the log.
- Anonymization is irreversible and has no dry-run. The service reports
  what it *did*, not what it *would* do.

## Alternatives considered

- **A core service that imports every module and writes the export
  by hand** — inverts the plugin dependency direction (ADR 0001) and
  turns every new module into an edit of core.
- **A central `table.column` registry of erasure rules** — a third place
  to forget, broken by renames and module moves. Same argument that
  settled ADR 0025.
- **`delete()` per module instead of `anonymize()`** — deletes rows that
  invoices and appointments reference, and offers no way to express the
  fiscal exception except by silently doing nothing.
- **Deriving everything from the classification, with no module code** —
  the classification knows which *columns* are personal, not which
  *rows* belong to a patient (the FK is named differently in every
  table) nor which sections are legally erasable. It does the column
  half; the module supplies the row half.

## How to verify the rule still holds

- `backend/tests/test_subject_rights.py` — the contract refuses a
  contributor that neither anonymizes nor explains; `anonymize_instance`
  scrubs classified columns and spares `FINANCIAL` ones; every
  contributor's export and anonymize is executed against a real patient,
  which is what catches a broken `ChildLink` chain or a renamed column.
- `TestCoverage::test_every_other_module_contributes` fails when a module
  contributes nothing and is not in `SILENT_BY_DESIGN`, and its companion
  fails when a `SILENT_BY_DESIGN` entry starts contributing. Adding a
  module that holds patient data without answering is now a test failure,
  not a discovery during a request.

## References

- `backend/app/core/privacy/subject.py`
- `backend/app/core/plugins/base.py` — `get_subject_contributors()`
- [ADR 0025](0025-pii-is-classified-on-the-column.md) — the classification
  that drives `anonymize_instance`
- [ADR 0001](0001-modular-plugin-architecture.md) — why core cannot answer
- [ADR 0018](0018-install-state-is-the-mount-authority.md) — why the
  fan-out uses `list_modules()`
