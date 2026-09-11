---
module: treatment_plan
screen: treatments_plans
route: /treatments/plans
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
  - backend/app/modules/treatment_plan/frontend/pages/treatments/plans/index.vue
  - backend/app/modules/treatment_plan/router.py
last_verified_commit: 3568519
---

# Plans inbox

Inbox of the clinic's treatment plans. Organized into **seven tabs**:
six follow-up queues served by `GET /pipeline`, and a closing *List*
of every plan.

## At a glance

- **In progress** *(first tab, the one that opens by default)*. Every
  plan in flight, wherever it sits in the circuit: `pending` (the
  dentist confirmed it and is waiting on the patient) and `active`
  (budget accepted, treatment under way). Reception treats both the
  same — a plan starts moving when the patient turns up for the
  diagnostic visit, long before the budget is signed — so splitting
  them across tabs hid work that was live. Sorted by most recent
  movement first: it answers "what is going on right now" rather than
  being a queue to work through.
- **Action queues.** *To quote* (confirmed, budget still draft),
  *Awaiting patient* (budget sent or expired), *No appointment* and
  *No next appointment* (active plans with pending treatments and an
  empty diary), *Closed* (last 90 days).
- **Rows that fit their own width.** Each card decides its layout by
  measuring itself rather than the window: once the card drops below 56rem
  — an upright tablet, rail open or collapsed — the patient moves to the top
  and *Treatments*, *Budget* and *days in status* share a wrapped line
  beneath. Nothing is hidden; those columns used to overlap the plan number.
- **When a plan becomes *In treatment*.** A plan reaches `active` by
  either of two routes, and one is enough: the **budget is accepted**, or
  the patient **attends the first appointment** linked to the plan. The
  visit counts even when no treatment is ticked off — a diagnostic first
  visit rarely ticks any. A *Draft* plan is never started by attendance:
  it has to be confirmed first.
- **Accept in clinic.** When the patient says yes while standing there,
  the button on the row opens a dialog that takes their name and,
  optionally, a signature drawn on the tablet. It shows only while the
  budget is *draft* or *sent*. A real signature is recorded — name,
  stroke, IP, timestamp and method — and accepting carries the plan to
  *In treatment* through the usual route.
- **Searching by name.** The box takes a plan number or the patient's name,
  in any order, accented or not: "Juan Pérez", "Pérez Juan" and "juan perez"
  all land on the same person. Every word has to match something, so adding
  a second one narrows the results rather than widening them.
- **All** *(last tab)*. Every plan in the clinic ordered by creation
  date, newest first, with a status filter. This is the catalogue
  view: any plan shows up here, including drafts and archived ones
  that belong to no queue.
- **Drafts live only here.** The patient record's *Clinical* tab does
  not list them: that view answers "where does this patient's treatment
  stand", and a half-written plan is not an answer — it also pushed the
  plans that matter further down the page. They stay visible, editable
  and deletable under *All*, whose status filter includes *Draft*.
  Previous plans do remain on the record, collapsed at the end of the
  list under **Previous plans**: completed and closed sit together,
  because to whoever is reading the history they are the same thing —
  treatment that is over — and splitting them put the patient's past
  behind two separate panels. Each card's badge still says which of the
  two it is.
- **Pipeline pagination.** The columns paginate for real: the pager
   ignored clicks because it used the component's old API, so only the
   first page was ever reachable.
- **Search and filters.** Search by patient or plan number; filter
  by assigned professional, creation date, and closure reason.
- **Budget sync.** Each plan has a linked budget (or creates one on
  confirm). Plan changes propagate to the budget via snapshot
  events — no need to edit the budget by hand.
- **Clinical notes.** Since issue #60, notes are not stored on the
  plan: they are delegated to the `clinical_notes` module. The plan
  only logs executions.

## Find a plan

1. Switch tabs or enter the pipeline.
2. Filter by professional, date, or closure reason as needed.
3. Click a row to open the [detail](./treatments_plans_id.md).

## Create a plan

> Requires `treatment_plan.plans.write`.

1. Click **New plan** (top right) → goes to `/treatments/plans/new`.
2. Pick patient, professional, and add treatments.

## Log a contact

> Requires `treatment_plan.plans.write`.

1. On the row or detail, use **Log contact** to record a phone /
   WhatsApp / email touchpoint by the front desk.
2. These contacts feed the pipeline view so plans don't go too long
   without activity.

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| View inbox, pipeline, and detail | `treatment_plan.plans.read` |
| Create, edit, add items, log contacts | `treatment_plan.plans.write` |
| Confirm (draft → pending) | `treatment_plan.plans.confirm` |
| Close a plan | `treatment_plan.plans.close` |
| Reactivate a closed plan | `treatment_plan.plans.reactivate` |

## Troubleshooting

- **Plan is pending but the patient accepted.** The `budget.accepted`
  event moves it to *active* automatically. If it hasn't, check
  that the budget is actually accepted and both modules are
  installed.
- **Closed plan is missing.** On the *Closed* tab, filter by
  *closure reason*. The default includes all.
- **No *Confirm* button.** Your role lacks
  `treatment_plan.plans.confirm` or the plan is already in pending
  or later.
