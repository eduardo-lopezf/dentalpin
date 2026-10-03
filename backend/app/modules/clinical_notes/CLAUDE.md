# Clinical notes module

Polymorphic clinical-notes store. Owns ``clinical_notes``. Document
attachments live in the ``media`` module since issue #55 — this module
registers its owner_types with ``media.attachment_registry`` and
delegates link/unlink/list operations to ``media.AttachmentService``.
Replaces the notes that previously lived inside ``treatment_plan``
(issue #60).

## Public API

Routes mounted at `/api/v1/clinical_notes/`.

- `GET    /notes?owner_type=…&owner_id=…`         — list for owner; `clinical_notes.notes.read`
- `POST   /notes`                                  — create; `clinical_notes.notes.write`
- `PATCH  /notes/{id}`                             — amend body; author or admin
- `GET    /notes/{id}/versions`                    — superseded bodies; `clinical_notes.notes.read`
- `DELETE /notes/{id}`                             — soft delete; author or admin
- `GET    /attachments?owner_type=…&owner_id=…`    — read-only proxy; new
  callers should use `/api/v1/media/attachments` directly
- `GET    /patients/{id}/recent`                   — Summary-tab feed (filterable)
- `GET    /patients/{id}/by-plan`                  — plan→treatment grouped feed
- `GET    /treatment-plans/{id}/merged`            — plan + treatment + visit notes for one plan
- `GET    /note-templates`                         — static template catalog

## Note matrix

| `note_type`                  | `owner_type`  | `owner_id` references                  | `tooth_number` |
|------------------------------|---------------|----------------------------------------|----------------|
| administrative               | patient       | patients.id                            | always NULL    |
| diagnosis                    | patient       | patients.id                            | optional       |
| treatment                    | treatment     | treatments.id (odontogram)             | always NULL    |
| treatment_plan               | plan          | treatment_plans.id (treatment_plan)    | always NULL    |
| appointment_clinical         | appointment   | appointments.id (agenda)               | always NULL    |
| appointment_administrative   | appointment   | appointments.id (agenda)               | always NULL    |

The `owner_id` has no DB-level FK (polymorphic); the service layer
verifies the owner exists in the same clinic before insert. A DB-level
CHECK enforces the matrix.

Treatment notes attach to the underlying ``treatments.id`` (not the
``planned_treatment_items.id``) so a note added at diagnosis time
travels with the treatment when it later becomes part of a plan.

## Dependencies

`manifest.depends = ["patients", "odontogram", "treatment_plan", "media"]`,
`manifest.integrates = ["professionals", "agenda"]`.

`agenda` is never imported: appointment owners and visit notes come from
`contracts.provider(AppointmentBook)` (ADR 0039). With that App off a note
cannot be added to an appointment and appointment/visit notes are not
listed; they stay stored.

`professionals` is never imported: attribution and visit-note authors come
from `contracts.provider(ProfessionalDirectory)` (ADR 0039). With that App
off a note is written with the account and no professional.

Backend reads cross-module models for two reasons:

1. **Owner validation.** Creating a ``treatment`` note must verify the
   referenced ``treatments`` row exists for this clinic; same for
   ``plan`` and ``patient`` owners.
2. **Aggregate feeds.** The Summary feed and the plan-grouped feed
   project plan/treatment metadata into the response so the UI can
   render contextual chips (``Diente 47``, ``Plan: PLAN-2024-0001``)
   without an extra round-trip.

UI integrations are slot-based. Host modules expose slot points and
`clinical_notes/frontend/plugins/slots.client.ts` registers components
into them. Hosts (``patients``, ``odontogram``, ``treatment_plan``)
never import this module.

## Permissions

`clinical_notes.notes.{read,write}`.

Roles get both by default — every clinical role and reception need to
read/write notes (administrative notes are reception-friendly).

## Events emitted

| Event | When |
|---|---|
| `clinical_notes.administrative_created` | administrative note created |
| `clinical_notes.diagnosis_created`      | diagnosis note created      |
| `clinical_notes.treatment_created`      | treatment note created      |
| `clinical_notes.plan_created`           | treatment_plan note created |
| `clinical_notes.appointment_clinical_created`       | clinical note on an appointment |
| `clinical_notes.appointment_administrative_created` | administrative note on an appointment |

Payload is uniform: ``{ clinic_id, patient_id, note_id, note_type,
owner_type, owner_id, tooth_number, user_id, body_excerpt, occurred_at }``.
``patient_timeline`` consumes them.

## Events consumed

None.

## Lifecycle

- `installable=True`, `auto_install=True`, `removable=False`. Notes
  are core clinical data — uninstalling would delete medical history.
- Migration ``cn_0001`` extends the existing tables created by
  ``treatment_plan.tp_0002`` (via ``depends_on``) instead of recreating
  them, so prod data is preserved across the ownership move.

## Gotchas

- **A note body is amended, never overwritten**
  ([ADR 0032](../../../../docs/adr/0032-clinical-record-is-append-only.md)).
  `NoteService.update` files the superseded text into `clinical_note_versions`
  and bumps `note.version`. Never assign `note.body` from anywhere else, and do
  not add an "edit without history" path: that is the defect this closed. A
  save whose text is unchanged writes no version on purpose — otherwise
  opening a note and pressing save manufactures history.

- **The current text stays on the note.** `clinical_notes.body` is the latest
  version and every consumer keeps reading it; the versions table holds only
  what was superseded. Reading a note must not cost a join.

- **Amending does not change `author_id`.** An admin correcting someone else's
  note does not become its author; the version row records who superseded the
  text. Clinical authorship by licensed professional is still missing — the two
  blockers are in `docs/features/expediente-clinico.md`.

- **Treatment notes survive plan churn.** They reference
  ``treatments.id`` directly, so removing a plan item, archiving the
  plan or moving the treatment to another plan all keep the notes
  attached.
- **No DB-level FK on owner_id.** Don't add one — it would require
  polymorphic-FK trickery and break uninstall safety. Trust the
  service-layer validators.
- **Spanish UI strings live in this module's i18n locale.** Add new
  strings under ``frontend/i18n/locales/{en,es}.json`` and key them
  with ``clinicalNotes.*``.
- **Slot points are stable contracts.** ``patient.summary.feed``,
  ``odontogram.diagnosis.sidebar``, ``odontogram.condition.actions``
  must stay populated even if you refactor — patient_timeline / agenda
  / patients UIs depend on them through the slot registry.

## Related ADRs

- `docs/adr/0032-clinical-record-is-append-only.md`

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0002-per-module-alembic-branches.md`
- `docs/adr/0003-event-bus-over-direct-imports.md`
- `docs/adr/0005-relative-permissions.md`

## CHANGELOG

See `./CHANGELOG.md`.
