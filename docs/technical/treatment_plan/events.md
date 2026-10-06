---
module: treatment_plan
last_verified_commit: 0000000
---

# Treatment Plan — events

> _Scaffolded stub — replace with proper documentation when this module is next touched._

Per-module slice of [`docs/events-catalog.md`](../../events-catalog.md)
(auto-generated). Update both files when adding or removing events.

## Published

| Event | When | Payload |
|-------|------|---------|
| `treatment_plan.budget_sync_requested` | _When does this fire?_ | _Payload keys._ |
| `treatment_plan.created` | _When does this fire?_ | _Payload keys._ |
| `treatment_plan.status_changed` | Any plan status transition. | `plan_id`, `old_status`, `new_status`, `clinic_id`. A reopen (`→ draft`) also carries `budget_id` (the live budget, nullable) and `user_id`: `budget` cancels that budget on hearing it. |
| `treatment_plan.confirmed` | `POST /treatment-plans/{id}/confirm`. | The plan snapshot (`plan_id`, `plan_number`, `clinic_id`, `patient_id`, `patient_full_name`, `items[]`, `total_estimated`), `confirmed_at`, `confirmed_by_user_id`, `plan_status`, and `budget_id` — the live budget the plan still links to, or null. `budget` mints the draft budget unless that is set (ADR 0042). |
| `treatment_plan.deleted` | `DELETE /treatment-plans/{id}`. | `plan_id`, `clinic_id`, `patient_id`, `plan_number`, `budget_id` (nullable), `deleted_by_user_id`. `budget` soft-deletes every budget the plan produced. |
| `treatment_plan.treatment_added` | A `PlannedTreatmentItem` is added to a plan via `POST /treatment-plans/{id}/items`. | `plan_id`, `item_id`, `treatment_id`, `clinic_id`, `patient_id`, `budget_id` (nullable), `catalog_item_id` (nullable), `tooth_number` (nullable), `surfaces` (nullable), `unit_price` (nullable, decimal-as-string), `assigned_professional_id` (nullable, snapshot of the doctor responsible for this line). |
| `treatment_plan.treatment_completed` | _When does this fire?_ | _Payload keys._ |
| `treatment_plan.treatment_removed` | _When does this fire?_ | _Payload keys._ |
| `treatment_plan.item_session_reopened` | A completed item is reopened (`PATCH /treatment-plans/{id}/items/{item_id}/reopen`) and the session that closed it was a completion, not a cancellation. One event, for that session only. | `plan_id`, `item_id`, `session_id`, `treatment_id`, `patient_id`, `clinic_id`, `reopened_by`, `occurred_at`. Consumed by `payments`, which drops the earned entry the completion booked. |

## Subscribed

| Event | Handler | Effect |
|-------|---------|--------|
| `catalog.specialty_enabled` | `treatment_plan.events.on_specialty_enabled` | Installs and shows the reference plan templates of that discipline. |
| `catalog.specialty_disabled` | `treatment_plan.events.on_specialty_disabled` | Hides the reference templates of that discipline. Templates the clinic saved itself are left alone. |
| `catalog.specialty_restored` | `treatment_plan.events.on_specialty_restored` | Puts the reference templates of that discipline back to the reference. |
| `appointment.completed` | `treatment_plan.events.on_appointment_completed` | From the payload's `planned_items` alone: starts the plans the visit belongs to, and completes the items ticked off in it. Reads no agenda table. |
| `budget.accepted` | _Handler module path._ | _What it does in response._ |
| `budget.created_for_plan` | `treatment_plan.events.on_budget_created_for_plan` | Links a `primary` budget to the plan (`budget_id`) and writes the history entry (`budget_created`, `budget_addendum` or `budget_extended`). The only place the plan's budget link is written. |
| `budget.rejected` | _Handler module path._ | _What it does in response._ |
| `budget.renegotiated` | _Handler module path._ | _What it does in response._ |
| `odontogram.treatment.performed` | _Handler module path._ | _What it does in response._ |

## Adding a new event

1. Add the constant to `backend/app/core/events/types.py` (`EventType`).
2. Publish from a service method, after the DB commit succeeds.
3. Add the row to the table(s) above.
4. Run `python backend/scripts/generate_catalogs.py` to refresh the
   global catalog.
