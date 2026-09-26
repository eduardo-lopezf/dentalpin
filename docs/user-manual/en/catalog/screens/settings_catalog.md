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
  - GET /api/v1/catalog/specialties/suggestions
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
last_verified_commit: 1facfd7
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

## Adding a specialty

The **New Specialty** button offers the **recognised ones the clinic does not
have yet** first — Radiology and Imaging, Oral Pathology, Oral Medicine,
Orofacial Pain and TMD, Sleep Dentistry, laboratory Dental Prosthetics,
Geriatric Dentistry. One tap adds them, with their name in both languages.
The free-text box is still underneath, for whatever a list cannot anticipate.

They are deliberately not seeded: no clinic uses them all, and putting them in
every picker would be the same clutter as a catalog full of treatments nobody
offers.

**The same specialty cannot be held twice.** Type a name that already exists
and the form says so before anything is sent, and will not save. This is not
tidiness: a professional gets tagged with one row and the treatments with the
other, and the *Only what my team does* filter then stops finding them with
nothing on screen to explain why. Accents and case do not make a different
specialty, and neither does the language: "Endodontics" is the same one as
"Endodoncia".

When the clash is with a **deactivated** specialty, the notice says so and
offers to **reactivate** it. That case matters: deactivating hides the row, not
its assigned treatments, so creating another under the same name would leave
the live half empty and the assignments stranded on a row no list shows.

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

## The list is complete

The **Treatment Type** tab loads the whole catalog and groups it by category.
It no longer paginates: a grouping can only be read off the complete list, and
the search box and category filter narrow what is loaded, in the browser,
without asking the server again.

The number beside the heading counts **the rows below it**. With a filter on it
reads *"12 of 136"*.

This has been a bug twice. The first time the pager ignored clicks and only the
first page was reachable. The second was worse because nothing showed it: the
screen asked for "500 treatments" from a listing that serves at most 100, so it
drew 100 of the clinic's 136 — Diagnostic, Periodontics and Cosmetic missing
outright, Endodontics showing 6 of its 10 — and headed them with the number
136. Which categories vanished depended on the internal order of their ids, so
it followed no pattern anyone would spot, and the grouped view has no pager to
reach what was missing.

So the list no longer asks for "everything" in one page: it walks the catalog
until it is exhausted, and the counter counts what arrived, never what should
have.

## "Performed by": one or several

A treatment belongs to **every discipline that performs it**, not to one. A
crown over an implant is Implantology and Oral Rehabilitation; a veneer is
Restorative by where it is filed and Cosmetic by what it is for. 48 of the 136
seeded treatments carry more than one specialty.

The form field is a multi-select and **saves the complete set**. It used to be
a plain dropdown, and that destroyed data silently: opening the record kept
only the first specialty and saving sent back that one, so opening a crown to
change its price left it with one of its three. The survivor was always the
most generic one — the list arrives oldest first — so editing prices slowly
emptied Implantology into General Dentistry, and with it the *By Specialty* tab
and the *Only what my team does* filter.

When **creating**, the treatment type proposes the specialty, the phase and the
placement, and you change them if another discipline does it here. On a
**saved** treatment, changing the type touches none of the three: you already
decided that.

## Editing treatments

Treatments shipped with the system are **editable**: price, name, duration, VAT,
category, specialties and phase. They can also be **deleted**, not merely
deactivated: a clinic does not offer everything the starter catalog ships.

The bin sits on the row, on treatments marked **System** too. For a while it
did not: the API already accepted removing them while the button stayed hidden
on exactly those, and since a freshly created clinic's catalog is *entirely*
system-seeded, it never appeared at all.

The deletion is a soft one. The record is not destroyed — treatments already
performed, budget lines and plan templates reference it — it simply disappears
from every picker: the catalog search, the odontogram bar, budgets.

**And it can be undone.** The **"Show inactive and removed"** switch beside the
search box brings back what is no longer offered: removed treatments appear
badged *Removed* with a **Restore** button, deactivated ones badged *Inactive*.
Without it both were unreachable from the only screen that can edit them — and
a removed treatment **keeps its internal code reserved**, so it could not be
recreated under the same code either.

Re-seeding the catalog does not resurrect it either: seeding sees the record is
still there and leaves it alone.

*Deactivating* remains the middle option: the treatment stops being offered but
keeps its price and configuration for when it comes back.

Creating, editing and deleting treatments requires the `catalog.write`
permission; managing categories, VAT types and specialties requires
`catalog.admin`. **By default only the admin profile holds either**, so in
practice it is the only one that can change the catalog. Every other profile
sees the catalog read-only.

The one locked field on a system treatment is the **internal code**: it is the
key seeding matches on, and changing it would make the next seed run recreate
the original as a duplicate.

## Setting your prices

A price is changed **in the table itself**: click the figure, type yours, press
Enter. The row updates on its own, so a whole column can be walked without the
list moving under the cursor.

This is the first job of a clinic starting out — the starter catalog ships 136
treatments at example prices — and until now it was one form per treatment:
open, find the field, save, wait for the list, find the next row.

`Esc` cancels, and leaving the box empty does not price the treatment at zero:
a treatment with no price is not the same as a free one, and the treatment plan
tells them apart.

Treatments **billed in stages** carry a layers icon and are not edited here:
their total is the sum of their sessions, which is changed from the form. In
the starter catalog there are seven of them.

## The "Visible" column

Each treatment has a **Visible** checkbox deciding whether it appears in the
**Treatments** menu. It is the same checkbox in both tabs: tick it under
"Treatment Type" and it shows ticked under "By Specialty".

**Not the same as active/inactive.** Hiding a treatment only removes it from
that browsing list; it stays active and billable, and keeps working in
budgets, the odontogram and history. To stop offering it, deactivate it.

Treatments start visible. Only an admin can change the checkbox.
