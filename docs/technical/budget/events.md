---
module: budget
last_verified_commit: 0000000
---

# Budget — events

> _Scaffolded stub — replace with proper documentation when this module is next touched._

Per-module slice of [`docs/events-catalog.md`](../../events-catalog.md)
(auto-generated). Update both files when adding or removing events.

## Published

| Event | When | Payload |
|-------|------|---------|
| `budget.created_for_plan` | A budget now prices a treatment plan: minted on `treatment_plan.confirmed`, generated on request, or an addendum. | `clinic_id`, `plan_id`, `budget_id`, `budget_number`, `kind` (`primary` \| `addendum` \| `extended`), `item_count`, `user_id`. `treatment_plan` links a `primary` one and logs all three. |

_The workflow events (`budget.sent`, `budget.accepted`, …) are listed in the [events catalog](../../events-catalog.md)._

## Subscribed

| Event | Handler | Effect |
|-------|---------|--------|
| `odontogram.treatment.performed` | _Handler module path._ | _What it does in response._ |
| `treatment_plan.budget_sync_requested` | _Handler module path._ | _What it does in response._ |
| `treatment_plan.confirmed` | `budget.plan_quotes.on_plan_confirmed` | Mints the plan's draft budget and publishes `budget.created_for_plan`. Skipped while the budget named in the payload's `budget_id` is live. |
| `treatment_plan.status_changed` | `budget.plan_quotes.on_plan_status_changed` | On a reopen (`pending`/`active` → `draft`), cancels the budget named in `budget_id`. |
| `treatment_plan.deleted` | `budget.plan_quotes.on_plan_deleted` | Soft-deletes every budget carrying the plan's number, plus the linked one. |
| `treatment_plan.treatment_added` | _Handler module path._ | _What it does in response._ |
| `treatment_plan.treatment_removed` | _Handler module path._ | _What it does in response._ |

## Adding a new event

1. Add the constant to `backend/app/core/events/types.py` (`EventType`).
2. Publish from a service method, after the DB commit succeeds.
3. Add the row to the table(s) above.
4. Run `python backend/scripts/generate_catalogs.py` to refresh the
   global catalog.
