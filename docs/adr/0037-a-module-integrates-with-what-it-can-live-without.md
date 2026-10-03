# 0037 — A module integrates with what it can live without

- **Status:** accepted — for `agenda`, the imports this ADR allowed were later removed in favour of core contracts ([ADR 0039](0039-modules-reach-each-other-through-core-contracts.md)); the availability check is now "does anyone supply the contract"
- **Date:** 2026-10-01
- **Deciders:** Eduardo (maintainer)
- **Tags:** modules, apps, dependencies, agenda

## Context

`depends` is all or nothing: enabling a module enables everything it
lists, and none of them can be disabled while it runs
([ADR 0035](0035-apps-are-disabled-not-uninstalled.md)). That fits a
module that cannot work without another. It does not fit Agenda, which
by default links to patients, professionals, the catalog and the
odontogram but has to keep working when a clinic runs without any one
of them.

The only escape was the allowlist: `agenda` already reached into
`treatment_plan` (a foreign key and an import) and `schedules` (an
import) without declaring either, because both depend on `agenda` and a
`depends` in the other direction would be a cycle. Both sat in the
isolation tests as known violations.

Two facts make an optional link cheap. A disabled module keeps its
tables and every database carries the whole schema (ADR 0035), so a
foreign key into an optional module is always valid. And its code is
still on disk, so importing its models still works. What goes when a
module is disabled is what it *mounts*: routes, permissions, screens.

## Decision

**A manifest declares `integrates`: modules it links to when they run
and does without when they do not.**

For the core, `integrates` grants what `depends` grants and demands
nothing:

| | `depends` | `integrates` |
|---|---|---|
| Imports and foreign keys allowed | yes | yes |
| Pulled in by `enable` | yes | no |
| Blocks `disable` of the target | yes | no |
| Blocks `uninstall` of the target | yes | yes |
| Orders boot and migrations | yes | no |

A name in both lists is a manifest error. `integrates` takes no part in
ordering, which is what lets two modules integrate with each other, or
one integrate with a module that depends on it.

For the module that declares it, `integrates` is a promise about
behaviour. While an integrated module is **disabled**:

1. **The module keeps working**, with that part of its functionality
   absent. Nothing it requires may come from an integration: an
   appointment can be created with no patient and no professional.
2. **Nothing of the disabled module is offered.** Its records are not
   listed or selectable, and the screen says why — "no se pueden
   asignar pacientes" — instead of showing an empty picker.
3. **Nothing is written to it**, and no new link to its records is
   accepted.
4. **Nothing is deleted.** Existing links and records stay in the
   database, and show again as soon as the module is enabled.

The check is `module_registry.is_installed(name)` on the backend and
the active-module list on the frontend.

## Consequences

### Good

- Agenda can run with any subset of the apps it links to, and enabling
  one later restores the links with no migration and no backfill.
- The two tracked violations become declarations, and the allowlists
  for `agenda` are empty.

### Bad / accepted trade-offs

- **The promise is not enforced by the core.** `integrates` makes the
  import legal; whether the module really degrades is down to its own
  guards and to a test per combination.
- **Columns that point at an integration must be nullable.**
  `appointments.professional_id` became so in `ag_0007`.
- **An appointment with no professional is outside the slot index.**
  `idx_appointment_slot` includes `professional_id`, and NULLs never
  collide: two unassigned appointments can share a time. There is
  nobody to double-book.
- **The API cannot take a professional or a patient off an
  appointment.** Updates ignore `null`, as they always have.
- **`uninstall` now looks wider than `disable`.** It is blocked by any
  module that still has tables — enabled or disabled — and lists the
  target in either field, since either may hold foreign keys into the
  tables about to be dropped.
- A link written while a module was enabled stays hidden, not removed,
  while it is disabled. Reports that count by professional or patient
  see those rows as unassigned for that period.

## Rollout

1. **Done:** the manifest field, its validation, the lifecycle rules,
   the isolation tests and the catalog column. `agenda` declares
   `integrates: [treatment_plan, schedules]`, which changes no
   behaviour: neither was in `depends`.
   Also done: Agenda follows rules 1–4 for planned treatments, which
   belong to the Treatments App (ADR 0038).
2. **Done:** `agenda.depends` is empty; `patients`, `professionals`,
   `catalog` and `odontogram` joined `integrates`, and `schedules`
   moved `professionals` there too. `ag_0007` makes
   `appointments.professional_id` nullable and adds `title`. The agenda
   follows rules 1–4 for patients and professionals through
   `integrations.py`, and the day view gained an unassigned column.
   While Professionals runs, a professional is still required: the
   default behaviour is unchanged.

The modules that read appointments (`notifications`, `reports`,
`clinical_notes`, `patient_timeline`, `recalls`, `copilot`, `payments`)
were checked for step 2: all already handle an appointment without a
patient or a professional. The exception is `agenda` itself, which
publishes `str(appointment.professional_id)` in three event payloads.

## Alternatives considered

- **Contracts in the core** (interfaces that `patients` and
  `professionals` implement) — removes the imports as well, but is not
  needed for this goal and changes how every read is made.
- **Dropping the foreign keys** — makes Agenda independent in schema
  too, and gives up the database's guarantee that an appointment's
  patient exists.
- **Keeping `professionals` as the one hard dependency** — cheaper, and
  rejected: no dependency of Agenda is to be mandatory.

## How to verify the rule still holds

- `backend/tests/test_module_manifest.py` — parsing, and the
  both-lists error.
- `backend/tests/test_module_install_flow.py` — an integration does not
  block `disable` and does block `uninstall`.
- `backend/tests/test_agenda_optional_links.py` — booking with each
  App off, refused links, and stored links hidden and restored.
- `backend/tests/test_module_isolation.py`,
  `backend/tests/test_module_fk_isolation.py` — imports and foreign
  keys must target `depends` or `integrates`.

## References

- `backend/app/core/plugins/manifest.py`, `service.py`, `manifest_validator.py`
- `backend/app/modules/agenda/__init__.py`
- [ADR 0003](0003-event-bus-over-direct-imports.md), [ADR 0035](0035-apps-are-disabled-not-uninstalled.md), [ADR 0036](0036-an-app-is-a-declared-group-of-modules.md)
