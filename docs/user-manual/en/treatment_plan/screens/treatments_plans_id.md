---
module: treatment_plan
screen: treatments_plans_id
route: /treatments/plans/[id]
related_endpoints:
  - DELETE /api/v1/treatment_plan/treatments/plans/{plan_id}
  - DELETE /api/v1/treatment_plan/treatments/plans/{plan_id}/items/{item_id}
  - GET /api/v1/treatment_plan/treatments/plans
  - GET /api/v1/treatment_plan/treatments/plans/patient/{patient_id}
  - GET /api/v1/treatment_plan/treatments/plans/pipeline
  - GET /api/v1/treatment_plan/treatments/plans/{plan_id}
  - PATCH /api/v1/treatment_plan/treatments/plans/{plan_id}/items/reorder
  - PATCH /api/v1/treatment_plan/treatments/plans/{plan_id}/items/{item_id}/complete
  - PATCH /api/v1/treatment_plan/treatments/plans/{plan_id}/status
  - POST /api/v1/treatment_plan/treatments/plans
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/close
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/apply-template
  - GET /api/v1/treatment_plan/treatment-plans/{plan_id}/proposals
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/proposals
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/confirm
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/contact-log
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/generate-budget
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/items
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/link-budget
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/reactivate
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/reopen
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/sync-budget
  - PUT /api/v1/treatment_plan/treatments/plans/{plan_id}
  - PUT /api/v1/treatment_plan/treatments/plans/{plan_id}/items/{item_id}
related_permissions:
  - treatment_plan.plans.read
  - treatment_plan.plans.write
  - treatment_plan.plans.confirm
  - treatment_plan.plans.close
  - treatment_plan.plans.reactivate
related_paths:
  - backend/app/modules/treatment_plan/frontend/pages/treatments/plans/[id].vue
  - backend/app/modules/treatment_plan/frontend/components/clinical/PlanDetailView.vue
  - backend/app/modules/treatment_plan/frontend/components/clinical/PlanTreatmentList.vue
  - backend/app/modules/treatment_plan/proposals.py
  - backend/app/modules/treatment_plan/router.py
last_verified_commit: e372dd4
---

# Treatment plan detail

Plan view: header with patient, professional, and status; main
column with the items (catalog or odontogram tooth treatment); and
sidebar with the linked budget, executions, and contacts. This is
where you confirm, sync with the budget, mark items as performed,
and close or reactivate.

## Building the plan

There are three ways to get treatments into a draft plan, and they
combine:

- **Apply template.** Brings in a whole plan shape (see
  [New plan](./treatments_plans_new.md)). It can be applied more than
  once, so a plan can be hygiene phase + single implant.
- **Propose from the chart.** The button appears with a count when the
  patient has findings charted that nothing is planned for. The list
  pairs each finding with the matching treatment — caries →
  composite, pulpitis on a molar → molar endodontics — and **Add**
  brings them all in. The finding stays on the chart: the diagnosis
  and the plan are separate things, and the caries is still there
  until it is treated. Untick a row whose suggestion does not fit and
  add that one by hand from the bar.
- **Treatment bar.** Pick the treatment and click the tooth. The
  treatment **stays armed** after each application, so 16, 26 and 36
  are three clicks, not three searches. The badge in the header says
  what is armed; the ✕ or `Esc` releases it. For a whole quadrant,
  use the **Quadrant 1–4** buttons next to the badge: they confirm,
  naming the teeth, before creating anything.

The plan list is grouped by **stage of care**: emergency,
stabilisation, rehabilitation, maintenance. Each item's stage comes
from the catalog. Dragging reorders within a stage; to move something
to another stage, change the treatment's stage.

**Save as template** lives in the **···** menu: treatments and their
stages are saved, teeth and prices are not.

## At a glance

- **Status chip.** The header chip reflects the state: `draft`,
  `pending`, `active`, `completed`, `closed`. Actions change with
  the state.
- **Items** — add, reorder, complete. Each item references a
  catalog item and, optionally, an odontogram tooth treatment.
  Completing an item publishes
  `treatment_plan.treatment_completed` (with
  `treatment_category_key` for recalls).
