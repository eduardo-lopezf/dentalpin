# Migración de datos (`data_migration`)

- **Tier:** optional  ·  **Version:** 0.1
- **Declared in:** `backend/apps.json`  ·  **Composition and requirements:** [Apps catalog](../../apps-catalog.md)

## What it is for

Imports patients, appointments, budgets, payments and documents from another program (a DPMF file).

## Modules

- [`migration_import`](../../technical/migration_import/overview.md) — code in `backend/app/modules/migration_import/` ([notes](../../../backend/app/modules/migration_import/CLAUDE.md))

## With this App off

Not verified.

## Notes

- Requires nearly every clinical and financial App, by nature. The `migration_import` module is not installed by default.
