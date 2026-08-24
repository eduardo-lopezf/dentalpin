---
module: catalog
screen: treatments_catalog
route: /treatments/catalog
related_endpoints:
  - GET /api/v1/catalog/categories
  - GET /api/v1/catalog/items
  - GET /api/v1/catalog/specialties
  - GET /api/v1/professionals
related_permissions:
  - catalog.read
related_paths:
  - backend/app/modules/catalog/frontend/pages/treatments/catalog.vue
last_verified_commit: e2b7328257c69af310ee8f0ff2ae624dfe2d7545
---

# /treatments/catalog

Clinical view of the catalog, for the whole team. It is the counterpart to
**Settings → Treatment catalog**, which administers prices and creation and
is admin-only: this page answers *what do we offer, and who performs it*.

## Permissions

- `catalog.read` — every profile.

## The three axes

Each treatment is crossed by three independent classifications that combine:

| Axis | Answers | Example |
|---|---|---|
| **Category** | where it is filed | Restorative |
| **Specialty** | who performs it | Implantology |
| **Phase** | when in a course of care | Rehabilitation |

All active treatments show by default. Filters only narrow; none hides
anything permanently.

The axes are not subsets of one another, which is the point: filtering by
**Implantology** gathers the implant (Surgery category), the implant crown
(Restorative) and the overdenture (Prosthetics) — one clinical flow spread
across three categories.

## Only what my team performs

This switch narrows the list to the specialties covered by the clinic's
**active** professionals.

It is a filter, not a lock: turning it off brings the whole catalog back.
That matters because the catalog is also history — you need to quote a
referral, look up a treatment done by a colleague who has left, or review
something invoiced last year.

When no professional has a specialty assigned the switch says so and matches
nothing: specialties are assigned under **Professionals**.
