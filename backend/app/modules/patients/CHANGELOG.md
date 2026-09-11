# Changelog — patients module

## Unreleased

- feat(patients): la tarjeta de identidad de *Info* pasa a ficha, con el
  mismo lenguaje visual que `ProfessionalProfileModal`: banda tintada,
  retrato apoyado en su borde, el nombre como título y los datos en
  mosaico de casillas en lugar de lista de definiciones. Una lista se lee
  de arriba abajo y obliga a rastrear la línea que buscas; el mosaico deja
  que el ojo aterrice en ella. Mismos campos, ninguno añadido ni quitado;
  la fecha de nacimiento se dibuja siempre, el resto sólo si tiene valor.

  Se cae la cabecera "Datos personales": la tarjeta abría con ese título y
  repetía el nombre debajo, dos títulos para una sola cosa. Ahora el nombre
  es el encabezado y `aria-labelledby` apunta a él.

  El botón pasa a llamarse **Editar datos generales** (clave
  `patients.editDemographics`, es y en). La clave `patients.demographics`
  ("Datos demográficos") ya no la usa nadie — queda señalada, no borrada.

- fix(patients): la fecha de nacimiento se leía un día antes. `date_of_birth`
  es una columna DATE y `new Date('1985-03-12')` la interpreta como
  medianoche UTC, así que al oeste de Greenwich el día local retrocede: la
  ficha decía 11/03/1985 mientras el formulario de edición, justo al lado,
  decía 12/03/1985. Ahora usa `formatDateOnly` (`~~/app/utils/date`), que ya
  existía por este mismo fallo en presupuestos y nunca se propagó.

  `computeAge` tenía la misma raíz y hacía cumplir años un día antes. Había
  **tres** copias de esa aritmética —el helper, `PatientStickyHeader` y
  `[id].vue`—, cada una con el fallo; ahora las tres pasan por `computeAge` /
  `isMinorPatient`, que es lo que impide que el arreglo se deje una fuera.
  La de `[id].vue` decidía si mostrar la tarjeta de tutor legal: un paciente
  dejaba de ser menor un día antes de cumplir 18.

  `formatPatientDate` se queda como está —sus otros dos llamantes le pasan
  instantes reales— pero ahora lo dice en su documentación.
  `frontend/tests/patients/patientDates.test.ts` fija los bordes con el
  runner anclado a la zona de la clínica; en UTC el fallo es invisible.

- fix(buscador): buscar sin acentos no encontraba a los pacientes. `ILIKE`
  ignora mayúsculas pero **no** las tildes, así que «Fernandez» no devolvía
  nada y «Garcia» solo encontraba a quien tenía el email escrito sin tilde
  —por casualidad—, mientras que el paciente sin email era invisible. Ese
  acierto accidental es lo que hacía el fallo difícil de ver: parecía que el
  buscador funcionaba. Ahora ambos lados se pliegan con `translate()`.
  El resto de la búsqueda ya estaba bien (por palabras, con nombre completo,
  teléfono, email y documento) y no se toca.
  El plegado vive en `app/core/utils/search.py` porque `treatment_plan` lo
  necesita igual y no puede importar de `patients` — ni al revés.
- fix(ui): en tablet vertical, las seis pestañas de la ficha del paciente
  quedaban en puntos suspensivos («Res…», «Admini…», «G…») porque Nuxt UI
  reparte el ancho entre ellas. Ahora la tira conserva su ancho natural y
  se desplaza en horizontal. Se aplica solo a la lista (`ui.list`), no al
  componente entero: los paneles conservan `overflow-visible`, del que
  dependen los hijos fijos. Mismo criterio que en la bandeja de planes.

- feat(privacy): `get_subject_contributors()` — this module now answers
  for its own data when a patient exercises portability or erasure
  ([ADR 0026](../../../../docs/adr/0026-subject-rights-are-a-module-contract.md)).
  Exports the identity row; erasure scrubs the classified columns plus
  date of birth and address (quasi-identifiers) and archives the row
  rather than deleting it, because invoices and appointments point at it.

- fix(schemas): `national_id_type` accepted only `curp`/`ine`/`passport`,
  so every patient imported from Gesdén (labelled `nif` by
  `migration_import`) 422'd on the first save of their demographics — the
  edit modal loads the stored value and sends it back untouched. The
  accepted set is now the union of both markets the deployment serves,
  grouped by jurisdiction in `NATIONAL_ID_TYPES_BY_JURISDICTION` so that
  narrowing it per tenant later is a rewiring rather than a
  rediscovery. Existing rows become valid without a data migration.

