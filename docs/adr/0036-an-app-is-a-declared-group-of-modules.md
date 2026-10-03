# 0036 — An App is a declared group of modules

- **Status:** accepted — the catalog moved from code to `backend/apps.json`, and `enabled` now takes effect ([ADR 0038](0038-apps-json-switches-apps-for-the-whole-deployment.md))
- **Date:** 2026-09-30
- **Deciders:** Eduardo (maintainer)
- **Tags:** modules, apps, tenancy

## Context

What a clinic chooses and what the code is made of are different
grains. "Agenda" to a clinic is appointments *and* working hours; in the
code those are two modules, `agenda` and `schedules`, with their own
versions, routes, permissions and Alembic branches, and eight other
modules import the first one.

Giving the clinic-facing unit a home needed one of three things: a new
module built in parallel (two sets of appointment tables and a data
migration to retire the old one), folding `schedules` into `agenda`
(routes, permissions and two migration chains move at once), or naming
the group without touching either.

## Decision

**An App is an entry in a declarative catalog that names the modules it
groups. It owns nothing at runtime.**

- The catalog is `APP_CATALOG` in `backend/app/core/plugins/apps.py`:
  `name`, `version`, `modules`, `enabled`.
- An App has **its own version**, independent of its modules'. Agenda
  is App `0.1` over module `agenda` `0.4.0`.
- A module belongs to at most one App.
- What an App *requires* is not declared: it is computed from its
  modules' `depends`, transitively, so it cannot drift from them.
- `core_module.state` still decides what runs
  ([ADR 0018](0018-install-state-is-the-mount-authority.md)). An App
  with `enabled=False` is listed and changes nothing; its modules keep
  the state they have.

The first entry is **Agenda v0.1** = `agenda` + `schedules`, created
disabled.

## Consequences

### Good

- No duplicated code, no second set of tables, nothing to migrate.
- Decoupling `agenda` from `patients`, `catalog`, `odontogram` and
  `professionals` can happen in place, import by import; the App's
  `requires` shrinks as it does, and that is the measure of progress.

### Bad / accepted trade-offs

- **`enabled` lives in code, so it is the same for every tenant.** It is
  a placeholder. Choosing Apps per tenant needs that flag stored per
  database, and enabling an App to mean enabling its modules; neither
  exists yet.
- **Settings → Apps shows two layers**, the catalog and the module list,
  until every module belongs to an App.
- An App's title and summary are i18n strings in the frontend, keyed by
  name; a catalog entry without them shows its bare name.

## Alternatives considered

- **A new module in parallel** — about 5,200 lines of Python and 9,200
  of frontend copied, appointments living in two sets of tables, and
  eight modules to repoint before the old one could go.
- **Merging `schedules` into `agenda`** — no coexistence and no
  duplication, but routes and permissions change at once and both
  migration chains are touched.

## How to verify the rule still holds

- `backend/tests/test_app_catalog.py` — every catalog module exists and
  belongs to one App, `requires` is the outside dependency closure, and
  a disabled App leaves its modules running.
- `frontend/tests/e2e/settings-apps.spec.ts` — Agenda v0.1 is listed as
  disabled.

## References

- `backend/app/core/plugins/apps.py`, `backend/app/core/plugins/router.py` (`GET /api/v1/apps`)
- `frontend/app/components/settings/modules/AppCard.vue`
- [ADR 0035](0035-apps-are-disabled-not-uninstalled.md) — what enabling and disabling mean
