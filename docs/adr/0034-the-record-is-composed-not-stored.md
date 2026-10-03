# 0034 — The clinical record is composed from the modules, and its contract lives in core

- **Status:** accepted
- **Date:** 2026-09-30
- **Deciders:** Eduardo
- **Tags:** clinical, modules, architecture

## Context

`docs/features/expediente-clinico.md` settled what a clinical record *is*: a
header and ordered sections of dated, attributed entries, assembled from data
seven modules already own. It also named the failure it exists to prevent —
adding an `expediente` table and copying data into it, after which there are
two truths about a patient's allergies.

Building the `record` module forced a question the spec left implicit: **where
does the contract live?** A contributing module has to return something, and
that something has a type.

Putting `RecordSection` in the `record` module looks natural and does not work:

- `patients_clinical` would have to import from `record` and declare it in
  `manifest.depends`. That inverts the real dependency — the record reads the
  modules, not the other way round.
- `record` is optional (`auto_install=False`, `removable=True`) while
  `patients_clinical` is `removable=False`. A non-removable module cannot
  depend on a removable one without making it effectively mandatory, which
  defeats the point of the module being optional.
- Uninstalling `record` would then be a question about clinical modules, which
  is exactly backwards: the record is a *view*.

The same question was already answered once, for subject rights: `patients`,
`billing` and fourteen others return `SubjectContributor` objects defined in
`app.core.privacy`, not in a module ([ADR 0026](0026-subject-rights-are-a-module-contract.md)).

## Decision

**The clinical record is a composition, never a table — and the contract that
makes it one lives in core.**

1. `app.core.record` owns the vocabulary: `RecordSection`, `RecordEntry`,
   `SectionCategory`, `EntryStatus`. Modules import *inward*, as they already
   do for privacy, and the `record` module needs no module in `depends` to
   read it.
2. `BaseModule.get_record_sections()` defaults to `[]`. A module that holds
   clinical facts contributes; one that does not stays silent, and when
   `record` is not installed nothing calls the hook at all.
3. The `record` module **owns no clinical tables**. It has no models and no
   migrations, like `reports`. The only tables it will ever own are the ones
   that are genuinely new — the authorisations that permit a disclosure, and
   the artifacts one produces.
4. **It is a separate contract from `SubjectContributor`, not a reuse of it.**
   They answer different questions for different readers, and the difference
   that matters most is that `billing`, `payments`, `verifactu` and
   `accounting_export` contribute to the subject export and **nothing** to a
   clinical record. A disclosure carrying invoice data is a privacy defect,
   not a feature.

## Consequences

### Good

- The record cannot drift from the source, because there is no copy.
- A module can be uninstalled and the record is shorter, not broken — the
  fan-out asks `list_modules()`, the installed set ([ADR 0018](0018-install-state-is-the-mount-authority.md)).
- Phase 0's append-only guarantees stay where the data is. Uninstalling
  `record` cannot make a clinical table deletable again, which would have been
  the consequence of encapsulating those corrections here.
- The export formats become mappings. Building the internal model in the shape
  of a composition means CDA R2 and FHIR `Composition` are projections rather
  than rewrites.

### Bad / accepted trade-offs

- Core carries a vocabulary that only an optional module consumes. It is inert
  when `record` is not installed, and the alternative — modules importing from
  an optional module — is worse.
- Reading a record costs one query per contributing section. A record is read
  by a human, a handful of times a day; the alternative is a copy.
- Two contracts that look similar sit next to each other, and a module author
  has to know which question they are answering. The table in
  `app.core.record` and in `docs/technical/record/overview.md` is there for
  exactly that moment.

## Alternatives considered

- **A materialised `expediente` table.** The failure the spec exists to
  prevent. Fast reads, and two truths about a patient's allergies.
- **Reusing `SubjectContributor`.** One contract, less code — and a clinical
  referral that carries the patient's invoices, because the subject contract
  is right to include them and a record is right to exclude them. The
  distinction is the product, not an implementation detail.
- **`RecordSection` in the `record` module.** Rejected for the dependency
  inversion above.
- **Duck typing with plain dicts.** No import, no types, and no way to refuse a
  section that forgot its `title_key` — which is how a record ends up with a
  Spanish literal that is wrong in the language it gets exported in.

## References

- `docs/features/expediente-clinico.md` — the spec this implements
- `app/core/record/` — the contract
- `app/modules/record/` — the composition
- [ADR 0026](0026-subject-rights-are-a-module-contract.md) — the sibling contract
- [ADR 0032](0032-clinical-record-is-append-only.md) — what makes the entries trustworthy
- [ADR 0018](0018-install-state-is-the-mount-authority.md) — why the fan-out asks the installed set
