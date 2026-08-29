# 0025 — PII is classified on the column, and the classification is enforced

- **Status:** accepted
- **Date:** 2026-08-28
- **Deciders:** Eduardo
- **Tags:** security, privacy, testing, modules

## Context

The copilot's PHI boundary decided what to tokenize from a list of key
names kept inside `backend/app/core/agents/redaction.py`. The list
mirrored the schema, and it lived nowhere near it, so it drifted every
single time anyone touched either side:

- `Patient.billing_tax_id` was never in the list. An RFC on a billing
  record reached the cloud model in cleartext for as long as the tool
  layer has existed.
- `LegalGuardian.dni` — a minor's guardian's document — was covered by
  accident (the list happened to carry the Spanish name) and fell out
  during a jurisdiction refactor.
- The list named Spanish documents while `Patient.national_id_type` had
  already moved to `curp`/`ine`/`passport`.

CLAUDE.md tells module authors to "name PII fields with redactor-known
keys". That is a convention, and a convention is a thing a person can
forget with no consequence until an audit. With 22 modules and a
plugin architecture that invites more, forgetting is the default outcome.

## Decision

**A column that holds personal data says so, on the column. Nothing
downstream keeps its own list, and a test fails when a column that looks
personal does not.**

```python
national_id: Mapped[str | None] = mapped_column(
    String(50), info=pii(PiiKind.NATIONAL_ID)
)
```

Three parts:

1. **`pii(kind, data_class=...)`** goes in `mapped_column(info=...)`.
   `PiiKind` is the redaction axis — which token family the value becomes
   (`NAME`, `PHONE`, `EMAIL`, `NATID`). `DataClass` is the policy axis —
   identifier, clinical, financial, operational — which nothing reads
   yet but which answers retention, export and erasure later. Both are
   recorded at once because both are answers about the same column, and
   coming back to classify 22 modules twice costs more than doing it
   once.

2. **The redactor derives its key map** from `pii_columns()`, plus the
   tenant's jurisdiction document names (ADR 0023) and a small explicit
   set of keys that a *tool payload* uses but no column carries —
   `full_name` composed by a handler, `mobile` as an alias for `phone`,
   `nif` as a CSV row key in `accounting_export`. That residue is the
   only hand-maintained part left, and it is small enough to read.

3. **`tests/test_pii_redaction_contract.py` enforces it**, in the shape
   `test_event_transaction_boundary.py` already established: a broad
   pattern finds columns that look personal, and each must either carry
   a classification or appear in a `_NOT_PERSONAL` allowlist that a human
   had to edit deliberately. Stale allowlist entries fail too, so the
   list cannot rot into a blanket exemption.

   The check builds its own view of the schema rather than reading
   `Base.metadata` as it finds it. Two reasons, both load-bearing: the
   metadata only holds what something imported, so a module no test
   touches would pass unchecked; and other tests register synthetic
   tables on the shared metadata (`test_module_yaml_loader` adds
   `seed_demo_items`), which made the first version of this test
   order-dependent. It imports every file that declares a table and keys
   on the `__tablename__` values the model classes declare — and a
   further test fails if a new table-declaring file appears that the
   importer does not reach.

Writing the test found nine more unredacted columns immediately:
`invoices.billing_name` / `billing_tax_id` / `billing_email`,
`budget_signatures.signed_by_name` / `signed_by_email`,
`verifactu_settings.producer_nif` / `producer_name`,
`verifactu_certificates.nif_titular`, and
`whatsapp_kapso_settings.display_phone_number`.

## Consequences

### Good

- Adding a PII column and forgetting to redact it is now one omission
  instead of two, and CI catches the one.
- The classification travels with the column through renames and module
  moves, because it *is* part of the column.
- `pii_columns()` reads the modules mounted right now, so an install
  brings its columns into the boundary without a registration step.
- `DataClass` gives the later work (retention, subject export, erasure) a
  place to read from that already covers the schema.

### Bad / accepted trade-offs

- **Redaction keys on the key of a JSON payload, which carries no
  table.** `name` is both `LegalGuardian.name` (a person) and
  `Allergy.name` (a substance); classifying the former puts `name` in the
  map, so a catalog name reaching the model under that key is tokenized
  too. The copilot therefore cannot discuss an allergy by name. Accepted
  for now: over-redaction degrades an answer, under-redaction leaks a
  patient.
- The `_LOOKS_PERSONAL` pattern is a heuristic. A column named
  `contact_reference` holding a phone number matches nothing and passes
  silently. The test raises the floor; it does not prove coverage.
- Model files now import from `app.core.privacy`, so a module's models
  depend on core. That direction is already normal here (every model
  imports `app.database`), but it is a dependency that did not exist.
- The contract covers the **schema**. A tool handler that invents a key
  (`{"whom": patient.full_name}`) is still only covered by the CLAUDE.md
  convention — payload keys cannot be checked statically.

## Alternatives considered

- **Keep the list, add a test that compares it to the schema** — the
  test would need the same PII judgement the annotation encodes, so the
  judgement would live in the test instead of the model. Same drift, one
  layer further away.
- **A central registry module mapping table.column -> kind** — a third
  place to forget, and it breaks when a module is renamed or moved.
- **Infer from column name alone, no annotation** — that is the
  `_LOOKS_PERSONAL` heuristic, and it cannot tell `Allergy.name` from
  `LegalGuardian.name`. Good enough to *flag*, not to *decide*.
- **Type-level marking (`Mapped[PiiStr]`)** — prettier at the call site,
  but it would need a custom SQLAlchemy type per kind and would change
  the column's Python type for every consumer.

## How to verify the rule still holds

- `backend/tests/test_pii_redaction_contract.py` — the whole point. It
  fails on an unclassified personal-looking column, on a stale allowlist
  entry, on a classified column the redactor does not cover, and on a
  kind mismatch between the two.
- `backend/tests/test_llm_orchestrator.py` — jurisdiction selection and
  the fail-closed default.

## References

- `backend/app/core/privacy/classification.py`
- `backend/app/core/agents/redaction.py` — `_kind_for_key`
- [ADR 0023](0023-privacy-policy-and-custody-modes.md) — jurisdictions
- `backend/tests/test_event_transaction_boundary.py` — the enforcement
  idiom this copies
