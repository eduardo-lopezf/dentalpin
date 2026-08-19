# Changelog — professionals module

## Unreleased

- feat(scheduling): adds the `hygienist` profile type. Active dentists and
  hygienists are now the scheduling source of truth for Agenda and Schedules.

- Initial release of the clinic directory for dentists and collaborators.
- Adds profile fields for photo URL, specialty, professional-license number,
  contact information, notes and active status.
- Adds `professionals.read` and `professionals.write` permissions, REST
  endpoints and the `/professionals` sidebar screen.
- Adds the isolated `pro_0001` Alembic branch and `professionals` table.
