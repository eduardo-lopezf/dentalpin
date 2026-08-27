# 0018 — Install state is the authority on what runs

- **Status:** accepted
- **Date:** 2026-08-26
- **Deciders:** Eduardo (maintainer)
- **Tags:** modules, lifecycle, migrations, boot

## Context

DentalPin tracks each module's lifecycle in `core_module.state`. The
[2026-07-03 audit](../technical/audit-2026-07-03.md) found (finding S1)
that **nothing read it**. Four things claimed to know which modules
exist, and they disagreed:

| Plane | Where it lives | Who read it |
|---|---|---|
| Disk — code + manifest | `app/modules/*`, entry points | `loader.discover_modules()` |
| Registry — lifecycle state | `core_module.state` | only the admin UI and the processor |
| Schema | `alembic_version` + per-module branches | `docker-entrypoint.sh`, blindly |
| Runtime — routes, handlers, tools, permissions, jobs | the FastAPI app and three singletons | derived from **disk** |

Concretely, after uninstalling `recalls`: its routes stayed mounted and
returned 500 instead of 404; its event handlers kept firing against
dropped tables with the exception swallowed by the bus; its copilot
tools stayed callable; `recalls.*` stayed granted in `/me`; and the next
restart re-created its schema, because `docker-entrypoint.sh` ran
`alembic upgrade heads` and `heads` walks every branch on disk. This is
issue #56's "cosmetic uninstall" one layer up, and it meant the
per-tenant `modules_enabled` direction of [ADR 0012](0012-multi-tenancy-brief.md)
had no enforcement point.

The registry API encouraged the confusion: `is_loaded()` meant
"discovered" and every caller used it to mean "installed" — including
`migration_import`, which decided whether to import fiscal compliance
data based on it.

## Decision

**`core_module.state` is the single authority on what runs.** Three
invariants:

1. **Mount ⊆ installed.** Discovery only fills the registry. Routers,
   event handlers, copilot tools, permission grants and scheduled jobs
   are given only to modules the database marks `installed`. The boot
   order is therefore `discover → reconcile → process pending → mount`;
   mounting is last and authoritative (it takes down whatever is live
   before mounting the wanted set).
2. **Migrate ⊆ installed.** The Alembic *graph* stays complete —
   `version_locations` lists every branch on disk, which is what makes
   `downgrade` and `history` work — but the *target* comes from the
   registry. Boot upgrades the core linear chain only
   (`resolve_core_head()`); each installed module's branch is brought to
   its head by `PendingProcessor`. A module whose branch cannot reach
   head is not mounted: its code moved and its tables did not.
3. **Uninstall takes effect immediately for HTTP, and symmetrically at
   the next boot.** Transitions are restart-based, so `uninstall` closes
   `module_gate` for that module — every `/api/v1/<name>/…` request
   answers `409` instead of writing into tables about to be dropped —
   and the processor's `unmount` step takes handlers off the bus and
   tools out of the registry *before* deleting data.

The registry now says which fact it is answering: `is_discovered()` /
`list_discovered()` for the disk inventory (the lifecycle processor and
the admin UI need it), `is_installed()` / `list_modules()` for the
active set (everything else).

## Consequences

### Good

- Uninstall is real: schema, routes, handlers, tools, permissions and
  nav all go, and stay gone across restarts.
- `modules_enabled` (ADR 0012) and any future per-module licensing have
  a single enforcement point instead of none.
- Installing a module goes live on the same restart that schedules it —
  the processor now runs *before* mounting, where it used to run after.
- A module never reachable through its own routes can no longer be
  reached through its copilot tools or its event handlers either.

### Bad / accepted trade-offs

- **Modules with `auto_install=False` that were reachable become 404
  until installed.** On any existing database, `verifactu`,
  `periodontogram`, `accounting_export`, `migration_import` and
  `whatsapp_kapso` were live while `core_module` said `uninstalled`.
  Deploying this makes them 404 until an admin installs them. That is
  the fix behaving correctly, and it needs saying out loud in the
  release notes.
- **Bootstrap still runs `alembic upgrade heads`.** On a database with
  no `core_module` table nothing can have been uninstalled, so the
  entrypoint creates the whole schema in one pass. A module you never
  install therefore has empty tables. Removing this carve-out means
  routing every auto-installed module through the processor's own
  migration step — ~18 Alembic subprocesses at ~5.7 s each on a first
  boot — so it stays until that cost is addressed.
- Catch-up migrations cost one Alembic subprocess per module whose
  branch actually advanced. A normal boot runs none.
- `mount_active` unmounting the live set first makes a second boot in
  one process legal; it also means calling it twice on the same app
  object would include its routes twice. Nothing does.

## Alternatives considered

- **Make `discover_version_locations` read the database** so
  `upgrade heads` only sees installed branches. Rejected twice over: it
  runs during Alembic bootstrap when `core_module` may not exist and in
  offline (`--sql`) mode with no connection, and on any database where an
  uninstalled module is still *stamped* (every database that predates
  this ADR) hiding its directory makes Alembic fail to resolve the
  revision in `alembic_version`.
- **One Alembic command with an explicit list of branch heads.**
  Alembic's CLI takes a single revision; `upgrade a,b` is parsed as one
  revision id and fails.
- **`<module>@head` as the migration target.** Only 11 of 22 branches
  declare `branch_labels`, so `alembic upgrade patients@head` fails with
  "Can't locate revision identified by 'patients'". Targets are branch
  head *revision ids*. Giving every branch a label is worth doing, but
  it edits 11 migration files and is a separate change.
- **Gate at the router with a dependency per module.** Same behaviour
  spread over 22 modules, and it would not have stopped the handlers,
  the tools or the jobs — which is where the real damage was.

## How to verify the rule still holds

- `backend/tests/test_module_state_gating.py` — mounting, registry
  semantics, permissions, `modules_enabled`, and the boot order.
- `backend/tests/test_boot_migration_targets.py` — the core head, the
  entrypoint's shape, catch-up migrations, and that an uninstalled
  branch is never migrated.
- `backend/tests/test_module_gate.py` — the uninstall window and the
  unmount symmetry.
- `backend/tests/test_module_restart_roundtrip.py` (marked
  `alembic_roundtrip`) — install → uninstall → restart → restart →
  reinstall, with real migrations and a real `pg_dump`.

## References

- `backend/app/main.py` — boot order, mount set, gate middleware
- `backend/app/core/plugins/loader.py` — `discover_and_register`,
  `mount_active`, `unmount_module`
- `backend/app/core/plugins/registry.py` — discovered vs installed
- `backend/app/core/plugins/gate.py` — the uninstall window
- `backend/app/core/plugins/processor.py` — `_migrate_installed`, the
  `unmount` step
- `backend/app/core/plugins/alembic_paths.py:resolve_core_head`
- `backend/docker-entrypoint.sh` — core chain vs bootstrap
- [`docs/technical/audit-2026-07-03.md`](../technical/audit-2026-07-03.md) — finding S1
- [ADR 0002](0002-per-module-alembic-branches.md) — branches; this ADR
  amends its "`alembic upgrade heads` is the canonical command" note:
  canonical by hand, never at boot
- [ADR 0012](0012-multi-tenancy-brief.md) — `modules_enabled`
- Issue #56
