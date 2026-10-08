---
module: catalog
last_verified_commit: 31b940c
---

# Catalog — events

Per-module slice of [`docs/events-catalog.md`](../../events-catalog.md)
(auto-generated). Update both files when adding or removing events.

## Published

| Event | When | Payload |
|---|---|---|
| `catalog.specialty_enabled` | A clinic enables a specialty pack (`POST /specialty-packs/{key}/enable`), or tops one up. | `clinic_id`, `specialty_key`. `treatment_plan` installs and shows the discipline's plan templates. |
| `catalog.specialty_disabled` | A clinic disables a specialty pack. | `clinic_id`, `specialty_key`. `treatment_plan` hides the discipline's reference templates. |
| `catalog.specialty_restored` | A clinic restores a specialty pack to the reference. | `clinic_id`, `specialty_key`. `treatment_plan` puts the discipline's reference templates back. |

Everything else about the catalog is read through `GET /api/v1/catalog/*`.

## Subscribed

| Event | Handler | Effect |
|-------|---------|--------|
| `clinic.created` | `events.py:on_clinic_created` | Seed the new clinic's baseline catalog — VAT types, treatment categories, catalog items and specialties. When the payload carries `specialties` (a clinic created by the control plane, `POST /api/v1/ops/clinics`), leave exactly those disciplines enabled: the baseline ones not listed are disabled, the listed ones beyond the baseline enabled. `general` is always kept. |

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
