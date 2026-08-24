# Changelog — professionals module

## Unreleased

- feat(specialties)!: `specialty` is no longer free text. Replaced by a
  many-to-many link to the catalog's `specialties` table via
  `professional_specialties` (migration `pro_0002`, `depends_on = cat_0004`).
  The same discipline names were being typed into three places — this column,
  the treatment catalog, and a hardcoded list in the professionals page — so a
  stray accent split one discipline in two. Many-to-many because a dentist who
  does both endodontics and periodontics is ordinary. Existing values are
  preserved for clinical staff: each distinct (clinic, specialty) is matched
  against the catalog by name across locales, created when missing, then
  linked. Collaborator labels ("Laboratorio", "Proveedor") are roles, not
  disciplines, so they move to `notes` rather than polluting the catalog, and
  the UI hides the field for non-clinical types. `manifest.depends` gains
  `catalog`. Requests take `specialty_ids` (authoritative on update);
  responses carry an eager-loaded `specialties` list. Search by discipline
  matches through the link. A specialty from another clinic returns 400.

- feat: profile responses now include `has_system_access` — true when the
  profile's email matches a user with a membership in this clinic. Surfaced
  in the profile modal next to "Activo" as a read-only "Usuario con acceso"
  indicator; computed at response time, not stored.

- feat(scheduling): adds the `hygienist` profile type. Active dentists and
  hygienists are now the scheduling source of truth for Agenda and Schedules.

- Initial release of the clinic directory for dentists and collaborators.
- Adds profile fields for photo URL, specialty, professional-license number,
  contact information, notes and active status.
- Adds `professionals.read` and `professionals.write` permissions, REST
  endpoints and the `/professionals` sidebar screen.
- Adds the isolated `pro_0001` Alembic branch and `professionals` table.
