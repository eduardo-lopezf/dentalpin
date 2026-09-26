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

- **The management screen has to offer both halves of a soft delete.** The bin
  is drawn on every row, `is_system` included — hiding it there is what made
  the delete unreachable on a fresh clinic, where the whole catalog is seeded —
  and `Mostrar inactivos y eliminados` loads `include_deleted=true` so a
  removed or deactivated treatment can be found and restored. A removed row
  keeps its `internal_code` reserved, so "create it again" is not a workaround.

- **Seeded treatments can be removed, and the removal is reversible.** A
  clinic does not offer everything the starter catalog ships; refusing to
  delete `is_system` items left ~130 of them in every picker for good.
  `DELETE /items/{id}` now accepts them (still gated by `catalog.write`, i.e.
  admin). The delete is **soft** because performed treatments, budget lines
  and plan-template lines all point at the row. `GET /items?include_deleted=true`
  finds it again — that flag also drops the default `is_active=True` filter,
  since a deleted item is inactive by construction — and `PUT` with
  `is_active: true` clears `deleted_at` and restores it. `get_item` takes
  `include_deleted` for exactly that path. Re-seeding does not resurrect a
  deleted item: `seed_catalog` matches on `internal_code` **regardless of
  `deleted_at`**, finds the row and skips it.
- **`internal_code` stays locked on seeded items.** It is the key the seeder
  matches on. Deleting is safe precisely because that match still finds the
  row; renaming breaks it, and the next seed run recreates the original
  alongside the renamed one.
- **`seed_catalog` is the only code that creates baseline data**, and it is
  idempotent by design (matches on `key` / `internal_code`, backfills missing
  specialty links and `default_phase`, never overwrites clinic-edited prices
  or names). Call it freely; do not add a second seeding path.

- **`MAX_PAGE_SIZE` is the one page-size bound.** `service.py` owns it; the
  router uses it as the `le` on `/items` and the service clamps to it. They
  used to disagree — `le=500` on the route, a silent clamp to 100 in the
  service, and the envelope echoing back the 500 that was asked for — so a
  caller was handed a subset and told it was everything. Never raise one
  without the other, and never let a screen ask for "all of it" in one page:
  page until the set is exhausted (`useCatalog.loadAllItems` /
  `fetchAllItems`).

- **Writing an item does not refresh any list.** `createItem` / `updateItem` /
  `deleteItem` return and stop there. They used to end in a bare
  `fetchItems()`, which re-read page one and dropped whatever search and
  category the caller was showing.

- **Session template** (``CatalogItemSession``) is optional per item;
  when present, the sum of ``default_price`` across sessions must
  equal the item's ``default_price`` (tolerance ±0.01). The rule holds on
  *every* write, including a PUT that carries only a new price: that one used
  to skip the check and leave the stored stages adding up to the old total.
  A price-only write on a staged item is therefore a 422, which is why the
  catalog list does not offer inline editing for those rows. PUT
  ``/items/{id}`` with ``sessions`` (list, even empty) replaces the
  template atomically via ORM ``item.sessions.clear()`` + re-append;
  omitting the key preserves the existing template. Consumers
  (treatment_plan) snapshot this template at plan-add time.
- **A treatment's `specialty_ids` is a full replace, like the specialty side.**
  Sending the key sets the whole set; omitting it leaves it alone. Anything
  editing an item must therefore carry *every* discipline it already had — the
  catalog form sent one, and a crown filed under three came out of a price
  change with one. `CatalogItemModal` keeps `specialtyIds` as a list for that
  reason; do not collapse it back to a single value.

- **A clinic holds one specialty per meaning.** `SpecialtyService.create_specialty`
  and `update_specialty` refuse a name the clinic already has —
  accent-folded, case-folded, across every language on the row — and an
  inactive row counts, because deactivating hides the row and not its
  assignments. `SUGGESTED_SPECIALTIES` in `seed.py` is the recognised list the
  UI offers; it is deliberately *not* seeded, and its keys are the only ones
  `POST /specialties` accepts, since a key is what the seeder matches on.

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
