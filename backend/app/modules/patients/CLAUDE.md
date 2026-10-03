# Patients module

Patient identity: name, contact, demographics, status. Foundational
module — most other modules depend on it. Soft-deleted via `status`,
never hard-deleted.

## Public API

Routes mounted at `/api/v1/patients/`.

- `GET    /patients`        — list (paginated); `patients.read`
- `GET    /patients/{id}`   — detail; `patients.read`
- `POST   /patients`        — create; `patients.write`
- `PUT    /patients/{id}`   — update; `patients.write`
- `DELETE /patients/{id}`   — soft-archive (status → archived); `patients.write`

## Dependencies

`manifest.depends = []`. Foundational. **Other modules may declare
`depends: ["patients"]`** — keeping this module stable matters for the
whole system.

## Permissions

`patients.read`, `patients.write` (declared relative; registry
namespaces them).

## Tools exposed

Agent tools in `tools.py` (wrap `PatientService`, no logic duplicated).

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `search_patients` | READ | `PatientService.list_patients` | `patients.read` |
| `get_patient` | READ | `PatientService.get_patient` | `patients.read` |
| `create_patient` | WRITE | `PatientService.create_patient` | `patients.write` |
| `update_patient` | WRITE | `PatientService.update_patient` | `patients.write` |

`update_patient` covers contact data only (phone, email) — identity
fields stay manual.

## Events emitted

| Event | When | Payload keys |
|---|---|---|
| `patient.created` | `PatientService.create` succeeds | `patient_id`, `clinic_id` |
| `patient.updated` | `PatientService.update` succeeds | `patient_id`, `clinic_id`, `changes` |
| `patient.archived` | `PatientService.archive` (soft-delete) | `patient_id`, `clinic_id` |

See `service.py:113`, `service.py:131`, `service.py:142`.

## Events consumed

None.

## Lifecycle

- `installable=True`, `auto_install=True`, `removable=False` —
  removing patients would orphan most of the system.

## Gotchas

- **Soft delete only.** `DELETE /patients/{id}` flips `status` to
  archived; the row stays. Do not add a hard-delete endpoint.
- **Multi-tenancy.** Every query MUST filter `Patient.clinic_id`.
  This includes future agent tools.
- **No cross-module FKs into patients without `depends: ["patients"]`**
  in the consuming module's manifest.
- **`do_not_contact` flag** — operational opt-out used by recalls and
  any future outreach module. Sibling modules MUST filter
  `Patient.do_not_contact == False` in addition to the
  `Patient.status != "archived"` filter when building call/outreach
  lists.
- **Patient-detail slots** — three stable contracts exposed by this
  module so siblings can plug into the patient file without imports:
  - `patient.summary.cards` — entries in the Resumen grid. Ctx
    `{ patient }`. Order convention: 10 plan, 20 next appointment,
    30 balance, 40 diagnoses, 50 medical history, 60 quick actions.
  - `patient.header.alerts` — clinical chips inside
    ``PatientStickyHeader``. Ctx `{ patient }`. Owner: ``patients_clinical``.
  - `patient.summary.actions` — module-contributed action buttons
    (recalls "Set recall", etc.). Rendered in both the sticky header
    and the Quick-Actions card. Ctx `{ patient }`. Kept under its
    legacy name so existing registrations keep working.
  - `patient.detail.tabs` — the tabs of the patient record that are
    not this App's (ADR 0041). Entry: `tab: { value, icon }`,
    `labelKey`, `order`; component receives `ctx: { patient }`.
    `value` is what `?tab=` carries. Today: Clínico (`treatment_plan`,
    30), Administración (`budget`, 40), Galería (`media`, 50). Resumen,
    Info and Actividad are built in.
  - `patient.detail.administracion.{billing,payments,documents}` —
    modes of the Administración tab, which `budget` owns. Each is
    filled by its module (`billing`, `payments`, `media`).
  - `patients.list.row.financial` / `patients.list.filter` — the entry's
    `loader(api, input)` supplies the data: per-row values for a page of
    patient ids, and the ids a filter selects. This module calls no
    other module's API.
  - `patient.detail.sidebar` — deprecated, kept registered for
    community modules. Renders as a section at the bottom of Resumen.
  - `patient.diagnosis.subtabs` — optional sub-tabs rendered inside
    the *Diagnosis* mode of `ClinicalTab`, alongside the implicit
    "Odontograma" tab. Ctx `{ patientId, readonly? }`. Order
    convention: 10 odontogram (implicit), 20 periodontogram. With
    zero registered entries `DiagnosisModeContainer.vue` falls back
    to the bare `<DiagnosisMode>` render — uninstalling every
    optional consumer restores the pre-slot UI verbatim.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0003-event-bus-over-direct-imports.md`
- `docs/adr/0005-relative-permissions.md`

## CHANGELOG

See `./CHANGELOG.md`.

## Frontend isolation

The Patients App (`patients`, `patients_clinical`, `patient_timeline`)
uses no component and calls no API of a module outside it (ADR 0041);
`frontend/tests/app-frontend-isolation.test.ts` enforces it. To show
another App's part of a patient, offer a slot and let that App register
— do not import its component here.