- fix(privacy): classified this module's personal columns with `pii()`
  so the copilot's PHI boundary derives them from the schema instead of a
  hand-kept list ([ADR 0025](../../../../docs/adr/0025-pii-is-classified-on-the-column.md)).

- fix(i18n): the `search_patients` tool told the model it could search by
  "DNI/NIE". `Patient.national_id` holds a CURP, INE or passport (the
  schema validator accepts nothing else), so the description now names
  those. The searched fields are unchanged.

- fix(i18n): the billing tax-id field was labelled "NIF/CIF" in Spanish
  while every other tax-id label in that locale (`setup`, `settings`,
  `invoice`) already said RFC, and its placeholder was hardcoded in the
  template instead of going through `t()`. Label is now "RFC" and the
  placeholder moved to `patients.billingTaxIdPlaceholder` in both locales.

- fix(ui): removed the "linked to plan" badge from the administration
  tab — `treatment_plan_id` exists nowhere in the budget module, so the
  badge could never render.

- fix(events): publish through ``event_bus.publish_after_commit(db, ...)``
  instead of announcing from inside the caller's open transaction.
  Handlers read through their own sessions, so a flushed-but-uncommitted
  row was invisible to them (audit S2). See
  [ADR 0019](../../../../docs/adr/0019-events-publish-after-commit.md).

