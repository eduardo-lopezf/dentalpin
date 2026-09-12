---
module: treatment_plan
last_verified_commit: 0000000
---

# Treatment Plan — permissions

> _Scaffolded stub — replace with proper documentation when this module is next touched._

Returned by `TreatmentPlanModule.get_permissions()`
(relative names; the registry namespaces them as `treatment_plan.<name>`).

| Permission | Allows | Required by |
|------------|--------|-------------|
| `treatment_plan.plans.read` | _Describe what this allows._ | _List the endpoints._ |
| `treatment_plan.plans.write` | Create a plan and change what is in it: its items, their order, their notes and stage, and the two bulk ways of filling it — a template, or treatments picked one by one from the catalog. Reopening a plan asks for more than this (see the module CLAUDE.md: an administrator or an assigned professional). | `POST /treatment-plans`, `PUT /treatment-plans/{id}`, `POST /treatment-plans/{id}/items`, `PUT /treatment-plans/{id}/items/{item_id}`, `DELETE /treatment-plans/{id}/items/{item_id}`, `PATCH /treatment-plans/{id}/items/reorder`, `POST /treatment-plans/{id}/apply-template`, `POST /treatment-plans/{id}/catalog-items`, `POST /treatment-plans/{id}/proposals` |
| `treatment_plan.plans.confirm` | _Describe what this allows._ | _List the endpoints._ |
| `treatment_plan.plans.close` | _Describe what this allows._ | _List the endpoints._ |
| `treatment_plan.plans.reactivate` | _Describe what this allows._ | _List the endpoints._ |
| `treatment_plan.plans.templates` | Curate the clinic's plan templates: create, edit, hide, and save an existing plan as one. Reading them needs only `plans.read` — everyone who builds a plan picks from the list. | `POST /plan-templates`, `PUT /plan-templates/{id}`, `DELETE /plan-templates/{id}`, `POST /plan-templates/from-plan/{plan_id}` |

## Role assignment

See `backend/app/core/auth/permissions.py` for the canonical role table.

## Adding a new permission

1. Add the relative name to `get_permissions()` in
   `backend/app/modules/treatment_plan/__init__.py` (or `module.py`).
2. Add the namespaced form to the relevant role(s) in
   `backend/app/core/auth/permissions.py`.
3. Add a row to the table above.
4. Annotate the endpoint(s) with `Depends(require_permission(...))`.
5. Update `frontend/app/config/permissions.ts` if it gates UI.
