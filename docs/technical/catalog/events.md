---
module: catalog
last_verified_commit: 31b940c
---

# Catalog — events

Per-module slice of [`docs/events-catalog.md`](../../events-catalog.md)
(auto-generated). Update both files when adding or removing events.

## Published

This module does not publish any events. The catalog is read through
`GET /api/v1/catalog/*`; changes to it are driven by the clinic, not
broadcast.

## Subscribed

| Event | Handler | Effect |
|-------|---------|--------|
| `clinic.created` | `events.py:on_clinic_created` | Seed the new clinic's baseline catalog — VAT types, treatment categories, catalog items and specialties. |

### Why this is an event and not a call

`/api/v1/auth/setup` lives in core, and core must not import a module
([ADR 0003](../../adr/0003-event-bus-over-direct-imports.md)). The baseline
data a module owns is the module's own responsibility to install, so core
announces the clinic and `catalog` reacts.

The bus awaits handlers inline, so the catalog is queryable before setup
returns its tokens — the first screen the new admin opens is not empty.
The bus also swallows handler exceptions: a seeding failure logs at
`ERROR` and leaves the account intact, recoverable with
`backend/scripts/backfill_catalog_specialties.py`.

`seed_catalog` is idempotent (matches on `key` / `internal_code`), so a
replayed `clinic.created` creates nothing and never overwrites prices or
names the clinic has edited.
