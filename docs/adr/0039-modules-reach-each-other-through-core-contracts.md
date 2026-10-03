# 0039 — A module reaches another's data through a core contract, not an import

- **Status:** accepted — applied to `agenda` and to `schedules`' use of `professionals`; other modules still import directly
- **Date:** 2026-10-01
- **Deciders:** Eduardo (maintainer)
- **Tags:** modules, dependencies, agenda, core

## Context

[ADR 0037](0037-a-module-integrates-with-what-it-can-live-without.md)
made every dependency of the agenda optional, and it worked: the agenda
books with any of its six links switched off. But its code still knew
the other modules by name. Twelve imports reached into `patients`,
`professionals`, `catalog`, `odontogram`, `treatment_plan` and
`schedules` — models for ORM relationships, a schema, a service — and
two of those modules depend on the agenda in turn.

That coupling had costs the optional-dependency work could not remove.
The agenda could not be read or tested without six other modules. Its
queries walked other modules' tables four levels deep
(`appointment → link → planned item → treatment → teeth`), so a column
renamed in `odontogram` broke the calendar. And "is the other module
running?" was asked by name against the registry, a second fact that
had to stay in step with the import beside it — the kanban got it wrong
by treating a successful import as proof that `schedules` was running.

## Decision

**The core names what a consumer needs; the owner supplies it; the
consumer asks the core.**

- `backend/app/core/contracts.py` holds the contracts — `Protocol`s and
  the small dataclasses that cross them (`PersonBrief`,
  `PlannedTreatmentBrief`). Rows never cross.
- A module supplies implementations from `get_providers()`:
  `{Contract: instance}`.
- A consumer calls `contracts.provider(Contract)`. It looks only at
  **running** modules, so the answer is also the availability check:
  `None` means the owning App is off, and the consumer carries on
  without the link (ADR 0037). There is no separate registry and no
  state to keep in step — the provider *is* the fact.

Four contracts exist, each as wide as the agenda's actual use:

| Contract | Supplied by | Used for |
|---|---|---|
| `PatientDirectory` | `patients` | validate a patient, label appointments |
| `ProfessionalDirectory` | `professionals` | validate, label, list the bookable, mirror a legacy account id, name the profile an account is |
| `PlannedTreatments` | `treatment_plan` | validate items, describe linked treatments |
| `AppointmentBook` | `agenda` | whose appointment it is, a patient's appointments, notes left in visits |
| `PlanBudgets` | `budget` | where a plan's quote stands, what is priced — read-only |
| `Collections` | `payments` | whether a patient paid into a plan |
| `PlanQuotes` | `treatment_plan` | the plan as a snapshot, for `budget` to price |
| `WorkingHours` | `schedules` | who is on a break or off right now |

`schedules` uses `ProfessionalDirectory` too, to validate and list
professionals and to resolve a demo account to its profile; it no
longer imports `professionals`. Its one remaining import is `agenda`,
which it depends on outright.

The Patients App (`patients`, `patients_clinical`, `patient_timeline`)
imports nothing outside itself either. `patients_clinical` asks
`ProfessionalDirectory.for_account` who answers for a history entry and
lists `professionals` under `integrates`; the timeline's demo seed, which
read five modules' models, moved to `app/seeds/`.
`tests/test_app_isolation.py` holds both.

`clinical_notes` attributes a note the same way and labels visit-note
authors with `briefs`; `professionals` is an integration for it too. It
reaches `agenda` through `AppointmentBook`, so `agenda` is an integration
as well; `patients`, `odontogram`, `treatment_plan` and `media` it still
imports and depends on outright.

The Treatments App (`catalog`, `treatment_plan`, `odontogram`,
`periodontogram`) imports only `patients` from outside
(`tests/test_treatments_app_isolation.py`). The attachment-owner registry
is not a contract but follows the same idea: it lives in
`app/core/attachments.py`, so a module registers what can take
attachments without importing `media`.

`agenda` now imports no other module, `TYPE_CHECKING` included. It
keeps its foreign keys — they are why `integrates` still lists
`patients`, `professionals`, `catalog` and `treatment_plan` — and drops
the ORM relationships to their rows. `presenter.py` builds the API
response by asking each directory once per page.

## Consequences

### Good

- The agenda's code, tests and queries stand on their own. What it
  needs from each neighbour is a handful of typed methods in one file.
- One fact instead of two: a link is available exactly when someone
  supplies its contract.
- The reads are batched — one query per directory per page — where the
  ORM walked relationships row by row.
- `treatment_plan` now owns the description of a planned treatment,
  which it was best placed to write: the agenda's schema used to reach
  through three of its neighbours' models to assemble it.

### Bad / accepted trade-offs

- **`appointment.patient`, `.professional`, `.planned_item` and
  `.catalog_item` no longer exist.** Code that used them must ask the
  owner. One place did (`clinical_notes`), and now queries
  `professionals` itself.
- **The response is assembled in Python**, not by the database: a list
  of appointments costs up to three extra queries instead of joins.
- **Contracts are shaped by one consumer.** They hold what the agenda
  calls and nothing else; a second consumer may need to widen them.
- **Only the agenda was converted.** Other modules still import each
  other under `depends`; the isolation tests allow it. This ADR is the
  pattern, not a sweep.
- **`provider()` finds nothing outside a running app.** A seed script
  or a one-off command has no module mounted, so code that may run
  there takes the provider as a parameter — `seed_schedules_demo`
  does, and `scripts/seed_demo.py` hands it over.
- **A contract with two suppliers resolves to the first running one.**
  Nothing prevents declaring two; nothing does today.

## Alternatives considered

- **A stateful provider registry filled at mount.** Needs unregistering
  on unmount and resetting in tests; asking the running modules gives
  the same answer with nothing to keep in step.
- **Composing in the frontend** — the agenda returns ids and the screen
  fetches names. Leaves validation unsolved and makes the calendar ask
  for every patient on it.
- **A local copy kept current by events.** Duplicates personal data and
  goes stale when an event is missed, which a disabled module does by
  definition.

## How to verify the rule still holds

- `backend/tests/test_agenda_integration_matrix.py` —
  `test_agenda_imports_no_other_module` reads the agenda's source, and
  the matrix runs its whole flow with every subset of links off.
- `backend/tests/test_agenda_optional_links.py` — refused, hidden and
  restored links, through the presenter.
- `backend/tests/modules/schedules/test_schedules_professionals_contract.py`
  — schedules imports only `agenda`, works through the directory, has
  nobody to keep hours for when it is absent, and seeds when handed it.

## References

- `backend/app/core/contracts.py`, `backend/app/core/plugins/base.py` (`get_providers`)
- `backend/app/modules/{patients,professionals,treatment_plan,schedules}/providers.py`
- `backend/app/modules/agenda/integrations.py`, `presenter.py`
