# Treatment plan module

Patient treatment plans with budget + odontogram sync. **Heaviest
`depends` in the system** — this module is an integration hub. Read
this file before changing any cross-module flow.

## State machine

```
                    ┌── budget accepted ──┐
draft ──confirm──► pending ───────────────┼──► active ──complete──► completed
  ▲                  │   └─ visit attended ┘      │
  │                  │ rejected/expired           │ cancelled by clinic
  │                  ▼                            ▼
  └─── reactivate ◄──────       closed      ◄─────┘
                            (closure_reason)
```

`pending → active` has **two** doors, and either is enough:

- `accept_from_budget`, on `budget.accepted`; and
- `activate_from_attendance`, whenever work is recorded against the plan
  — the clinic counts a plan as under way from the first consultation the
  patient attends, which is normally well before anything is signed.

Both are idempotent and both refuse anything that is not `pending`, so a
`draft` plan never skips confirmation.

**Every completion path calls `_sync_plan_lifecycle`**, which runs the
start and then the finish. Do not call `_check_and_complete_plan`
directly from a new path: on its own it only ever finishes an `active`
plan, so a plan carried out in one go would stall in `pending` with every
item done. The three paths that finish a treatment — `_finalize_item`,
`on_appointment_completed` and `on_treatment_performed` — all route
through the hook.

`closure_reason` ∈ `{rejected_by_patient, expired,
cancelled_by_clinic, patient_abandoned, other}`. See ADR 0006 and
`docs/workflows/plan-budget-flow.md` (staff manual).

## Public API

Routes mounted at `/api/v1/treatment-plans/`.

- `GET   /treatment-plans`              — list; `treatment_plan.plans.read`
- `POST  /treatment-plans`              — create; `treatment_plan.plans.write`
- `GET   /treatment-plans/{id}`         — detail
- `PUT   /treatment-plans/{id}`         — update; status transitions
- `POST  /treatment-plans/{id}/items`   — add item from catalog or odontogram tooth treatment
- `PUT   /treatment-plans/{id}/items/reorder`
- `POST  /treatment-plans/{id}/items/{item_id}/complete`
- `POST  /treatment-plans/{id}/confirm`     — `plans.confirm`; draft → pending
- `POST  /treatment-plans/{id}/reopen`      — pending|active → draft, cancels linked budget; admin or an assigned professional only
- `POST  /treatment-plans/{id}/close`       — `plans.close`; any → closed
- `POST  /treatment-plans/{id}/reactivate`  — `plans.reactivate`; closed → draft
- `POST  /treatment-plans/{id}/contact-log` — record reception touchpoint
- `GET   /treatment-plans/pipeline`         — bandeja (6 tabs; `en_curso` leads)
- `GET   /treatment-plans/{id}/history`     — change log + the caller's rights
- `POST  /treatment-plans/{id}/apply-template` — append a template; `plans.write`.
  Body takes `excluded_template_item_ids`; returns `{items, skipped}`.
- `POST  /treatment-plans/{id}/catalog-items` — append hand-drawn lines;
  `plans.write`. `{lines: [{catalog_item_id, tooth_numbers, surfaces, phase,
  notes}]}` in, `{items, skipped}` out, 422 naming the lines still waiting
  for a tooth. Same code underneath as `apply-template`.
- `GET   /plan-templates`                   — list; `plans.read`
- `POST  /plan-templates`                   — create; `plans.templates`
- `PUT   /plan-templates/{id}`              — update; items are a full replace when sent
- `DELETE /plan-templates/{id}`             — soft delete (`is_active=False`)
- `POST  /plan-templates/from-plan/{id}`    — save an existing plan as a template
- `GET   /treatment-plans/{id}/proposals`   — charted findings with nothing planned yet
- `POST  /treatment-plans/{id}/proposals`   — turn accepted findings into plan items

> **Notes endpoints moved.** Since issue #60 the `clinical_notes` module
> owns every clinical-note CRUD path (`/api/v1/clinical_notes/*`). The
> per-item completion endpoint here no longer accepts `note_body` — the
> client orchestrates a follow-up POST to `clinical_notes` when the
> dentist captures a note at completion time.

## Dependencies

`manifest.depends = ["patients", "agenda", "odontogram", "catalog", "budget", "media", "professionals"]`.
Seven dependencies. Anything not on this list is off-limits — no imports,
no FKs.

