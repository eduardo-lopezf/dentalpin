# Agenda (`agenda`)

- **Tier:** core  ·  **Version:** 0.1
- **Declared in:** `backend/apps.json`  ·  **Composition and requirements:** [Apps catalog](../../apps-catalog.md)

## What it is for

Appointments, cabinets, the day board (kanban) and the opening hours of the clinic and of each professional.

## Modules

- [`agenda`](../../technical/agenda/overview.md) — code in `backend/app/modules/agenda/` ([notes](../../../backend/app/modules/agenda/CLAUDE.md))
- [`schedules`](../../technical/schedules/overview.md) — code in `backend/app/modules/schedules/` ([notes](../../../backend/app/modules/schedules/CLAUDE.md))

## With this App off

The Agenda menu entry and its pages go; other Apps keep working and say "No se pueden crear citas" where they offered to book (`useAppointmentBooking`).

## Notes

- Requires no other App. With Patients, Professionals or Treatments off it still books: an appointment can carry just a title, and the missing pickers are replaced by a notice.
- It offers the `AppointmentBook` contract, and `appointment.completed` says which planned treatments a visit covered.
- API declared: Google Calendar (planned).

## Decisions

- [0037](../../adr/0037-a-module-integrates-with-what-it-can-live-without.md)
- [0039](../../adr/0039-modules-reach-each-other-through-core-contracts.md)
