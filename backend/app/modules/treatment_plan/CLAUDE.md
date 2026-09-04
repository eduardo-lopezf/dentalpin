# Treatment plan module

Patient treatment plans with budget + odontogram sync. **Heaviest
`depends` in the system** — this module is an integration hub. Read
this file before changing any cross-module flow.

## State machine

```
draft ──confirm──► pending ──accept──► active ──complete──► completed
  ▲                  │                    │
  │                  │ rejected/expired   │ cancelled by clinic
  │                  ▼                    ▼
  └─── reactivate ◄──────  closed  ◄─────┘
                       (closure_reason)
```

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
- `POST  /treatment-plans/{id}/reopen`      — pending → draft, cancels linked budget
- `POST  /treatment-plans/{id}/close`       — `plans.close`; any → closed
- `POST  /treatment-plans/{id}/reactivate`  — `plans.reactivate`; closed → draft
- `POST  /treatment-plans/{id}/contact-log` — record reception touchpoint
- `GET   /treatment-plans/pipeline`         — bandeja (5 tabs)
- `POST  /treatment-plans/{id}/apply-template` — append a template; `plans.write`
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
| `appointment.completed`         | `on_appointment_completed`  | mark planned items as performed if linked |
| `budget.accepted`               | `on_budget_accepted`        | pending → active (idempotent) |
| `budget.rejected`               | `on_budget_rejected`        | pending → closed (closure_reason=rejected_by_patient) |
| `budget.renegotiated`           | `on_budget_renegotiated`    | pending → draft (budget already cancelled by publisher) |
| `odontogram.treatment.performed` | `on_treatment_performed`   | mark planned item completed when its tooth treatment is performed |

## Lifecycle

- `removable=False`. Plans tie patients ↔ budgets ↔ tooth treatments;
  removing the module would orphan all three.

## Gotchas

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