- fix(events): include `clinic_id` in the `patient.archived` and
  `patient.updated` payloads (audit event-bus #11, #95). Every event
  must carry the tenant per the multi-tenancy convention; the omission
  broke the media archive cascade and forced the recalls handler into an
  unscoped query.

- feat(agents): new copilot tool `update_patient` (WRITE) — updates a
  patient's contact data (phone, email) via `PatientService.update_patient`.
  Identity fields stay manual.

- fix(search): multi-term patient search. `PatientService.list_patients`
  now splits the `search` string on whitespace and requires **every**
  term to match **some** field (AND across terms, OR across fields),
  matching against `first_name`, `last_name`, the concatenated full
  name, `phone`, `email` and `national_id`. Fixes "Nombre Apellido"
  (and reversed "Apellido Nombre") returning no results — previously the
  whole input was one substring ILIKE'd against each field separately,
  so a name split across `first_name`/`last_name` never matched. Same
  fix reaches the copilot `search_patients` tool (shared service path);
  its arg description now tells the agent to pass the full name as one
  query. No frontend change — UI already routes through this service.

- feat(agents): expose `tools.py` for the copilot agentic layer —
  `search_patients`, `get_patient` (READ), `create_patient` (WRITE).
  Thin wrappers over `PatientService`; clinic-scoped; RBAC via existing
  `patients.read`/`patients.write`. Issue #81 Layer B.

- feat(ux): patient list default sort changed from ``last_name:asc`` to
  ``last_visit:desc`` so patients seen most recently surface first.
  ``last_visit`` is computed via a ``MAX(start_time) GROUP BY patient_id``
  subquery against the ``agenda.appointments`` table, LEFT JOINed with
  NULLS LAST so never-seen patients fall to the bottom. The patients
  module keeps ``depends = []``: the appointments table is referenced
  via ``sqlalchemy.table()`` rather than importing the ``Appointment``
  model — same workaround as ``get_recent_patients``. ``updated_at`` is
  also exposed as an opt-in sort field. Frontend sort menu order:
  Última visita, Apellidos, Nombre, Registro, Editado recientemente.
- feat(ux): ``PatientVisualSelector`` (shared) gains an inline "create patient" mode. When the typed query has no match and the user has ``patients.write``, a footer row in the search dropdown opens a 3-field mini-form (nombre, apellidos, teléfono). Submitting POSTs ``/api/v1/patients`` and emits the selection upward. Includes soft-duplicate phone lookup (debounced + ``AbortController``-cancelled) reusing ``GET /patients?search=``. No backend changes — feeds into the agenda's *Nueva cita* flow. See ``docs/features/agenda-quick-patient-create.md``.
- feat(ux): redesigned patient detail as a dashboard-first IA. The
  Resumen tab is now a grid of slot-driven smart cards (Plan, Próxima
  cita, Saldo, Diagnósticos, Historial médico, Acciones rápidas) plus
  the clinical-notes feed. A persistent ``PatientStickyHeader``
  replaces the dense left rail and stays visible across every tab.
  Mobile gets a ``PatientBottomActionBar`` with the three most-used
  actions (cita, cobrar, nota). Saves one click to Plan, Cobros,
  Próxima cita and Odontograma.
- feat(slots): exposes two new slot contracts: ``patient.summary.cards``
  (grid entries on Resumen) and ``patient.header.alerts`` (chips in the
  sticky header). The existing ``patient.summary.actions`` slot is
  preserved and now renders both in the sticky header and in the
  Quick-Actions card. Each smart card lives in (and is registered by)
  its owning module — ``patients`` keeps ``depends = []``.
- refactor: dropped ``PatientSummaryHero.vue`` and the legacy
  ``ActivePlanWidget`` / ``NextAppointmentWidget`` props pipeline. The
  page no longer reaches into agenda or treatment_plan APIs to compute
  widgets; each module fetches its own data inside its card.
- chore(shared): ``SegmentedControl`` accepts ``badge`` /
  ``badgeColor`` per option and a ``fullWidth`` mode so the
  Clínica/Administración sub-nav can surface contextual counts.
- refactor(perms): migrate the hardcoded ``can('payments.record.read')`` gate on the patients list to ``PERMISSIONS.payments.recordRead``.
- fix(isolation): drop the cross-module ORM coupling to ``agenda`` and
  ``patient_timeline``. ``Patient`` no longer declares
  ``relationship(back_populates=...)`` to ``Appointment`` /
  ``PatientTimeline`` (the foundational module cannot point at
  consumers) — the sibling side keeps a one-directional reference.
  ``get_recent_patients`` no longer lazily imports
  ``agenda.models.Appointment``; it reads ``appointments`` through a
  raw SQL fragment with the same fallback semantics.
- perf(list): drop subquery-count anti-pattern; count uses
  ``COUNT(Patient.id)`` over the same filter set as the data query.
- perf(indexes): new migration ``pat_0003_recall_filter_indices`` adds
  ``(clinic_id, status)`` and a partial ``(clinic_id)`` where
  ``do_not_contact = false`` so recalls / outreach list builders
  stop falling back to a full table scan once a clinic accumulates
  patients.

### Added (lists redesign, 2026-05-14)

- `GET /api/v1/patients` accepts new params: `patient_ids[]`, `city`,
  `do_not_contact`, `include_archived`, `sort=field:dir` (whitelist:
  `last_name`, `first_name`, `created_at`).
- New slots exposed on `/patients` list page: `patients.list.filter`
  (toolbar chip injection) and `patients.list.row.financial` (per-row
  cell injection). Payments module registers fillers for "Con deuda"
  toggle + debt badge.
- List page rewritten on `DataListLayout` + `FilterBar` +
  `useListQuery`. Card view <md, URL-synced filters, sort dropdown,
  status/city/do-not-contact filters.

- **`do_not_contact: bool` flag** added to the patient model
  (issue #62, recalls). Operational opt-out — patients with this flag
  set are excluded from the recalls call list and any future
  outreach automation. Defaults to `false`. Editable from the
  Demographics edit modal. Migration: `pat_0002`.
- New slot mount `patient.summary.actions` rendered on
  `PatientSummaryHero` so sibling modules (e.g. `recalls`) can
  contribute action buttons to the patient summary without modifying
  the patients module UI.
- New slot `patient.detail.administracion.payments` exposed inside
  `AdministrationTab` (ctx: `{ patient, patientId }`). Optional
  sub-mode "Pagos" appears in the segmented toggle only when the slot
  has at least one provider visible to the user — the `payments`
  module registers a panel here. Patients module stays free of any
  payments imports; the contract is the slot name alone. URL
  `?adminMode=payments` falls back to `budgets` when the slot is
  empty.

- Patient detail → Administración → Presupuestos: paginated (page_size=20).
  `AdministrationTab` now owns its own paginated fetch via the shared
  `PaginationBar`; the parent `[id].vue` no longer prefetches budgets.
- Added per-module `CLAUDE.md` for AI-agent context (2026-04-27).
- Issue #60: patient detail page lands on a new **Summary** tab by
  default (replaces Info as default; Info stays accessible via tab
  list and `?tab=info`). Summary renders `patient.summary.feed` slot —
  filled by the clinical_notes module.
- Removed left sidebar (`PatientQuickInfo`) from patient detail. All
  tabs now span full width. Sidebar widgets (avatar, status, alerts,
  contact strip, active plan, next appointment, emergency contact)
  collapsed into a new `PatientSummaryHero` rendered at the top of
  the **Summary** tab. The `patient.detail.sidebar` slot is preserved
  by re-mounting it inside the hero so community modules keep their
  extension point.
- **Summary** tab now uses a 2-column layout: a sticky left rail
  (`PatientSummaryHero`) and a main column for the clinical-notes feed.
  Other tabs (info, clinical, administration, timeline) keep their
  full-width layout.

## 0.1.0 — initial

- Patient identity model: name, contact, demographics, `status`.
- `/api/v1/patients/*` CRUD with soft-delete via archive.
- Events: `patient.created`, `patient.updated`, `patient.archived`.
- Permissions: `patients.read`, `patients.write`.
