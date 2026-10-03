# 0043 — The workspace is the base App, and every App has a tier

- **Status:** accepted
- **Date:** 2026-10-03
- **Deciders:** Eduardo (product owner)
- **Tags:** modules, apps

## Context

The App catalog (`backend/apps.json`,
[ADR 0036](0036-an-app-is-a-declared-group-of-modules.md),
[0038](0038-apps-json-switches-apps-for-the-whole-deployment.md)) listed
Apps that each group modules. What every workspace runs on — the clinic,
its users, roles and permissions, sign-in, the shell with its home page
and widgets, settings, privacy requests — was not in it, because it is
not a module: it is the core (`backend/app/core/`) and the host frontend
(`frontend/app/`). The product names that layer "Espacio de trabajo"
(workspace) and wants it encapsulated as an App, never disabled, and the
place where the interface is customised.

Separately, the product has named its **core Apps** — set up for every
workspace: Agenda, Patients, Recalls and Treatments. Nothing in the
catalog said so.

## Decision

**`apps.json` declares a `workspace` App with tier `base` and no
modules, and every App carries a tier: `base`, `core` or `optional`.**

- `base` is the core and the shell, not a group of modules. It lists
  none, it opens the catalog, and the loader refuses it disabled. There
  is exactly one.
- `core` Apps are the ones every workspace is set up with. Today:
  `agenda`, `patients`, `recalls`, `treatments`. They can still be
  switched off in the file, so the rule that no App breaks another while
  it is off ([ADR 0037](0037-a-module-integrates-with-what-it-can-live-without.md))
  keeps being exercised.
- `optional` is the default when `tier` is left out, and for now it
  means "not yet classified": the screen labels these "App opcional".
  Since 2026-10-03 every module belongs to an App, so the optional ones
  are Budgets & payments, Cash desk, Communications, Professionals,
  Clinical record, Reports, AI and Data migration; `professionals` is meant to be core
  for workspaces of the Clinic kind, which the catalog cannot yet
  express. Classifying them is pending (`docs/technical/todos.md`).
- Every App other than the base groups at least one module.
- `GET /api/v1/apps` returns `tier`; Settings → Apps shows the base App
  first, marked "App principal · Siempre habilitada", and core Apps with
  a badge; optional Apps carry an outlined one.

No code moved. What the workspace contains is described, not enforced:
the core keeps living in `app/core/` and the shell in `frontend/app/`.
Extracting parts of the host frontend into a module is left for when it
pays off.

The Settings category that was called "Espacio de trabajo" (cabinets,
opening hours, data migration) is now labelled "Clínica y horarios", so
the name means one thing. Its id and URLs (`/settings/workspace/…`) stay,
so links and other modules' registrations keep working.

## Consequences

### Good

- The catalog describes the whole product: one base, the core Apps, the
  optional ones.
- Customising the interface (which widgets the home page shows, menu
  order, branding) has an owner, and it is per clinic, not in this file.
- Under [ADR 0042](0042-core-apps-must-stay-separable.md) the base App is
  what would stay as the platform if core Apps leave the process.

### Bad / accepted trade-offs

- The base App's contents are a description in i18n, not a module list
  the code can check.
- The Settings category id `workspace` now differs from its label and
  shares a word with the App. Renaming it means changing URLs.

## Alternatives considered

- **A `workspace` module** holding the host's own pages — real
  encapsulation, but auth, tenancy and permissions cannot be a module that
  could be switched off, so it would encapsulate only part, at a high cost.
- **Leave the core out of the catalog** — the product's main App would be
  the one thing the Apps screen does not show.

## First customisation: the home page

Settings → Apps → **Espacio de trabajo** (`/settings/apps/workspace`) is
the workspace App's own page; it is also reached from the *Configurar*
button on the App's card. Its first section, *Inicio*, chooses which
widgets the home page shows and their order, for the whole clinic. Stored in
`clinic.settings.home_layout` as `{hidden: [ids], order: [ids]}` through
`GET`/`PUT /api/v1/auth/clinic/settings/home`: reading needs only a
clinic membership, since every member's home page reads it; writing needs
`admin.clinic.write`.

- A widget keeps the area of the page its App registered it in; the order
  applies within the area. Moving widgets between areas is not offered.
- A widget the layout does not mention is shown, after the ordered ones,
  so one added by a newly enabled App appears instead of staying hidden.
  Unknown ids are ignored, so a removed App leaves no trace.
- The home page draws nothing until the layout is known, so a hidden
  widget never flashes in. `useHomeLayout()` holds it; `arrangeEntries`
  is the rule.

## How to verify the rule still holds

- `backend/tests/test_app_catalog.py` — the base App cannot be disabled,
  there is one, only it may group no modules, the shipped catalog opens
  with it and names the four core Apps.
- `frontend/tests/e2e/settings-apps.spec.ts` — the workspace card comes
  first, marked as the main App and always enabled.
- `backend/tests/test_home_layout.py`, `frontend/tests/home-layout.test.ts`,
  `frontend/tests/e2e/settings-home.spec.ts` — the home layout is saved,
  read by everyone, written only by an admin, and drawn as chosen.

## References

- `backend/apps.json`, `backend/app/core/plugins/apps.py` (`AppTier`)
- `frontend/app/components/settings/modules/AppCard.vue`
