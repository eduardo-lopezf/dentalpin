# Professionals module

Clinic-scoped directory for dentists and collaborators. A record stores
the general professional profile: name, profile photo URL, specialty,
professional-license number, contact details, notes and active status.

## Public API

Routes are mounted at `/api/v1/professionals`.

- `GET /` — paginated list; supports search, type and active filters.
- `GET /{id}` — profile detail.
- `POST /` — create a profile.
- `PUT /{id}` — edit a profile or deactivate it.

## Permissions

- `professionals.read` — view the directory and profile data.
- `professionals.write` — create and update profiles.

Admins manage profiles. Dentists, hygienists, assistants and receptionists
can view them by default.

## Data ownership and boundaries

- Owns the `professionals` table on its isolated `professionals` Alembic
  branch (`pro_0001`).
- Every row is scoped by `clinic_id`; all service queries must keep that
  filter.
- Profiles intentionally do not require a `users` account. This supports
  external collaborators and staff who have not been given product access.
- Deactivation is represented by `is_active`; retain history rather than
  deleting an operational profile.

## Events and tools

This module currently publishes and consumes no events and exposes no agent
tools. Future scheduling or treatment-assignment integrations should use a
declared dependency or events, never a hidden cross-module import.
