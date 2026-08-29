# Changelog — patients_clinical module

## Unreleased

- feat(privacy): `get_subject_contributors()` — this module now answers
  for its own data when a patient exercises portability or erasure
  ([ADR 0026](../../../../docs/adr/0026-subject-rights-are-a-module-contract.md)).
  Two sections: `clinical_history` and `contacts`. The contacts one is
  the only place a **third party's** data (emergency contact, legal
  guardian) hangs off a patient record, and it is erased with them.

- fix(privacy): classified this module's personal columns with `pii()`
  so the copilot's PHI boundary derives them from the schema instead of a
  hand-kept list ([ADR 0025](../../../../docs/adr/0025-pii-is-classified-on-the-column.md)).

- fix(i18n): the legal-guardian ID field was labelled "DNI/NIE" in
  Spanish, a document this deployment's patient records cannot even
  represent (`national_id_type` accepts `curp`/`ine`/`passport`). Label
  is now "Identificación" with the three accepted documents as the
  placeholder. English was already neutral and is untouched.

- fix(events): publish through ``event_bus.publish_after_commit(db, ...)``
  instead of announcing from inside the caller's open transaction.
  Handlers read through their own sessions, so a flushed-but-uncommitted
  row was invisible to them (audit S2). See
  [ADR 0019](../../../../docs/adr/0019-events-publish-after-commit.md).

- refactor(types): drop the ``as unknown as Record<string, unknown>`` cast in ``useMedicalHistory`` now that ``useApi`` accepts ``object`` payloads.
- Added per-module `CLAUDE.md` for AI-agent context (2026-04-27).

## 0.1.0 — initial

- Normalized medical history, allergies, medications, emergency contacts.
- `patient.medical_updated` event for the timeline.
- Role-scoped permissions: hygienists read-only on medical, write on emergency.