`assigned_professional_id` (on `TreatmentPlan` and `PlannedTreatmentItem`)
FKs to `professionals.id`, not `users.id` — the assigned doctor is a
directory profile, independent of any product account (see `professionals`
module). `created_by`/`completed_by` stay FK'd to `users.id`: those record
who performed the action in the app, not who the clinical work is
attributed to.

## Permissions

`treatment_plan.plans.{read,write}`, plus `plans.{confirm,close,reactivate}`
for the workflow transitions and `plans.templates` for curating the clinic's
plan templates. Clinical-note permissions live in the `clinical_notes` module
since issue #60.

## Frontend slots exposed

- `treatment_plan.detail.sidebar` — rendered by `PlanDetailView.vue` above
  the treatment list. `payments` registers the collections card there. Slot
  ctx: `{ planId, patientId, patientName, budgetId, planStatus }`.

## Events emitted

| Event | When | Notes |
|---|---|---|
| `treatment_plan.created` | plan created | consumed by `patient_timeline` |
| `treatment_plan.status_changed` | status transition | currently no subscribers |
| `treatment_plan.confirmed` | draft → pending | snapshot payload (items, totals, patient). Subscriber: `patient_timeline`. |
| `treatment_plan.closed` | any → closed | payload includes `closure_reason`. Subscriber: `patient_timeline`. |
| `treatment_plan.reactivated` | closed → draft | Subscriber: `patient_timeline`. |
| `treatment_plan.treatment_added` | item added | snapshot payload (catalog_item_id, tooth, surfaces, unit_price, budget_id). Subscriber: `budget`. |
| `treatment_plan.treatment_removed` | item removed | payload includes `budget_id`. Subscriber: `budget`. |
| `treatment_plan.treatment_completed` | item marked done | consumed by `patient_timeline`, `recalls`. Payload includes `treatment_category_key` (snapshot, may be null) so subscribers can map a completed treatment to a follow-up policy without importing catalog or treatment_plan models (issue #62). Earned-ledger generation **moved out** of this event since the multi-session feature — see `item_session_completed` below. |
| `treatment_plan.item_session_completed` | one session of a multi-session item marked done | payload: `{plan_id, item_id, session_id, sequence, label, amount, treatment_id, patient_id, completed_by, occurred_at}`. Consumed by `payments` (earned entry, idempotent on `(treatment_id, session_id)`). Fires for every completed session — single-session items publish it once on completion. |
| `treatment_plan.budget_sync_requested` | manual resync | snapshot payload includes full `items[]`. Subscriber: `budget`. |
| `treatment_plan.item_completed_without_note` | completion check | consumed by `patient_timeline` |

Clinical-note created events (`clinical_notes.{administrative,diagnosis,treatment,plan}_created`) live in the `clinical_notes` module.

> All events above are declared in `EventType` and published via the
> constants. ``items_reordered`` used to be a string-only literal —
> it now lives at `EventType.TREATMENT_PLAN_ITEMS_REORDERED`.

## Events consumed

| Event | Handler | Effect |
|---|---|---|
| `appointment.completed`         | `on_appointment_completed`  | start the plan (`pending` → `active`) for every plan the appointment links to, then mark planned items as performed. The activation query is deliberately wider than the completion loop: it does not require `completed_in_appointment`, because a diagnostic first visit usually ticks nothing off and is exactly the visit that starts the plan. |
| `budget.accepted`               | `on_budget_accepted`        | pending → active (idempotent) |
| `budget.rejected`               | `on_budget_rejected`        | pending → closed (closure_reason=rejected_by_patient) |
| `budget.renegotiated`           | `on_budget_renegotiated`    | pending → draft (budget already cancelled by publisher) |
| `odontogram.treatment.performed` | `on_treatment_performed`   | mark planned item completed when its tooth treatment is performed |

## Lifecycle

- `removable=False`. Plans tie patients ↔ budgets ↔ tooth treatments;
  removing the module would orphan all three.

## Gotchas

- **`confirm` must always adopt the budget it was handed.** `reopen`
  cancels the linked budget but leaves `plan.budget_id` pointing at it.
  `create_from_plan_snapshot` is idempotent only against *non-cancelled*
  budgets, so a re-confirmation mints a fresh draft — and `confirm` has
  to store it. Guarding the assignment on `budget_id is None` (as it did
  until the reopen→re-confirm bug) stranded the plan in `pending` against
  a cancelled budget, which satisfies no bandeja `tab_where`, so the plan
  disappeared from the pipeline while the new budget floated unreferenced.
  Pinned by `test_reconfirm_after_reopen_links_the_fresh_budget`.
  The cascade is worse than the missing link suggests: `budget` finds the
  plan to activate with a reverse lookup on `treatment_plans.budget_id`
  (`BudgetWorkflowService._lookup_plan_id`), so an orphaned budget resolves
  to `plan_id: None`, `on_budget_accepted` takes its "orphan budget" early
  return, and accepting the budget never carries the plan to `active`. The
  budget could not even be *sent* — it was cancelled. Pinned end to end by
  `test_accepting_the_budget_after_a_reopen_still_activates_the_plan`.
- **`en_curso` spans two statuses on purpose.** The leading bandeja tab is
  `p.status IN ('pending', 'active')`. Reception counts a plan as under way
  from the diagnostic visit, which happens before the budget is accepted, so
  a tab keyed to `active` alone would hide exactly the plans they are chasing.
- **Plan → budget direct call is the carve-out.** `confirm()` calls
  `BudgetService.create_from_plan_snapshot` synchronously to keep the
  draft-budget creation transactional with the state transition.
  Allowed because `budget` is in `manifest.depends`. Item-level
  add/remove sync remains event-driven (the snapshot payloads carry
  enough data so `budget` doesn't import treatment_plan).
- **Plan ↔ budget item sync goes through events**, not direct calls.
  Adding a treatment to a plan publishes
  `treatment_plan.treatment_added` with a denormalized snapshot
  (catalog_item_id, tooth, surfaces, unit_price, budget_id); the
  budget module's handler creates the matching budget line.
- **Item completion has two paths**: the user marks an item complete
  here, or the odontogram fires `odontogram.treatment.performed`. Both
  must converge to the same state — keep them idempotent.
- **Sessions are the source of earned signal.** Every plan item now
  owns ≥1 `PlannedTreatmentItemSession` (backfilled by `tp_0006`).
  Per-session completion fires `item_session_completed`; the item
  finalizes (and `treatment_completed` fires) only when every session
  is in a terminal state and at least one is `completed`. Editing a
  completed session is refused — its amount is the snapshot that
  payments already booked.
- **Completion still emits an audit event.** `treatment_plan.item_completed_without_note`
  fires whenever an item is completed; the timeline reconciles it with a
  follow-up `clinical_notes.treatment_created` event when the client
  captured a note. Don't bypass — the event is the only signal that an
  item was completed at all.
- **Don't import `clinical_notes`.** The dependency is one-way:
  `clinical_notes → treatment_plan`. The frontend calls both modules
  during completion; do not add a server-side cross-module import.
- **A template carries treatments, never teeth.** `PlanTemplate` is an
  ordered list of catalog items with a stage of care; the teeth arrive at
  apply time. The apply rule is one sentence on purpose, because a dentist
  has to be able to predict it: **every per-tooth item is created once per
  tooth supplied, whole-mouth items once, and whole-arch items once per arch
  the teeth belong to (both arches when no teeth were given).** A template
  with per-tooth items and no teeth is refused with a 422 that names the
  treatments waiting, so the UI can ask for the right thing.
- **Hand-drawn lines take the template's path, not the item path.**
  `POST /catalog-items` goes through `PlanTemplateService.add_catalog_items`
  → `_create_treatments` → `add_item`, because turning a catalog item into
  planned `Treatment` rows is where all the scope logic lives (one per tooth,
  once per arch, once for the mouth). `POST /items` is the other door and
  takes a `Treatment` that already exists — that is the odontogram's path,
  and it cannot serve a client that only knows a catalog item id. The body is
  a **list of lines**, each with its own teeth: the plan is drawn on a chart,
  so a crown on 16 and a filling on 24 arrive together.
- **The create screen has no patient until the end, and that is the point.**
  `/treatments/plans/new` opens on a blank chart (`PlanDraftChart`, which
  shares `ToothQuadrant` with the real chart but fetches nothing) and holds
  the whole plan in client memory until *Crear*, which then creates the
  patient if new, the plan, and every line. Nothing is half-written if the
  screen is abandoned. The cost is that the chart cannot show what the
  patient already has, so the patient step re-reads their odontogram and
  **warns** — a missing tooth comes from `tooth_records.general_condition`,
  not from a treatment, and a check that only read treatments would warn
  about nothing.
- **A template line is either a given or a decision.** `is_optional` marks the
  ones a clinic may not offer or a patient may not need — the orthodontics of
  an orthognathic case, a genioplasty. Optional lines are offered **ticked**
  (the author put them there because they usually apply) and go out through
  `excluded_template_item_ids`. Excluding a *required* line is a 400: a
  template whose required steps can be dropped is not a shape any more.
- **`apply` reports what it left out.** A line whose catalog item the clinic
  never had or has retired is skipped instead of failing the whole
  application, and comes back in `skipped` with `reason="not_in_catalog"`.
  A plan that quietly arrives one treatment short is worse than one that says
  so. This is why `apply` returns `ApplyResult`, not a bare list.
- **`PlanTemplateService.get` uses `populate_existing`.** It is the read that
  runs straight after a write; without it the identity map hands back the
  collection as it was before `_replace_items`, and a PUT answers with the old
  line-up while the database holds the new one.
- **Templates are seeded from `clinic.created`, tolerantly.** The starter set
  lives in `templates_seed.py` and references catalog items by
  `internal_code`. Handler order against `catalog`'s own seeder is not a
  contract, so `PlanTemplateService.seed` skips codes that are not there yet,
  never overwrites a template the clinic edited, and fills in gaps on a
  re-run. `scripts/backfill_plan_templates.py` is the repair and
  existing-clinic path.
- **`_replace_items` writes by statement, not through the relationship.**
  It runs against templates that were just created and never loaded;
  touching `template.items` there triggers a lazy load the async session
  cannot service.
- **Proposals read the chart, they never write to it.** `proposals.py` lists
  findings (`Treatment` rows with a diagnostic `clinical_type`,
  `status='performed'`, no catalog link) that have no planned work on the same
  tooth, and pairs each with a catalog item resolved by `internal_code` from
  the `SUGGESTIONS` table. Accepting one creates a *new* planned Treatment;
  the finding is left alone, because the diagnosis and the plan are separate
  records and the chart should keep showing the caries until it is treated.
  The "already addressed" test is coarse on purpose — any planned treatment on
  that tooth hides the finding. Guessing whether a given plan line answers a
  given finding would be a guess.
- **`SUGGESTIONS` is clinical judgement in a table, so it stays conservative.**
  Where the honest answer depends on how much tooth is left, the least
  invasive option is proposed: upgrading a composite to a crown is a smaller
  correction than the reverse. Nothing is created until the dentist ticks the
  row.
- **The plan shows money it does not own.** `usePlanCollections` calls
  `POST /payments/summary/by-treatments` from the frontend layer — no backend
  import, nothing added to `manifest.depends`. That is the sanctioned
  cross-module read (`docs/technical/payments/cross-module-summaries.md`), the
  same one the budget and patient lists use. One call per plan feeds both the
  per-session chips and the per-phase totals; when it fails (payments not
  installed, or no `payments.record.read`) the plan renders without the money
  column, which is the correct degraded state.
- **A chip only appears once a session is earned.** A pending session is not
  "uncollected" — there is nothing to collect until the work is done, and
  saying otherwise reads as a debt the patient does not have.
- **A plan can start without an appointment ever existing.** Ticking a
  treatment off directly on the plan sets `completed_without_appointment`
  and creates no `appointment_treatments` row, so anything reasoning about
  "did the patient come" from appointments alone misses that path — it is
  how a first consultation often gets recorded.
  `scripts/backfill_started_plans.py` counts either signal and is the
  one-off pass for visits that predate the attendance rule; it is dry-run
  by default. The live path covers both since completion routes through
  `_sync_plan_lifecycle`.
- **Reopening is narrower than `plans.write`.** It throws away a budget the
  patient may already have seen, so the endpoint also asks `stewards_of`:
  an administrator, or a professional assigned to the plan or to any of its
  items. The account↔professional bridge is the licence number
  (`users.professional_id` ↔ `professionals.license_number`) because
  `Professional` deliberately has no `user_id`; a professional with no
  account resolves to nobody and the plan stays admin-only. Rights are
  derived from the current assignment, so reassignment transfers them with
  no extra bookkeeping. The client never reproduces this rule — it reads
  `permissions` off the history endpoint.
- **History rows share the caller's transaction.** `record_history` is not a
  coroutine and does not flush: a log line that outlives a rolled-back edit
  describes something that never happened.
- **Auto-close cron lives here** (`tasks.py:auto_close_expired_plans`),
  not in budget — closing a plan is a treatment_plan write and budget
  is in this module's depends, so the read of `budgets` from the
  cron query is allowed.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0003-event-bus-over-direct-imports.md`
- `docs/adr/0006-budget-public-link-2-factor-auth.md`

## CHANGELOG

See `./CHANGELOG.md`.
