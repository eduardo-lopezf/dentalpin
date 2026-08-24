# Catalog module

Treatment catalog, categories, VAT types. Foundational pricing source
of truth for budgets and billing.

## Public API

Routes mounted at `/api/v1/catalog/`.

## Dependencies

`manifest.depends = []`. Foundational.

## Permissions

`catalog.read`, `catalog.write`, `catalog.admin`.

## Tools exposed

Agent tools in `tools.py` (wrap `CatalogService`, no logic duplicated).

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_catalog_items` | READ | `CatalogService.list_items` | `catalog.read` |
| `get_catalog_item` | READ | `CatalogService.get_item` | `catalog.read` |

Both filter by `ctx.clinic_id`. `names`/`descriptions` are localized
JSONB; the tools collapse to `es` → `en` → first value for the agent.

## Events emitted

None.

## Events consumed

| Event | Handler | Effect |
|---|---|---|
| `clinic.created` | `events.py:on_clinic_created` | Seed the new clinic's baseline catalog: VAT types, categories, items, specialties. |

Payload consumed: `clinic_id` (required), `created_by`, `name`. Published by
core's `/api/v1/auth/setup` after it commits the clinic — core must not
import a module (ADR 0003), so the module installs its own baseline data.

The bus awaits handlers inline, so the catalog is queryable before setup
returns. It also swallows handler exceptions: a failure logs at `ERROR`
and leaves the account intact — recover with
`backend/scripts/backfill_catalog_specialties.py`.

See `docs/technical/catalog/events.md`.

## Lifecycle

- `removable=False`. Budget, billing, odontogram, treatment_plan all
  depend on this.

## Gotchas

- **`seed_catalog` is the only code that creates baseline data**, and it is
  idempotent by design (matches on `key` / `internal_code`, backfills missing
  specialty links and `default_phase`, never overwrites clinic-edited prices
  or names). Call it freely; do not add a second seeding path.

- **Session template** (``CatalogItemSession``) is optional per item;
  when present, the sum of ``default_price`` across sessions must
  equal the item's ``default_price`` (tolerance ±0.01). PUT
  ``/items/{id}`` with ``sessions`` (list, even empty) replaces the
  template atomically via ORM ``item.sessions.clear()`` + re-append;
  omitting the key preserves the existing template. Consumers
  (treatment_plan) snapshot this template at plan-add time.
- **Specialty assignment is many-to-many** — ``catalog_item_specialties``
  links treatments to ``Specialty``. ``PUT /specialties/{id}/items`` is a
  full replace, not a merge: the payload is the complete set. Item
  responses embed the specialties, so any new query returning a
  ``TreatmentCatalogItem`` must ``selectinload`` the relationship or the
  async session raises on lazy load. Specialties are soft-deleted
  (``is_active``), which leaves existing assignments intact on purpose.
- **VAT types are versioned** — when changing a VAT rate, create a new
  version rather than mutating in place. Historical invoices must
  reproduce their original VAT.
- **Pricing rules live in `pricing.py`** — keep service code thin and
  delegate calculations there.
- **Seed data** is shipped via `seed.py` and idempotent — re-running it
  must not duplicate categories.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`

## CHANGELOG

See `./CHANGELOG.md`.
