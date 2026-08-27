---
module: catalog
screen: catalog
route: /settings/catalog
related_endpoints:
  - DELETE /api/v1/catalog/categories/{category_id}
  - DELETE /api/v1/catalog/items/{item_id}
  - DELETE /api/v1/catalog/specialties/{specialty_id}
  - DELETE /api/v1/catalog/vat-types/{vat_type_id}
  - GET /api/v1/catalog/categories
  - GET /api/v1/catalog/categories/{category_id}
  - GET /api/v1/catalog/items
  - GET /api/v1/catalog/items/popular
  - GET /api/v1/catalog/items/search
  - GET /api/v1/catalog/items/{item_id}
  - GET /api/v1/catalog/odontogram-treatments
  - GET /api/v1/catalog/odontogram-treatments/by-category
  - GET /api/v1/catalog/specialties
  - GET /api/v1/catalog/specialties/{specialty_id}
  - GET /api/v1/catalog/specialties/{specialty_id}/items
  - GET /api/v1/catalog/vat-types
  - GET /api/v1/catalog/vat-types/default
  - GET /api/v1/catalog/vat-types/{vat_type_id}
  - POST /api/v1/catalog/categories
  - POST /api/v1/catalog/items
  - POST /api/v1/catalog/specialties
  - POST /api/v1/catalog/vat-types
  - PUT /api/v1/catalog/categories/{category_id}
  - PUT /api/v1/catalog/items/{item_id}
  - PUT /api/v1/catalog/specialties/{specialty_id}
  - PUT /api/v1/catalog/specialties/{specialty_id}/items
  - PUT /api/v1/catalog/vat-types/{vat_type_id}
related_permissions:
  - catalog.read
  - catalog.write
  - catalog.admin
related_paths:
  - backend/app/modules/catalog/frontend/pages/settings/catalog/index.vue
last_verified_commit: 3568519
---

# /settings/catalog

> _Scaffolded stub — replace with proper documentation when this module is next touched._

_Screen `/settings/catalog` of the `catalog` module._

## Permissions

- `catalog.read`
- `catalog.write`
- `catalog.admin`

## What this screen does

_Documentation pending._

## Tabs

The screen has two tabs:

- **Treatment Type**: existing view, treatments grouped by category
  (`TreatmentCategory`).
- **By Specialty**: manage (create/edit/deactivate) the dental
  specialty catalog (`Specialty`), independent from a treatment's
  category — e.g. "Oral and Maxillofacial Surgery", and assign catalog
  treatments to each one.

### Assigning treatments to a specialty

Each specialty renders as a collapsible group listing the treatments
assigned to it (code, name, category and price). A final **No
specialty** group collects the treatments not yet classified, so the
gaps are visible at a glance.

The **Assign treatments** button (admins only) opens a searchable list
of the whole catalog with checkboxes. The saved payload is the full
selection: treatments that get unchecked lose the assignment to that
specialty.

A treatment may belong to several specialties at once (a simple
extraction can be both general practice and oral surgery), in which
case it appears under each matching group.

Inactive treatments show up in the assignment list only when already
assigned, so an assignment can be removed without reactivating the
treatment.

## Seeded specialties

A clinic starts with ten baseline specialties: General Dentistry, Dental
Hygiene, Endodontics, Periodontics, Oral and Maxillofacial Surgery,
Implantology, Orthodontics, Pediatric Dentistry, Cosmetic Dentistry and Oral
Rehabilitation. They can be renamed, deactivated or extended (Radiology, Oral
Pathology, Sleep Dentistry, ...) safely: seeding matches them by an internal
key, not by the displayed name.

Catalog treatments arrive already classified. Assignment starts from the
category and is refined per treatment where the category falls short:
Implantology gathers the implant (Surgery), its crown (Restorative) and the
overdenture (Prosthetics) — three categories, one discipline. Veneers are
Restorative but also Cosmetic. Periodontal maintenance also counts as Dental
Hygiene.

Re-seeding only fills gaps; it never removes assignments you made by hand.

## Pagination

The list paginates. Until now the pager ignored clicks — it used the
component's old API — and only the first page was reachable; the
treatments beyond it existed with no way to get to them.

## Editing treatments

Treatments shipped with the system are **editable**: price, name, duration, VAT,
category, specialties and phase. They can also be **deactivated** when your
clinic does not offer them, rather than deleted — which keeps the budget and
invoice history that references them intact.

Only the **admin** profile can create or edit treatments. Every other profile
sees the catalog read-only.

The one locked field on a system treatment is the **internal code**: it is the
key seeding matches on, and changing it would make the next seed run recreate
the original as a duplicate.

## The "Visible" column

Each treatment has a **Visible** checkbox deciding whether it appears in the
**Treatments** menu. It is the same checkbox in both tabs: tick it under
"Treatment Type" and it shows ticked under "By Specialty".

**Not the same as active/inactive.** Hiding a treatment only removes it from
that browsing list; it stays active and billable, and keeps working in
budgets, the odontogram and history. To stop offering it, deactivate it.

Treatments start visible. Only an admin can change the checkbox.
