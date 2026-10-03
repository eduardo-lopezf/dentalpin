# 0044 — The App organises; the module holds the code

- **Status:** accepted
- **Date:** 2026-10-03
- **Deciders:** Eduardo (product owner)
- **Tags:** modules, apps, repository layout

## Context

The product is now described as Apps — one base, four core, eight
optional ([ADR 0043](0043-the-workspace-is-the-base-app.md)) — while the
repository is laid out by module: 26 folders side by side under
`backend/app/modules/`, each with its Python, its migrations, its Nuxt
layer and its notes. An App existed only as an entry in `apps.json`.
Tests, docs and the host frontend followed no App at all: half the tests
sat in one flat folder, the host carried components that belong to other
Apps, and thirteen modules belonged to no App.

The question was whether the directory tree should be rebuilt around
Apps.

## Decision

**The module stays the unit of code and stays where it is. The App is
the organising layer over it, made visible by generated and per-App
artefacts rather than by moving folders.**

1. **Modules stay flat** in `backend/app/modules/<module>/`. Nothing is
   nested under an App folder.
2. **Every module belongs to exactly one App** in `backend/apps.json`
   (`test_every_module_belongs_to_an_app`).
3. **Each App has a folder of its own for what is the App's, not a
   module's:** `docs/apps/<app>/README.md` (what it is for, what happens
   with it off) and `CHANGELOG.md` (the App's version).
4. **What an App is made of is generated**, not written:
   `docs/apps-catalog.md`, from `apps.json` and the manifests, checked in
   CI like the other catalogs.
5. **One rule says what every App may reach into:**
   `backend/tests/test_app_isolation.py` pins, per App, the other Apps
   its code imports and the ones it requires. The tables only shrink.
6. **Tests are looked at by App without being moved:** every test carries
   an `app_<name>` marker derived from the modules its file touches, so
   `pytest -m app_agenda` is the Agenda suite.
7. **The base App owns no other App's code.** The host frontend
   (`frontend/app/`) holds the shell and what is truly shared; a component
   or composable that belongs to an App lives in that App's layer.

## Consequences

### Good

- A module that changes App — it has happened three times — is a
  one-line edit to `apps.json`, not a move of folders and import paths.
- The repository can be read by App (catalog, per-App docs, per-App test
  run) without the cost of a reorganisation: 616 imports in 216 files and
  the migration, entry-point and Docker paths stay as they are.
- When a core App is extracted to its own container
  ([ADR 0042](0042-core-apps-must-stay-separable.md)) it becomes its own
  package — the entry-point registry already takes modules from outside
  `app/modules/` — and that is the moment its code moves.

### Bad / accepted trade-offs

- The tree does not show the Apps. Someone browsing `app/modules/` sees 26
  siblings and has to open the catalog to learn which belong together.
- The markers are derived from imports, so a test that touches many
  modules belongs to many Apps; `app_workspace` is the residue, not a
  curated set.
- Not finished, and named so it is not mistaken for done:
  - `frontend/app/types/index.ts` still declares the types of nearly
    every module.
  - `frontend/app/pages/finanzas.vue` (the page that hosts the Budgets &
    payments tabs) is still in the host.
  - `docs/technical/` still mixes per-module folders with loose
    module-specific files; `docs/modules/` is where those belong.

## Alternatives considered

- **Nest modules under Apps** (`app/apps/<app>/<module>/`) — the tree
  would show the Apps, at the price of rewriting every import path and of
  making "which App is this module in" a matter of where a folder sits.
- **One package per App now** — the right shape for an extracted App and
  premature for the rest.

## How to verify the rule still holds

- `backend/tests/test_app_catalog.py`, `backend/tests/test_app_isolation.py`.
- `python backend/scripts/generate_catalogs.py --check` — the Apps catalog
  is fresh and every App has its `docs/apps/<app>/` folder.
- `frontend/tests/app-frontend-isolation.test.ts`.

## References

- `backend/apps.json`, `docs/apps-catalog.md`, `docs/apps/`
- `backend/tests/conftest.py` (per-App markers)
