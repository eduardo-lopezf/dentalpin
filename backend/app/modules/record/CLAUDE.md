# Record module

The clinical record (*expediente clínico*) as a **composition**: a header and
ordered sections of dated, attributed entries, assembled from the modules that
own the data.

Spec: [`docs/features/expediente-clinico.md`](../../../../docs/features/expediente-clinico.md).
Decisions behind it: [ADR 0032](../../../../docs/adr/0032-clinical-record-is-append-only.md)
(the record is append-only) and [ADR 0033](../../../../docs/adr/0033-disclosure-requires-a-recorded-authorisation.md)
(disclosure requires a recorded authorisation).

## Public API

Routes mounted at `/api/v1/record/`.

- `GET /patients/{patient_id}` — the composition; `record.read`.
  `?include_retracted=true` adds the entries that were taken back.

## Dependencies

`manifest.depends = ["patients", "professionals"]` — deliberately short.

Contributing modules are reached through `get_record_sections()`, a **core**
contract, so this module never imports them. `patients_clinical`,
`clinical_notes`, `odontogram`, `periodontogram`, `treatment_plan`, `media` and
`agenda` are therefore **not** dependencies: when one is uninstalled the record
simply has fewer sections. What is declared is what the header reads directly —
who the record is about, and which professional answers for it.

Expect `media` to join when phase 2 produces artifacts, and possibly
`notifications` for the patient notice that a disclosure happened.

## Permissions

`record.read`. `export`, `disclose` and `authorise` arrive with the endpoints
that use them — a permission with nothing behind it is a promise the UI starts
making on its own. Who holds `disclose` is a clinical-governance question left
open in the spec; the defensible default is that it is not a reception-desk
permission.

## Data ownership

**None, on purpose.** No models, no migrations, like `reports`. The only tables
this module will ever own are the ones that are genuinely new: the
authorisations that permit a disclosure, and the artifacts one produces.

## Tools exposed

None yet. An agent-addressable "read this patient's whole clinical record" is a
disclosure in everything but name, and it waits for the authorisation phase to
say who may ask for one.

## Events

None emitted or consumed yet. Phase 2's disclosure will publish one.

## Lifecycle

`installable=True`, `auto_install=False`, `removable=True`. A clinic that never
hands a record to anyone does not need it.

## Gotchas

- **Never add a clinical table here.** The spec exists to prevent exactly that:
  *"The record is not a new place to keep clinical data; it is a view of data
  seven modules already own, and the moment it becomes a copy it starts
  drifting from the source and there are two truths about a patient's
  allergies."* A section that needs data nobody owns means the owning module is
  missing a column, not that the record needs a table.

- **Phase 0's guarantees do not live here and must not move here.** Append-only
  history (`patients_clinical`), note versions (`clinical_notes`) and the
  account↔professional link (`professionals`) are corrections inside the
  modules that own that data. Uninstalling this module must not make a clinical
  table deletable again.

- **Sections come back empty rather than missing.** "This module holds nothing
  about this patient" is an answer; an absent section leaves the reader unable
  to tell it was asked.

- **A failing section does not deny the rest of the record.** `compose()` logs
  the exception and returns that section empty. A clinician mid-consultation
  loses one section, not the chart.

- **Retracted entries are excluded by default, never dropped.** They stay
  reachable with `include_retracted=true`, because "what did the chart say on
  the day of the procedure" has to stay answerable (ADR 0032) — but they are
  not part of what a colleague is handed.

- **`title_key`, never a literal.** A record is read in the clinic's language
  and exported in the patient's. The contract refuses a section without one.

## Related ADRs

- `docs/adr/0018-install-state-is-the-mount-authority.md` — the fan-out asks
  `list_modules()`, the installed set, not what is on disk.
- `docs/adr/0026-subject-rights-are-a-module-contract.md` — the sibling
  contract, and why this is a separate one.
- `docs/adr/0032-clinical-record-is-append-only.md`
- `docs/adr/0033-disclosure-requires-a-recorded-authorisation.md`

## CHANGELOG

See `./CHANGELOG.md`.
