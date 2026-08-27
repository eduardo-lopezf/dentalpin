# 0021 — Module layers are typechecked, behind a shrinking baseline

- **Status:** accepted
- **Date:** 2026-08-26
- **Deciders:** Eduardo (maintainer)
- **Tags:** frontend, ci, modules, types

## Context

Each module ships a Nuxt layer under
`backend/app/modules/<name>/frontend`, and the backend writes
`frontend/modules.json` at runtime with the paths where the frontend
container mounts them (`/module_layers/<name>/frontend`). Those paths
exist only inside that container.

CI had no container and no database, so the `frontend-typecheck` job
stubbed an empty `modules.json` — and then ran `nuxi prepare`, not a
typecheck. Its own comment claimed it "guards against broken Vue/TS
imports across module Nuxt layers"; it did neither. `npm run lint` has
the same blind spot from the other direction: ESLint derives its base
path from the config file's location, so a config inside `frontend/`
cannot lint files above it.

The result, measured the first time anyone looked: **303 type errors**
across the layers, invisible behind a green build — including 109 Nuxt
UI **v2** colour tokens (`'green'`, `'red'`) on v4 components, which
render as no colour at all, and imports of packages and composables that
resolve at runtime but had never been checked.

## Decision

**CI typechecks the host and every module layer, and fails on any error
the baseline does not already know about.**

Three pieces:

1. `frontend/scripts/write-module-layers.mjs` writes a manifest with
   repo-relative layer paths, and links `frontend/node_modules` into the
   modules root — Node resolves bare imports by walking *up* from the
   importing file, and a layer never reaches the host's packages
   otherwise.
2. `nuxt.config.ts` reads `process.env.DENTALPIN_MODULES_JSON` when set,
   so CI points at that manifest while a developer's real `modules.json`
   (written by their running backend) is left alone.
3. `frontend/scripts/typecheck-gate.mjs` runs the typecheck and compares
   it against `frontend/typecheck-baseline.json`. New errors fail the
   build; the baseline shrinks as the backlog is worked off.

Errors are keyed by file + code + message, without line numbers, so
editing above an error does not churn the baseline — but the *count* per
key is part of it, so a new occurrence of a known error still fails.

## Consequences

### Good

- A type error in module code now fails CI on the commit that adds it.
- The backlog is visible and countable instead of hypothetical. It went
  303 → 194 while writing this ADR (colour tokens migrated, imports
  fixed, patient update types corrected).
- The manifest generator also makes `nuxt typecheck` runnable from a
  plain checkout, with no backend and no container.

### Bad / accepted trade-offs

- **194 known errors are frozen, not fixed.** A baseline is a promise to
  come back, and promises rot. It is checked in precisely so its size is
  visible in review.
- **Lint still does not cover the layers.** Making it work means moving
  the ESLint config to the repo root, and the Nuxt-generated config's
  parser and file patterns do not survive the move — every config object
  would need remapping. Typecheck catches the class that matters (types,
  imports, component props); lint would add style and unused-symbol
  coverage. Left open deliberately rather than half-done.
- The `node_modules` symlink at the modules root is a build artifact in
  the source tree. It is gitignored, and nothing reads it at runtime.
- CI now typechecks all 23 layers, while a given deployment runs only the
  installed subset. Checking everything that *ships* is the right set —
  any of them can be installed ([ADR 0018](0018-install-state-is-the-mount-authority.md)).

## Alternatives considered

- **Turn the gate on with zero tolerance.** Either CI is red until 194
  errors are fixed, or the fixes land as one unreviewable commit. The
  baseline gets the guarantee today and spreads the cleanup.
- **Let CI run the containers and use the real `modules.json`.** Much
  slower, and it ties a type check to a database and an install state.
- **`paths: { '*': [...] }` in `typescript.tsConfig`** to solve package
  resolution. Tried: it replaces Nuxt's own path mappings instead of
  merging, and errors went 229 → 998.
- **Give each layer its own `package.json` + workspaces.** The real
  monorepo answer, and a much larger change to how modules are built and
  shipped.

## How to verify the rule still holds

- `frontend/scripts/typecheck-gate.mjs` — exits 1 on a new error
  (verified by injecting one), 0 on a clean tree.
- `.github/workflows/ci.yml`, job `frontend-typecheck`.
- `frontend/typecheck-baseline.json` — the backlog; it should only ever
  get smaller.

## References

- `frontend/scripts/write-module-layers.mjs`
- `frontend/scripts/typecheck-gate.mjs`
- `frontend/nuxt.config.ts` — `DENTALPIN_MODULES_JSON`
- [`docs/technical/audit-2026-07-03.md`](../technical/audit-2026-07-03.md) — finding S5, "CI blind spot"
