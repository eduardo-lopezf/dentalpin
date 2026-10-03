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
- **`user_id` is the account this person signs in with, and it is stated, never
  inferred.** It is what lets a clinical entry name who is responsible for it
  ([ADR 0032](../../../../docs/adr/0032-clinical-record-is-append-only.md)):
  `ProfessionalService.for_user(db, clinic_id, user_id)` is the lookup the
  clinical modules call. Do not backfill it from `email` and do not let
  `has_system_access` stand in for it — that flag is an email comparison, and a
  coincidence cannot decide who authored a clinical record. The service refuses
  an account with no membership here (400) and one already linked to another
  profile in the same clinic (409).
- **Modules that FK to `professionals.id` from another Alembic branch must
  declare `depends_on = ("professionals",)`** — see `liq_0001`, `pc_0003`,
  `cn_0006`. Without it the constraint refers to a table an empty database has
  not built yet and boot fails; the label names `pro_0001`, the revision that
  creates the table, not the branch head.
- Deactivation is represented by `is_active`; retain history rather than
  deleting an operational profile.

## Events and tools

This module currently publishes and consumes no events and exposes no agent
tools. Future scheduling or treatment-assignment integrations should use a
declared dependency or events, never a hidden cross-module import.
