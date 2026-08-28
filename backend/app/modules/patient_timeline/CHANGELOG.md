# Changelog — patient_timeline module

## Unreleased

- feat(privacy): `get_subject_contributors()` — este módulo ya responde
  cuando un paciente ejerce portabilidad o supresión
  ([ADR 0026](../../../../docs/adr/0026-subject-rights-are-a-module-contract.md)).
  Índice derivado de eventos. **Sí borra**, incluida la descripción ya renderizada.

- fix(ui): infinite scroll actually scrolls. The `IntersectionObserver`
  was created in `onMounted` from a ref that lives in the `v-else`
  branch — absent on first paint, since the loading branch renders
  instead — so it observed nothing and the timeline stopped at the
  first page of 20 with no hint there was more. Now attached by
  watching the ref, which also survives a filter change (audit S5).

- feat(agents): expose `tools.py` — `get_patient_timeline` (READ)
  wrapping `TimelineService.get_timeline`. Returns structured event
  metadata only (type/category/title/timestamp); free-text description +
  event_data omitted so no un-redactable prose reaches the cloud LLM.
  Issue #81 P0 batch.

- perf(list): drop the ``select_from(query.subquery())`` count
  anti-pattern in ``TimelineService.get_timeline``; count now runs
  directly over the indexed ``(clinic_id, patient_id)`` filter.
- fix(isolation): ``PatientTimeline.patient`` no longer uses
  ``back_populates="timeline_entries"`` — that attribute was removed
  from the foundational ``patients`` module so it would stop pointing
  at this consumer. Relationship stays one-directional.
- Added per-module `CLAUDE.md` for AI-agent context (2026-04-27).

### Added (plan/budget workflow rework, 2026-04-29)

- Subscribed to 8 new cross-module events with snapshot payloads:
  `treatment_plan.{confirmed,closed,reactivated}` and
  `budget.{rejected,expired,renegotiated,viewed,reminder_sent}`. All
  rendered as Spanish-titled timeline entries; no upstream ORM imports.

## 0.1.0 — initial

- Unified activity log per patient.
- Subscribes to 22 events across the system.
- Append-only model with archive instead of delete.
