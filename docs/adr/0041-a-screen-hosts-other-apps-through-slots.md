# 0041 — A screen hosts other Apps through slots, never by naming them

- **Status:** accepted — applied to the Patients App
- **Date:** 2026-10-02
- **Deciders:** Eduardo (maintainer)
- **Tags:** frontend, modules, apps, patients

## Context

`patients` declares no dependency and imports no module on the backend.
Its frontend was the opposite. The patient record is where every other
App shows its part of a patient, and it did so by naming them: thirteen
components and one composable from eight modules, and direct calls to
three modules' APIs. None of it was declared, and none of it was
checked — the backend has had an isolation test for years, the frontend
had none.

So `patients` could not lose a single neighbour. With Treatments off the
Clínico tab rendered against an API that answered 404; a link carrying
`?tab=clinical` opened on an empty panel.

Two of the tabs were not even `patients`' to begin with. Clínico is
diagnosis, plans and appointments; Administración is budgets, invoices,
payments and documents. `patients` only held the file.

## Decision

**A screen that shows another App's part of something offers a slot.
The other App registers into it. The host never names the guest.**

- **Tabs.** The patient record takes its tabs from
  `patient.detail.tabs`. An entry carries `tab: { value, icon }` and a
  `labelKey`; `value` is what `?tab=` carries and must stay stable.
  Resumen, Info and Actividad are the App's own. Clínico is registered
  by `treatment_plan`, Administración by `budget`, Galería by `media`.
  A tab comes with its module and goes with it; a link to a tab that is
  not there opens the summary.
- **A tab belongs to whoever owns what is in it.** `ClinicalTab` and
  `DiagnosisModeContainer` moved to `treatment_plan`;
  `AdministrationTab` and its toggle to `budget`. Inside
  Administración, invoices, payments and documents are slots of their
  own (`patient.detail.administracion.<mode>`), because `billing` and
  `payments` depend on `budget` and a slot is the only direction that
  works.
- **Data comes through the slot too.** A list that needs another
  module's data for a whole page of rows calls the entry's `loader`,
  passing its own API client. The patients list gets debt badges and the
  "Con deuda" filter this way; the endpoints live in `payments`.
- **The Patients App is `patients`, `patients_clinical` and
  `patient_timeline`.** What the three use of each other is internal
  and stays as it is.
- **It is checked.** `frontend/tests/app-frontend-isolation.test.ts`
  reads the App's source and fails on a component or an `/api/v1/` path
  that belongs to a module outside it.

## Consequences

### Good

- Switching off Treatments, Agenda, Media or the finance modules removes
  their tabs and modes from the patient record and leaves the rest
  working, with no request to an API that is not there.
- The files live with the module that maintains what is in them.
- One request per page still: the `loader` keeps the bulk fetch the
  list always made.

### Bad / accepted trade-offs

- **The tab strip is client-only.** Slot registrations run in
  `slots.client.ts`, so the server cannot know the tabs; the strip
  renders after hydration behind a skeleton.
- **A slot's `ctx` and `loader` shapes are a contract kept by
  convention**, documented beside the registration. Nothing types the
  two ends against each other.
- **`with_debt` is still the name of the list's module filter** in the
  URL and in the page's state. The page no longer knows what it calls,
  but the word is `payments`'.
- **A guest's frontend is compiled whether or not its module runs.**
  Its registration plugin still executes with the module off, so what
  hides a tab or a mode is its *permission* — nobody holds a module's
  permissions while it is not mounted. A registration with a condition
  wider than its own module (`budget.read || billing.read`) therefore
  stays visible, and what it renders must cope: with Budgets off the
  Administración tab remains, without its Budgets mode.
- **Not everything is decoupled.** `patients_clinical` still depends on
  `professionals` on the backend (clinical entries name a licensed
  author), and `patient_timeline`'s demo seed imports five modules.
  Both are outside what this ADR changes.

## Alternatives considered

- **Keep the tabs in `patients` with a slot per mode.** Less moved, but
  `patients` would keep owning the coordination between diagnosis and
  plans, which is not its business.
- **Guard each embedded component with "is the module running".** The
  host still names every guest, and every new guest edits the host.

## How to verify the rule still holds

- `frontend/tests/app-frontend-isolation.test.ts`.
- By hand, 2026-10-02, with a module off: Treatments off removes
  Clínico and two summary cards; Media off removes Galería and the
  Documents mode; Budgets off leaves Administración with invoices,
  payments and documents; all three off leaves Resumen, Info,
  Administración and Actividad. In every case a link to a missing tab
  opens Resumen and no request fails.
- By hand, 2026-10-02: the six tabs of a patient record render with the
  same content as before the move, the four Administración modes
  switch, `?tab=clinical` opens Clínico and an unknown tab opens
  Resumen; the patients list shows its debt badges and filters by debt,
  with the same two requests to `payments`.

## References

- `backend/app/modules/patients/frontend/pages/patients/[id].vue`, `index.vue`
- `backend/app/modules/treatment_plan/frontend/components/patient/`
- `backend/app/modules/budget/frontend/components/patient/`
- `backend/app/modules/media/frontend/plugins/slots.client.ts`
- `frontend/app/composables/useModuleSlots.ts` (`tab`, `loader`)
- [ADR 0037](0037-a-module-integrates-with-what-it-can-live-without.md), [ADR 0039](0039-modules-reach-each-other-through-core-contracts.md)
