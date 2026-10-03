# 0035 — Apps are disabled, not uninstalled, and every database carries the whole schema

- **Status:** accepted
- **Date:** 2026-09-30
- **Deciders:** Eduardo (maintainer)
- **Tags:** modules, lifecycle, migrations, tenancy

## Context

A tenant is a database ([ADR 0012](0012-multi-tenancy-brief.md)), and
the plan is to pick, when a tenant is created, which apps it runs. That
makes "is this app on?" a per-tenant fact that will be changed far more
often than modules were ever installed or removed.

The only way to turn a module off was `uninstall`: a `pg_dump`, an
Alembic downgrade and dropped tables. That is the wrong tool for a
routine switch.

- Most modules cannot use it at all — 16 of 26 are `removable=False`,
  because cash counts, invoices and clinical entries are records the
  clinic is obliged to keep.
- It makes the schema differ between tenants, so a foreign key that is
  valid in one database has no target in another, and enabling an app
  later means running migrations against live data.
- `ModuleState.DISABLED` already existed for this and did nothing:
  nothing set it and nothing read it.

## Decision

**Turning an app off never touches its tables. `disabled` is a mount
decision; the schema is the same in every database.**

1. **Mount ⊆ enabled.** Unchanged from [ADR 0018](0018-install-state-is-the-mount-authority.md):
   only `installed` (shown to users as *enabled*) gets routes, event
   handlers, tools, permissions, jobs and navigation.
2. **Migrate ⊆ enabled ∪ disabled.** This amends ADR 0018's second
   invariant. A disabled module's branch is brought to head at boot like
   an enabled one, so its tables never fall behind the modules that
   reference them. Only `uninstalled` branches are skipped.
3. **A module that was never enabled is `disabled`, not `uninstalled`.**
   `auto_install=False` modules start there, and reconcile moves rows
   left `uninstalled` by older versions across.
4. **Enabling pulls dependencies in; disabling refuses while something
   depends on it.** `enable` is the install flow (migrate, a no-op here,
   then seed and the `install` hook). `disable` has no `force`: the
   refusal is what keeps the running set coherent, since a dependent
   imports the module it depends on.
5. **Nobody turns an app off from the interface.** Settings → Apps is
   read-only. `disable` is a CLI command, and there is no `disable` or
   `uninstall` route.

`uninstall` stays, on the CLI only, for the case it was built for:
removing a module for good, tables included.

## Consequences

### Good

- Disabling loses nothing and is undone by enabling. `removable` stops
  being a reason an app cannot be switched off.
- Foreign keys are valid in every tenant database, whichever apps it
  runs, and enabling an app later needs no migration.
- The dependency rule already written for `uninstall` is the only one;
  `disable` reuses it.

### Bad / accepted trade-offs

- **Empty tables.** A tenant carries the tables of apps it never uses.
- **A disabled module hears no events.** `patient_timeline` consumes 35
  of them; switched off for a month and back on, its history has a
  month-long hole. No foreign key is broken, but derived data is
  incomplete, and nothing backfills it.
- **A module that first ships in a later image is recorded at head
  without its tables being created**, on databases that already existed.
  This is how reconcile has always treated `auto_install` modules; it
  heals when the module is enabled or its branch gains a revision.
  Until then that one module's tables are missing.
- **Enable and disable need a restart**, like every other transition.
  Between a `disable` and the restart `module_gate` answers `409`.
- **The interface can no longer install, upgrade or apply changes.**
  `upgrade` and `restart` remain as routes and CLI commands.

## Alternatives considered

- **Create an app's tables the first time it is enabled.** Saves the
  empty tables, but keeps two migration paths and puts a schema change
  behind a routine switch.
- **Make `removable=False` block `disable` too.** The flag protects
  data, and disabling loses none.
- **Filter per request instead of at mount.** Needed once one process
  serves several tenants with different selections; `TenantContext.modules_enabled`
  is the place for it. Not needed while a process serves one tenant.

## How to verify the rule still holds

- `backend/tests/test_module_install_flow.py` — the enable/disable
  transitions, the dependency block, and the reconcile rules.
- `backend/tests/test_boot_migration_targets.py` — a disabled branch is
  migrated, an uninstalled one is not.
- `frontend/tests/e2e/settings-apps.spec.ts` — the screen offers nothing
  that turns an app on or off.

## References

- `backend/app/core/plugins/service.py` — `enable`, `disable`, `reconcile_with_db`
- `backend/app/core/plugins/processor.py` — `_migrate_installed`
- `backend/app/core/plugins/router.py` — `/enable`; no `/disable`, no `/uninstall`
- `frontend/app/pages/settings/apps/index.vue`
- [ADR 0018](0018-install-state-is-the-mount-authority.md) — amended here
