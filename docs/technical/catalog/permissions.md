---
module: catalog
last_verified_commit: 0000000
---

# Catalog — permissions

Returned by `CatalogModule.get_permissions()`
(relative names; the registry namespaces them as `catalog.<name>`).

The split is between **the treatments themselves** and **the taxonomy
around them**. A clinic can plausibly want someone maintaining the price
list without letting them restructure categories, specialties or VAT
types — so items sit on `catalog.write` and everything that classifies
them on `catalog.admin`.

| Permission | Allows | Required by |
|------------|--------|-------------|
| `catalog.read` | Read the whole catalog: treatments, categories, VAT types, specialties and odontogram mappings. | `GET /items`, `GET /items/{id}`, `GET /items/search`, `GET /items/popular`, `GET /categories`, `GET /categories/{id}`, `GET /vat-types`, `GET /vat-types/default`, `GET /vat-types/{id}`, `GET /specialties`, `GET /specialties/{id}`, `GET /specialties/{id}/items`, `GET /odontogram-treatments`, `GET /odontogram-treatments/by-category` |
| `catalog.write` | Create, edit and delete **treatments**, including toggling their visibility (a `PUT` on the item). | `POST /items`, `PUT /items/{id}`, `DELETE /items/{id}` |
| `catalog.admin` | Manage the **taxonomy** a treatment is classified by: categories, VAT types and specialties. | `POST/PUT/DELETE /categories/{id}`, `POST/PUT/DELETE /vat-types/{id}`, `POST/PUT/DELETE /specialties/{id}`, `PUT /specialties/{id}/items` |

**By default only the `admin` role holds `write` or `admin`** — the
module manifest grants every other role `read` and nothing else. The
frontend asks for the same grants rather than checking the role, so
delegating the price list to a dentist is a change to
`manifest.role_permissions` and nothing else.

## Role assignment

See `backend/app/core/auth/permissions.py` for the canonical role table.

## Adding a new permission

1. Add the relative name to `get_permissions()` in
   `backend/app/modules/catalog/__init__.py` (or `module.py`).
2. Add the namespaced form to the relevant role(s) in
   `backend/app/core/auth/permissions.py`.
3. Add a row to the table above.
4. Annotate the endpoint(s) with `Depends(require_permission(...))`.
5. Update `frontend/app/config/permissions.ts` if it gates UI.
