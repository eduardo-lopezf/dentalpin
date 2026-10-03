# 0042 — Core Apps must stay separable from the backend process

- **Status:** accepted
- **Date:** 2026-10-02
- **Deciders:** Eduardo (product owner)
- **Tags:** modules, apps, architecture

## Context

Every App runs today in one backend process against one database. The
Apps model ([ADR 0036](0036-an-app-is-a-declared-group-of-modules.md),
[0038](0038-apps-json-switches-apps-for-the-whole-deployment.md)) names
a set of **core Apps** — the ones every workspace is set up with:
Agenda, Patients, Recalls and Treatments, plus Professionals for a
workspace of the Clinic kind. Everything else is optional for now.

The long-term goal is that a core App can be taken out of the backend
container and run in its own. Nothing asks for that yet, and building it
now would buy operating cost for no benefit. But code written today can
quietly make it impossible: an import, a join, or two Apps' writes
sharing one transaction each weld two Apps into one deployable unit.

## Decision

**Code that crosses from one App to another is written so that it would
survive a process boundary.** No container is split by this ADR; it
fixes the rules that keep the split possible.

1. **Contracts carry plain data.** What crosses through
   `app/core/contracts.py` ([ADR 0039](0039-modules-reach-each-other-through-core-contracts.md))
   is a dataclass or a primitive — never an ORM row, a query, or
   anything bound to the caller's session.
2. **Contracts read; events write.** One App does not write another
   App's data inside its own operation. It commits its own change and
   publishes an event ([ADR 0019](0019-events-publish-after-commit.md));
   the other App reacts in its own transaction. A contract may answer a
   question about the other App's data. It may not change it.
3. **A reaction can be repeated.** A handler that creates something
   because of an event first checks that it is not already there.
4. **No new database coupling between Apps.** No new foreign key, ORM
   relationship or join from one App's tables into another's. The
   foreign keys that exist stay ([ADR 0035](0035-apps-are-disabled-not-uninstalled.md));
   they are the known list of what a split would have to replace.
5. **Hand-backs name the seams.** A change that leaves a cross-App
   shared-transaction or shared-session assumption in place says so.

## Consequences

### Good

- Extracting a core App later is a matter of replacing the transport
  under contracts and events, not of rewriting the Apps.
- Rule 2 is also what makes an optional App optional: a core App that
  finishes its own work without calling the optional one behaves the
  same whether that App is running, switched off, or elsewhere.

### Bad / accepted trade-offs

- **What used to be atomic becomes eventual.** Confirming a treatment
  plan no longer returns its budget in the same response: the budget
  appears a moment later, and a failure to create it no longer undoes
  the confirmation. Failures are recorded
  ([ADR 0020](0020-handler-failures-are-recorded.md)), not retried, so
  the screen has to offer a way to ask again.
- **Existing contracts take the caller's `db` session.** They assume a
  shared database. That is enough for "same database, several
  containers" and not for separate databases; the provider
  implementations would be rewritten, their callers would not.
- **The event bus is in-process.** It is the first thing to replace
  before any App leaves the process.
- Contracts written before this ADR are not all read-only
  (`ProfessionalDirectory.ensure_profile`, `profile_for_account`). They
  stay as known exceptions and are not to be imitated.

## Alternatives considered

- **Split now** — operating several services and distributed
  consistency, for a product that one process serves well.
- **Decide when the need comes** — by then the coupling is written. The
  cheap moment to keep a seam open is while the code on both sides of
  it is being touched anyway.
- **Write contracts for writes too** — keeps today's behaviour, and is
  exactly the cross-App transaction that a split cannot keep.

## First application: a plan and its budget

`treatment_plan` used to call `BudgetService` inside its own transaction
to create, cancel and delete budgets (the carve-out of
[ADR 0003](0003-event-bus-over-direct-imports.md)). It no
longer does. Confirming, reopening and deleting a plan publish events;
`budget/plan_quotes.py` reacts and announces `budget.created_for_plan`,
which the plan turns into its link. The two things a person asks for by
name — generate the budget, price what was added — became `budget`
endpoints that read the plan through `PlanQuotes`.

Seams left in place, per rule 5: `budget` still reads `treatment_plans`
with raw SQL in two places (`_lookup_plan_id`, `belongs_to_plan`), and
the plan pipeline and one scheduled task join `budgets` the same way.

## Second application: events carry what the listener needs

`treatment_plan` read `appointment_treatments` to learn what a completed
visit had covered. `agenda` now says so in the event
(`planned_items` on `appointment.completed`), and the plan acts on the
payload alone. Together with `ProfessionalDirectory` for assignments and
the attachment-owner registry moving to `app/core/attachments.py`, the
Treatments App imports and requires one module outside itself:
`patients`.

## How to verify the rule still holds

- `backend/tests/test_app_isolation.py` — what every App may import and
  require, pinned per App ([ADR 0044](0044-the-app-organises-the-module-holds-the-code.md)).
- `backend/tests/test_agenda_integration_matrix.py`,
  `backend/tests/test_treatments_app_isolation.py` — how the core Apps
  behave with others off.
- Review: a new method in `app/core/contracts.py` that changes another
  App's data needs a reason written next to it.

## References

- `backend/app/core/contracts.py`
- `backend/apps.json`
- [ADR 0037](0037-a-module-integrates-with-what-it-can-live-without.md)
