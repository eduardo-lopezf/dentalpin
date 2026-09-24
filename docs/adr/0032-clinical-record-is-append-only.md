# 0032 — The clinical record is append-only, and every entry names a licensed author

- **Status:** proposed
- **Date:** 2026-09-22
- **Deciders:** Eduardo
- **Tags:** clinical, compliance, privacy, modules

## Context

DentalPin holds everything a dental clinical record needs — demographics
in `patients`, history in `patients_clinical`, evolution notes in
`clinical_notes`, tooth status and procedures in `odontogram`, charting
in `periodontogram`, therapeutic plans in `treatment_plan`, radiographs
in `media`. What it does not yet have is the property that turns that
data into a *record*: you cannot prove what it said on the day of the
medical act.

Three concrete defects, verified on `main`:

- **`patients_clinical` hard-deletes.** Seven `db.delete()` call sites in
  `backend/app/modules/patients_clinical/service.py` (allergies,
  medication, systemic disease, surgical history, emergency contacts,
  legal guardians). A penicillin-allergy row removed on a mistaken tap
  leaves no trace. This is a patient-safety defect before it is a
  compliance one, and it already violates this repo's own rule — root
  `CLAUDE.md`, *Database conventions*: "Soft delete via `status` (never
  hard-delete patient data)."
- **Notes are overwritten in place.** `clinical_notes/service.py:304`
  assigns `note.body = body`. The prior text is gone; an amendment is
  indistinguishable from the original.
- **Authorship points at an account, not a professional.**
  `clinical_notes.author_id` is a FK to `users.id`. The legal author of a
  clinical entry is a professional with a credential — *cédula
  profesional* in Mexico, número de colegiado in Spain — which lives on
  `professionals.license_number`, not on `users`.

Both regimes this product operates under require the same two things: the
record is preserved and corrections are *annotated* rather than erased,
and each entry carries the name and credential of whoever authored it.
In Mexico that is NOM-004-SSA3-2012 (*Del expediente clínico*), which
also sets a minimum retention of five years from the last medical act; in
Spain, Ley 41/2002, with a comparable five-year floor that several
autonomous communities extend. The precise obligations belong to local
counsel — what is architectural, and what this ADR fixes, is that today
the software cannot satisfy *either* reading.

The shape is already established in-house. [ADR 0013](0013-periodontogram-snapshot-model.md)
settled that periodontal charting is immutable dated rows rather than a
mutable current state, for exactly this reason. This ADR generalises that
answer to the rest of the clinical surface.

## Decision

**Clinical data is corrected by appending, never by overwriting or
deleting, and every clinical entry is attributable to a licensed
professional — separately from the account that typed it.**

Three clarifications, each of which is the part that matters:

1. **"No longer true" and "never was true" are different states, and the
   model must hold both.** A medication the patient has stopped taking is
   a clinical fact with an end date (`ended_at`); an entry recorded on the
   wrong patient is a mistake to be retracted (`retracted_at`, with a
   reason). Collapsing them into one `deleted_at` destroys clinical
   meaning: a retracted allergy must stop driving warnings, while a
   discontinued medication remains part of the history and must still be
   visible to whoever reads it later. Neither removes the row.

2. **An amendment is a new version, not an edit.** The body of a note at
   any past instant must be recoverable. The current text stays cheap to
   read — consumers keep reading the latest version — but the prior
   version and the reason for the change are retained and attributed.

3. **"Entered by" and "authored by" are two fields.** An assistant may
   type a note the dentist is responsible for. `author_id → users.id`
   remains the audit trail of who operated the software;
   `authored_by_professional_id → professionals.id` carries the clinical
   responsibility and, through it, the licence number that appears on an
   exported record. Modules holding clinical entries declare both. This
   continues the rewire that moved `treatment_plan` and `agenda` onto
   directory professionals rather than product accounts.

Retention is not re-invented here: the floor is expressed through the
`retention_reason` that [ADR 0026](0026-subject-rights-are-a-module-contract.md)
already requires from a contributor that cannot erase.

## Consequences

### Good

- The record becomes evidence. "What did the chart say on the day of the
  procedure?" is answerable, which is the question that matters in a
  complaint, an insurance review or a court.
- A mistaken tap stops being a clinical hazard.
- Exported records can name a responsible professional and a licence,
  which is a precondition for any interchange format worth the name
  (see `docs/features/expediente-clinico.md`).
- Erasure requests get an honest answer instead of a silent one: the
  clinical sections declare a `retention_reason` like every other
  contributor that law forbids erasing.

### Bad / accepted trade-offs

- Clinical tables grow monotonically. For a dental clinic's volume this
  is irrelevant against the cost of the alternative, but it is real.
- Every read path in `patients_clinical` and `clinical_notes` gains a
  predicate, and the UI gains a decision it did not have: whether to show
  ended and retracted entries. Defaulting them out of sight while keeping
  them one interaction away is the intended shape.
- A migration must backfill existing rows with a professional. Rows whose
  author is an account with no directory profile cannot be invented — they
  keep the account attribution and are marked as pre-dating this rule,
  rather than being assigned a professional that did not sign them.
- This is a data migration over populated tables, which is the class of
  change that has already broken a deploy here. It is tested against a
  database with rows, not only an empty one.

## Alternatives considered

- **A generic audit-log table in core.** Rejected for the reason that
  settled [ADR 0025](0025-pii-is-classified-on-the-column.md) and
  [ADR 0026](0026-subject-rights-are-a-module-contract.md): a central
  table describing other modules' rows is a third place to forget, and it
  breaks when a module is renamed. Each module keeps its own history, as
  each module already answers for its own subject data.
- **Postgres temporal tables / row versioning extensions.** Real history
  with no application code, but it records *when the row changed*, not
  *why* or *who is clinically responsible* — which is the part the
  regulations actually ask for. It also puts a clinical guarantee outside
  the modules that own the data.
- **Keeping hard delete and relying on backups.** A backup is not a
  record: it cannot be produced per patient, it is not attributable, and
  restoring it to answer one question is not an operation a clinic can
  perform.
- **One `deleted_at` for both cases.** Simpler, and wrong — see
  clarification 1.

## How to verify the rule still holds

- A contract test in the shape this repo already uses for
  `tests/test_pii_redaction_contract.py` and
  `tests/test_event_transaction_boundary.py`: a module that declares
  clinical sections may not call `db.delete()` against its own clinical
  tables, and each such table must carry the retraction and attribution
  columns. Violations fail with the offending call site named; the
  allowlist takes a reasoned entry, not a blanket skip.
- A round-trip test: amend a note, then assert the pre-amendment body is
  still retrievable and still attributed to its original professional.

## References

- `backend/app/modules/patients_clinical/service.py` (7 `db.delete()` sites)
- `backend/app/modules/clinical_notes/service.py:304`
- `backend/app/modules/professionals/models.py` — `license_number`
- [ADR 0013](0013-periodontogram-snapshot-model.md) — immutable dated rows, same reasoning
- [ADR 0026](0026-subject-rights-are-a-module-contract.md) — `retention_reason`
- `docs/features/expediente-clinico.md` — the record this rule makes possible
- NOM-004-SSA3-2012 (MX); Ley 41/2002 (ES) — obligations to be confirmed with local counsel
