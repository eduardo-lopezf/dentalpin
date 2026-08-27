# Changelog — patients_clinical module

## Unreleased

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