- **Doctor per treatment.** Every item carries its own
  `assigned_professional_id`. New items inherit the plan's doctor.
  Click the coloured chip next to the item name to assign a
  different professional (e.g. filling by Dr A, endodontics by
  Dr B). When two or more doctors are involved in the plan, the
  chip colours make the mix visible at a glance. The chip stays
  editable while the item is pending, even after the plan is
  validated and the budget is active — reassignment is operational
  and does not change the patient-facing contract. Once an item is
  marked as completed, the chip becomes a read-only indicator and
  keeps showing `assigned_professional_id` (the clinician
  responsible for the treatment); completion can be triggered by
  reception or an admin on behalf of the clinician, so "who clicked
  Complete" is intentionally not the chart's reference.
- **Linked budget.** **Generate budget** / **Link to existing
  budget** / **Sync** buttons as needed. The plan publishes
  `treatment_plan.treatment_added / _removed /
  budget_sync_requested` so `budget` keeps the budget up to date.
- **Contacts** — front-desk touchpoint history. Useful when the
  plan is *pending* awaiting acceptance.
- **Clinical notes.** Can be attached to the plan from the
  `clinical_notes` module (slot `patient.detail.clinical.notes`).

## Confirm a plan

> Requires `treatment_plan.plans.confirm`.

1. On a `draft` plan, click **Confirm**.
2. `treatment_plan.confirmed` is published. The plan moves to
   `pending`.
3. If no budget was linked, **Generate budget** creates a new one
   on the `budget` module.

## Mark items as performed

> Requires `treatment_plan.plans.write`.

1. On the item, click **Mark as done**.
2. `treatment_plan.treatment_completed` is published. `recalls` can
   suggest a follow-up recall based on `treatment_category_key`.
3. To record a clinical note at that moment, use the *Add note*
   button (contributed by `clinical_notes`).

**Removing an item from the plan** (the trash icon on the row) asks
for confirmation: it cascades into the odontogram treatment and the
associated budget line.

## Multi-session treatments

Some catalog items (e.g. crown, root canal) carry a **session
template** with a label and price per step. When the treatment is
added to a plan, one session is created per step.

- The item header shows an **X/Y sessions** progress chip.
- Below the item, the session list renders one row per session (✓
  icon when completed, dashed circle when pending).
- Click the check on a pending session to mark it done — publishes
  `treatment_plan.item_session_completed`; `payments` records an
  "earned" entry for that amount.
- The item is finalized automatically when the last pending session
  is completed (the legacy completion flow runs at that point).
- Cancel a session if it was not delivered — no earned entry is
  generated.

## Change the plan's doctor

> Requires `treatment_plan.plans.write`.

1. Open **Edit plan** and pick a new professional.
2. If there are pending items still assigned to the previous
   doctor, a confirmation appears: *"Reassign pending treatments?"*.
3. Choose **Yes, reassign pending** to push all matching pending
   items onto the new doctor in the same save. Items with an
   explicit override (different doctor) and completed items are
   never touched.
4. Choose **No, keep as they are** to update only the plan-level
   doctor; the items stay where they were.

## Close or reactivate

> Closing requires `treatment_plan.plans.close`. Reactivating
> requires `treatment_plan.plans.reactivate`.

1. **Close** — pick reason: rejected, expired, cancelled,
   abandoned, or *other*. Publishes `treatment_plan.closed` with
   `closure_reason`.
2. **Reactivate** — back to `draft`. Publishes
   `treatment_plan.reactivated`.

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| View detail, items, and contacts | `treatment_plan.plans.read` |
| Add/reorder items, complete them, log contacts | `treatment_plan.plans.write` |
| Confirm (draft → pending) | `treatment_plan.plans.confirm` |
| Close | `treatment_plan.plans.close` |
| Reactivate | `treatment_plan.plans.reactivate` |

## Troubleshooting

- **Confirmed the plan but no budget appears.** Click **Generate
  budget** or **Link to existing budget**. Confirming does not
  auto-create a budget unless you use *Generate* afterwards.
- **Patient accepted the budget but the plan is still pending.**
  Check that `budget.accepted` is flowing (the `budget` module must
  be installed and the budget actually accepted). The
  `on_budget_accepted` handler moves it to *active*.
- **Cannot delete an item.** The item is already marked as done.
  Completed items remain as history.
- **Cannot complete an item.** Your role lacks
  `treatment_plan.plans.write`.
