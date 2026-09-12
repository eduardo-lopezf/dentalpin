# Agenda module

Appointments, scheduling, cabinets. Owns the `Appointment` entity and
its state machine.

## Public API

Routes mounted at `/api/v1/agenda/`. See `router.py` for the full
surface (appointments CRUD, transitions, cabinet assignments, kanban).

## Dependencies

`manifest.depends` includes `professionals`: appointments reference the
clinic directory's `professionals.id`, never a product-account ID.

## Permissions

`agenda.appointments.{read,write}`, `agenda.cabinets.{read,write}`.

## Tools exposed

Agent tools in `tools.py` (wrap `AppointmentService`, no logic duplicated).
Write tools use `ctx.supervisor_id` (the human in the loop) for audit columns.

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `get_day_overview` | READ | `AppointmentService.list_appointments` | `agenda.appointments.read` |
| `get_appointment` | READ | `AppointmentService.get_appointment` | `agenda.appointments.read` |
| `list_cabinets` | READ | `CabinetService.list_cabinets` | `agenda.cabinets.read` |
| `list_professionals` | READ | `kanban_service._fetch_professionals` | `agenda.appointments.read` |
| `book_appointment` | WRITE | `AppointmentService.create_appointment` | `agenda.appointments.write` |
| `reschedule_appointment` | WRITE | `AppointmentService.update_appointment` | `agenda.appointments.write` |
| `update_appointment_status` | WRITE | `AppointmentService.transition` | `agenda.appointments.write` |
| `cancel_appointment` | DESTRUCTIVE | `AppointmentService.cancel_appointment` | `agenda.appointments.write` |

`update_appointment_status` excludes `cancelled` (that's `cancel_appointment`,
DESTRUCTIVE). Invalid transitions return the allowed next states from
`VALID_TRANSITIONS` so the agent can self-correct instead of retry-looping.

`find_free_slots` is intentionally **not** here — free-slot computation belongs to
`schedules`, which will register its own tool. Agenda does not cross that boundary.

## Frontend slots exposed

- `appointment.completed.followup` — rendered by `AppointmentQuickActions.vue`
  after a successful transition to `completed`. Sibling modules
  (e.g. `recalls`) register components that prompt the receptionist
  for a follow-up action. Modal stays hidden when no registrations
  exist. Slot ctx: `{ appointment }`.

## Events emitted

- `appointment.scheduled` — new appointment
- `appointment.updated` — generic update
- `appointment.status_changed` — published alongside specific status events; payload carries `from_status`/`to_status`/`changed_at`/`changed_by`
- `appointment.cabinet_changed` — cabinet (re)assignment, payload includes `from_cabinet_id`/`to_cabinet_id` (nullable)
- `agenda.visit_note_updated` — visit-level note (reuses `AppointmentTreatment.notes`)

## Events consumed

None.

## Lifecycle

- `removable=False`. Most modules depend on appointments.

## Gotchas

- **Schedules must NOT be a dependency.** The `schedules` module depends
  on agenda; the data flow is one-way. Never declare
  `depends: ["schedules"]` here. See `schedules/CLAUDE.md`.
- **Status transitions go through `AppointmentService.transition`** —
  it publishes both the specific status event and the generic
  `appointment.status_changed`.
- **Cabinet assignment uses `assign_cabinet`** — it publishes
  `appointment.cabinet_changed` with both old and new ids.
- **Mobile free-slot computation is client-side** (#61). The composable
  `frontend/composables/useFreeSlots.ts` derives gaps from already-loaded
  appointments + the optional `schedules` availability payload. Do not
  add a backend free-slot endpoint without ADR — the data flow stays
  client-side and the schedules dependency stays optional.
- **Professional identity.** `Appointment.professional_id` is a directory
  profile that is active and of type `dentist` or `hygienist`.
- **The grids drag on Pointer Events, never mouse events.** The week and
  day grids share `composables/useSlotGridDrag.ts`; the kanban has its
  own pointer implementation because it hit-tests columns rather than
  snapping to a slot. Do not reintroduce `mousedown`/`mousemove` or HTML5
  `draggable` here — Chrome on Android delivers neither while a finger is
  moving, which is how create, move and resize came to be silently
  broken on tablets. See `docs/technical/touch-adaptation.md`.
- **`start_time` / `end_time` are the clinic's wall clock, not instants.**
  The offset they carry is a storage artifact. Read them with
  `wallClockDate` / `formatWallClockTime` / `parseIsoParts` from
  `frontend/utils/date.ts`; serialize day boundaries with `toWallClockIso`.
  Plain `new Date(start_time)` moves the hands by the browser's offset and
  is how the same appointment came to be drawn at 12:00 on the grid and
  06:00 on the kanban card, listed at 11:30 in the patient record while the
  calendar said 17:30, counted as upcoming after it had happened, and filed
  under the previous day in deep links and per-day counts. Comparing two
  appointments with `new Date()` is fine — both shift equally — but
  anything that renders, buckets by day, or compares against *now* is not.
- **"Today" on the dashboard is the clinic's day.** `useHomeAgenda`
  resolves it through `clinicTimezone`; the greeting above those tiles does
  the same. Reading the browser's day instead put the header and the tile
  on different dates for anyone working outside the clinic's zone.
- **Calendar geometry reads `useDensity().effective`, not `density`.**
  The preference can say "compact" while a coarse pointer forces the
  touch scale; reading the preference puts the drag maths 10 px per slot
  out of step with the CSS variable that is actually drawn.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0003-event-bus-over-direct-imports.md`

## CHANGELOG

See `./CHANGELOG.md`.
