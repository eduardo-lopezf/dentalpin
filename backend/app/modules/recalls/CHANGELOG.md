# Changelog — recalls module

## Unreleased

- feat(privacy): `get_subject_contributors()` — este módulo ya responde
  cuando un paciente ejerce portabilidad o supresión
  ([ADR 0026](../../../../docs/adr/0026-subject-rights-are-a-module-contract.md)).
  Recordatorios e intentos de contacto. **Sí borra**, incluidas las notas libres.

- fix(ui): the call list has a pager. It tracked `page`/`total` and sent
  them to the API, but nothing changed the page and no control was
  rendered — a clinic with more than 50 recalls in the month saw the
  first 50 and nothing said otherwise (audit S5).

- fix(ui): cancelling a recall asks for confirmation; it drops the patient
  off the call list for good. `markDone` stays one click on purpose — it is
  the primary action of the screen and is recoverable (audit S5).

- fix(events): publish through ``event_bus.publish_after_commit(db, ...)``
  instead of announcing from inside the caller's open transaction.
  Handlers read through their own sessions, so a flushed-but-uncommitted
  row was invisible to them (audit S2). See
  [ADR 0019](../../../../docs/adr/0019-events-publish-after-commit.md).

- fix(professionals): `assigned_professional_id` on `recalls` now points
  at `professionals.id` (directory) instead of `users.id`, matching the
  `agenda`/`schedules`/`treatment_plan`/`budget` directory-professional
  rewire (`ag_0006`/`sch_0002`/`tp_0007`/`bud_0004`). Assigning a
  professional to a recall was failing with a 500
  (`ForeignKeyViolationError`) because the frontend already sends a
  directory professional id. Migration `rec_0002` backfills existing
  rows via the same deterministic account→profile mapping. Adds
  `professionals` to `manifest.depends`. `create`/`update` now validate
  the assigned professional against the directory (active
  dentist/hygienist in-clinic) — previously unchecked. `recommended_by`
  is untouched — it still FKs to `users.id` (who suggested the recall,
  not who it's clinically attributed to). `PATCH /{recall_id}` now
  catches `ValueError` from the service (404, matching `POST /`'s
  existing convention) instead of letting it fall through as a 500 —
  the new validation was the first thing that could raise from
  `update()`.

- fix(security): reject `create` when `patient_id` belongs to another
  clinic (audit multi-tenancy #1, #95). Previously the recall was
  inserted with the caller's `clinic_id` but no check that the patient
  was theirs, and the list/export join had no `Patient.clinic_id`
  predicate — so a caller could point a recall at a foreign patient and
  read that patient's name/phone back. `create` now 404s on a foreign
  patient (HTTP and copilot tool paths), and the list join is scoped to
  `Patient.clinic_id` as defense in depth.

- feat(agents): expose `tools.py` for the copilot agentic layer —
  `list_due_recalls`, `get_recall` (READ; the latter `exposes_free_text`),
  `create_recall`, `log_contact_attempt`, `snooze_recall`,
  `complete_recall` (WRITE). Thin wrappers over `RecallService`;
  clinic-scoped; RBAC via existing `recalls.read`/`recalls.write`.

- refactor(perms): migrate the hardcoded ``can('recalls.read')`` route guard on ``/recalls`` to ``PERMISSIONS.recalls.read`` (new entry in the host permissions config; also covers ``recalls.write`` / ``recalls.delete``).
- perf(list): rewrite ``RecallService.list`` to count via a direct
  ``COUNT(Recall.id)`` over the joined ``recalls × patients`` filter
  set instead of materialising the data query as a subquery. Pairs
  with the new ``patients`` indices on ``status`` /
  ``do_not_contact`` to keep the monthly call-list page sub-second.
- docs(user-manual): reescribir pantallas con guía operativa (ES + EN).
- Initial release. Patient call-back workflow (issue #62).
- Tables: `recalls`, `recall_contact_attempts`, `recall_settings`
  on the `recalls` Alembic branch (`rec_0001`).
- Endpoints under `/api/v1/recalls/*` — list, create (duplicate
  guard), detail, snooze, cancel, mark-done, log-attempt, link
  appointment, settings, dashboard stats, suggestions/next, CSV
  export.
- Events published: `recall.created`, `recall.completed`,
  `recall.snoozed`, `recall.cancelled`. `recall.due` enum value
  reserved for a future cron — not published in V1.
- Events consumed: `appointment.scheduled` (auto-link),
  `appointment.completed` (auto-close), `appointment.cancelled`
  (revert), `treatment_plan.treatment_completed` (suggestion hook,
  stateless), `patient.archived` (move active → needs_review).
- Frontend layer registers slot entries in:
  - `patient.summary.actions` — "Set recall" button
  - `patient.summary.feed` — recall pill + recent history
  - `odontogram.condition.actions` — per-treatment "Set recall"
  - `appointment.completed.followup` — "Schedule recall?" prompt
  - `dashboard.attention` — due/overdue/conversion widget
  - `settings.sections` — reason-interval + category-map editor
- Permissions: `recalls.{read,write,delete}`. Receptionist + dentist
  + hygienist + assistant get read+write; admin gets `*`.
- Auto-link policy on `appointment.scheduled` is **conservative**:
  fires only when the patient has exactly one matching active recall.
  Two-plus candidates → no-op, reception links manually from the
  call-list row. Avoids silent wrong-association across multiple
  reasons (no reliable signal in agenda's free-text `treatment_type`).
- `installable=True`, `auto_install=True`, `removable=True`.
  Round-trip uninstall test verifies all three tables drop cleanly.
- Sidebar entry registered via `manifest.frontend.navigation`
  (`/recalls`, icon `i-lucide-bell`, gated by `recalls.read`,
  `order: 25` — between `Agenda` and `Planes de tratamiento`).
  Host i18n adds `nav.recalls` for ES/EN.
