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
| `treatment_plan.plans.read` | Read plans and everything that only describes them: the list, the bandeja, one plan's detail and its change log, the clinic's plan templates, and the charted findings proposed for a patient — whether that patient already has a plan or is about to get their first one in the builder. Nothing here writes; accepting a proposal is `plans.write`. | `GET /treatment-plans`, `GET /treatment-plans/pipeline`, `GET /treatment-plans/{id}`, `GET /treatment-plans/{id}/history`, `GET /treatment-plans/patient/{patient_id}`, `GET /treatment-plans/patient/{patient_id}/proposals`, `GET /treatment-plans/{id}/proposals`, `GET /plan-templates` |
| `treatment_plan.plans.write` | Create a plan and change what is in it: its items, their order, their notes and stage, and the two bulk ways of filling it — a template, or treatments picked one by one from the catalog. Also marking a treatment done and undoing that — reopening one *treatment* is the way back from the completion click, so it takes the same grant. Reopening a *plan* asks for more than this (see the module CLAUDE.md: an administrator or an assigned professional). **Adding** a treatment works on a plan in progress too — it takes nothing away from what the patient signed — and `budget-addendum` prices what was added, on a document of its own; changing or removing an accepted line still needs the plan reopened. | `POST /treatment-plans`, `PUT /treatment-plans/{id}`, `POST /treatment-plans/{id}/items`, `PUT /treatment-plans/{id}/items/{item_id}`, `DELETE /treatment-plans/{id}/items/{item_id}`, `PATCH /treatment-plans/{id}/items/reorder`, `PATCH /treatment-plans/{id}/items/{item_id}/complete`, `PATCH /treatment-plans/{id}/items/{item_id}/reopen`, `POST /treatment-plans/{id}/apply-template`, `POST /treatment-plans/{id}/catalog-items`, `POST /treatment-plans/{id}/proposals`, `POST /treatment-plans/{id}/dismissed-findings`, `POST /treatment-plans/{id}/budget-addendum` |
| `treatment_plan.plans.confirm` | _Describe what this allows._ | _List the endpoints._ |
| `treatment_plan.plans.close` | Close a plan with a reason. Closing with `cancelled_by_clinic` is refused with 409 `PLAN_HAS_COLLECTIONS` when the patient has paid into the plan (allocated to any of its budgets, net of refunds, or on-account money covering its work); every other reason still closes it. `DELETE /treatment-plans/{id}` (`plans.write`) answers the same 409. | `POST /treatment-plans/{id}/close` |
| `treatment_plan.plans.reactivate` | _Describe what this allows._ | _List the endpoints._ |
| `treatment_plan.prescriptions.read` | See and reprint the prescriptions written for a treatment. Granted to hygienist, assistant and receptionist so the front desk can reprint one the doctor already wrote. | `GET /treatment-plans/{id}/items/{item_id}/prescriptions`, `GET /prescriptions/{prescription_id}/pdf` |
| `treatment_plan.prescriptions.write` | Write a prescription for a treatment, signed by a professional from the directory whose name and licence are copied onto it. A clinical act, so only admin and dentist hold it. | `POST /treatment-plans/{id}/items/{item_id}/prescriptions` |
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
