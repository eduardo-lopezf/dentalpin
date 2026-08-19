---
module: professionals
last_verified_commit: 7406862
---

# Professionals — technical overview

The professionals module owns the clinic-local directory of dentists,
hygienists and collaborators. It is independent from authentication accounts,
so external specialists can have a profile without being able to sign in.

## Data

`professionals` is scoped by `clinic_id` and stores the person's name, type,
specialty, professional-license number, contact fields, profile photo URL,
notes and active status. Records are deactivated with `is_active` rather than
deleted.

Agenda and Schedules reference the profile ID directly. Only active dentists
and hygienists are schedulable; collaborators remain directory-only profiles.

## API surface

- `GET /api/v1/professionals`
- `GET /api/v1/professionals/{professional_id}`
- `POST /api/v1/professionals`
- `PUT /api/v1/professionals/{professional_id}`

## Frontend

The Nuxt layer provides `/professionals`, listed immediately after Budgets in
the backend-driven sidebar (`order: 45`). The list supports text/type filters,
inactive profiles and a create/edit modal.

## Boundaries

The module has no dependencies or event subscriptions. Agenda and Schedules
declare their dependency on this module before referencing its records.
