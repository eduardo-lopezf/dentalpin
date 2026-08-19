---
module: agenda
last_verified_commit: 7406862
---

# Agenda — technical overview

Appointments are assigned to active clinic-directory profiles of type
`dentist` or `hygienist`. `appointments.professional_id` is a foreign key
to `professionals.id`, never to a product user account.

## API surface

- `DELETE /api/v1/agenda/appointments/{appointment_id}`
- `DELETE /api/v1/agenda/cabinets/{cabinet_id}`
- `GET /api/v1/agenda/appointments`
- `GET /api/v1/agenda/appointments/{appointment_id}`
- `GET /api/v1/agenda/appointments/{appointment_id}/cabinet-history`
- `GET /api/v1/agenda/appointments/{appointment_id}/transitions`
- `GET /api/v1/agenda/cabinets`
- `GET /api/v1/agenda/kanban/day`
- `PATCH /api/v1/agenda/appointment-treatments/{appointment_treatment_id}`
- `PATCH /api/v1/agenda/appointments/{appointment_id}/cabinet`
- `POST /api/v1/agenda/appointments`
- `POST /api/v1/agenda/appointments/{appointment_id}/transitions`
- `POST /api/v1/agenda/cabinets`
- `PUT /api/v1/agenda/appointments/{appointment_id}`
- `PUT /api/v1/agenda/cabinets/{cabinet_id}`

## Frontend

- `backend/app/modules/agenda/frontend/pages/appointments/index.vue` → `/appointments`

The professional picker, calendar columns and kanban strip all consume the
same directory records. Collaborators and inactive profiles cannot be booked.

## Permissions

`appointments.read`, `appointments.write`, `cabinets.read`, `cabinets.write`

See [`./permissions.md`](./permissions.md) for the full role mapping.

## Events

- **Emits:** _(none)_
- **Subscribes:** _(none)_

module participates in the event bus).

## See also

- Module CLAUDE notes: `backend/app/modules/agenda/CLAUDE.md`
- [Documentation portal contract](../../technical/documentation-portal.md)
