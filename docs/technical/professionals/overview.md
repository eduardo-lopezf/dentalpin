---
module: professionals
last_verified_commit: 0000000
---

# Professionals — technical overview

The professionals module owns the clinic-local directory of dentists and
collaborators. It is independent from authentication accounts, so external
specialists can have a profile without being able to sign in.

## Data

`professionals` is scoped by `clinic_id` and stores the person's name, type,
specialty, professional-license number, contact fields, profile photo URL,
notes and active status. Records are deactivated with `is_active` rather than
deleted.

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

The module has no cross-module dependencies or event subscriptions. Any
future connection with schedules, user accounts or treatment assignments must
be explicitly designed as an event contract or declared dependency.
