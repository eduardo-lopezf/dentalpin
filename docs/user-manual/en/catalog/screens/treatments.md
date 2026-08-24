---
module: catalog
screen: treatments
route: /treatments
related_permissions:
  - catalog.read
  - treatment_plan.plans.read
related_paths:
  - backend/app/modules/catalog/frontend/pages/treatments/index.vue
last_verified_commit: 42c33757157786fe53cdb00fc76091e9922be1c5
---

# /treatments

Section entry point — not a screen of its own. It redirects immediately to
whichever of the two "Tratamientos" surfaces the current role should land
on:

- **[Plan pipeline](../../treatment_plan/screens/treatments_plans.md)**
  (`/treatments/plans`) — the daily work, for anyone with
  `treatment_plan.plans.read`.
- **[Treatment catalog](./treatments_catalog.md)** (`/treatments/catalog`)
  — fallback for roles without plan access; everyone holds `catalog.read`.

The section folds two former menu entries (plans, catalog) into one nav
item. Landing on the pipeline by default keeps the high-frequency task one
click away instead of behind the reference page.

## Permissions

- `catalog.read` — every profile; guarantees the fallback destination is
  always reachable.
- `treatment_plan.plans.read` — when present, wins and routes to the
  pipeline instead.
