# Changelog — odontogram module

## Unreleased

- feat(odontogram): skeletal clinical types for orthognathic surgery.
  `TreatmentType` was closed and entirely tooth-bound, so a maxillofacial
  catalog item had no honest type to map to and had to borrow `extraction`.
  Adds `osteotomy_lefort1`, `osteotomy_sagittal_ramus`, `genioplasty`,
  `osteosynthesis` and `osteosynthesis_removal`, mirrored in the
  `ClinicalType` union and labelled in both locales, with glyphs so the
  bar does not render an empty icon.

  They are deliberately **not** in `TREATMENTS_BY_CATEGORY` nor in
  `TREATMENT_VISUALIZATION_RULES`: those drive the per-tooth palette —
  whose fallback hard-codes `treatment_scope: 'tooth'` — and the drawing on
  the chart, and a skeletal act is neither. They reach the UI as
  `global_mouth` / `global_arch` catalog items, in the "Boca completa" tab.

  No migration: `treatments.clinical_type` is `VARCHAR(30)` with no CHECK,
  and every new value fits. `frontend/tests/odontogram/clinicalTypeParity.test.ts`
  now pins the Python enum, the TypeScript union and the two label bundles
  together — they were hand-mirrored with nothing checking them.

- fix(odontogram i18n): `bridge` had no label in either bundle, so anywhere
  the clinical type is named on its own it rendered the raw key. Only the
  multi-tooth picker was unaffected, because it reads its own
  `odontogram.multiTooth.bridge.label` ("Puente fijo"). Named "Puente" /
  "Bridge", matching how the catalog already spells it ("Puente zirconio",
  "Puente Maryland"). Found by the parity test above, which now runs with
  no exemptions.

- feat(privacy): `get_subject_contributors()` — este módulo ya responde
  cuando un paciente ejerce portabilidad o supresión
  ([ADR 0026](../../../../docs/adr/0026-subject-rights-are-a-module-contract.md)).
  Tres secciones — estado dental, tratamientos aplicados e histórico del odontograma. Registro asistencial: se conservan.

- fix(ui): the change-history panel offers the rest instead of hiding
  it. The endpoint pages at 50 and reports the true count; the panel
  took `data` and dropped `total`, so the older half of a long clinical
  history was simply invisible. Now shows "showing N of M" with a
  load-more (audit S5).

- fix(ui): the treatment-edit modal keeps the user's edits when the save
  fails instead of closing over them, and deleting a treatment asks first
  — it may already be invoiced and there is no undo endpoint (audit S5).

- fix(events): publish through ``event_bus.publish_after_commit(db, ...)``
  instead of announcing from inside the caller's open transaction.
  Handlers read through their own sessions, so a flushed-but-uncommitted
  row was invisible to them (audit S2). See
  [ADR 0019](../../../../docs/adr/0019-events-publish-after-commit.md).

- fix(frontend): render an error state with retry when the odontogram
  fetch fails, instead of falling through to a fabricated all-healthy
  32-tooth chart (audit S5, #95). Adds `odontogram.messages.loadError`.

- feat(ux): ``DiagnosisMode`` now publishes a ``treatmentsToothById`` map
  and an ``onTeethHover`` callback through the
  ``odontogram.diagnosis.sidebar`` slot ctx, so the clinical-notes
  sidebar can pulse the matching tooth on the chart when the user
  hovers/focuses a note. Reuses the existing ``hoveredTeeth`` →
  ``highlightedTeethProp`` plumbing on ``OdontogramChart``.
- feat(treatments): add ``crown_on_implant`` and
  ``provisional_crown_on_implant`` clinical types. Both render on the
  lateral view as a solid prosthetic fill on the crown path (same code
  path as ``bridge``) — the diagonal-stripes pattern used by regular
  ``crown`` looked too sparse / artificial for implant-supported
  restorations. The two new types appear in ``TreatmentPicker`` under
  the Restauradora category, and count as ``hasReplacementTreatment``
  so the underlying ``missing`` / ``extraction`` state stops fading
  the tooth.
- fix(ToothDualView): when a tooth carrying ``missing`` /
  ``extraction_indicated`` / ``extraction`` state receives a
  prosthetic replacement (implant, bridge, crown, pontic,
  bridge_abutment, overlay, inlay, unerupted), render the tooth at
  full opacity — the restoration supersedes the extracted state.
  Also suppress the dashed/solid X overlays (occlusal + lateral) on
  those teeth, so the X no longer paints over the implant/crown.
  Previously, SVG-level opacity (and the wrapper ``.transparent``
  0.4 dim) faded both the natural anatomy and every overlay, so a
  newly placed implant on an extracted tooth rendered almost
  invisible. Opacity now applies only to natural-anatomy paths and
  only when no replacement is present.
- fix(DiagnosisMode): hide treatments whose
  ``source_module === 'migration_import'`` from the Diagnóstico panel.
  Migrated patients arrived with their entire chart history (often
  decades of crowns, fillings and extractions) flooding the active
  diagnosis workflow. The artefacts remain visible on the odontogram
  via ``ToothRecord.general_condition``, and the historical record
  stays in the History tab + the auto-generated treatment plans.
- refactor(types): drop the ``as unknown as Record<string, unknown>`` cast in ``useTreatments`` now that ``useApi`` accepts ``object`` payloads.
- Added per-module `CLAUDE.md` for AI-agent context (2026-04-27).
- Issue #60: `DiagnosisMode.vue` exposes a right-rail
  `odontogram.diagnosis.sidebar` slot (with mobile slideover) and
  `ConditionsList.vue` exposes a per-treatment
  `odontogram.condition.actions` slot. The clinical_notes module fills
  both — odontogram itself does not depend on it.

## 0.3.0 — initial documented version

- Per-tooth state with surface granularity, JSONB-backed.
- Tooth treatment workflow with `added` / `status_changed` /
  `performed` / `deleted` events.
- Drives budget + treatment_plan sync via `odontogram.treatment.performed`.
