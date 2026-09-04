# Changelog — odontogram module

## Unreleased
- fix: un tratamiento del catálogo sin dibujo en el odontograma ya se puede
  planificar. `clinical_type` se exigía siempre, y como se deducía del
  mapeo de odontograma, cualquier ítem sin mapeo daba 400 al intentar
  crearlo. Eso dejaba fuera **69 de los 136 tratamientos activos** del
  catálogo sembrado: una limpieza, una revisión, una panorámica, una
  prótesis removible o un ajuste oclusal no se podían añadir a un plan en
  absoluto. Un acto facturable que no dibuja nada en un diente no es un
  error, es la mitad de un catálogo dental real: ahora resuelve al tipo
  `procedure` y sigue su curso.

- feat(ui): el tratamiento elegido sigue armado después de aplicarlo. El
  trabajo dental viene en tandas — cuatro selladores, un cuadrante de
  raspado, composites en 16/26/36 — y soltarlo tras cada diente obligaba a
  buscar el mismo chip en una lista de ~30 cada vez. La chapa de la
  cabecera dice qué está armado y lo suelta; Esc también, y cada aplicación
  sigue ofreciendo deshacer.

- feat(ui): colocación por cuadrante. Con un tratamiento armado aparecen
  los cuadrantes disponibles; elegir uno pide confirmación nombrando las
  piezas antes de crear nada, porque ocho tratamientos creados por error no
  tienen deshacer en bloque. Solo para tratamientos de diente completo: los
  de superficie necesitan elegir caras pieza a pieza y los multi-diente son
  una única decisión clínica.


- feat(odontogram): the plan builder reaches every therapeutic category.
  `THERAPEUTIC_CATEGORIES` listed four of them, so the bar's planning mode
  silently dropped every mapped periodontal, preventive and paediatric
  treatment — 8 of the 61 items that carry a mapping. `diagnostico` stays out
  on purpose: it holds findings you record and never plan, and billable
  diagnostic *acts* are whole-mouth items that reach the bar through the
  globals tab.

  `TreatmentClinicalCategory` grew with it, on both sides. It listed five
  values while the database already held seven — `clinical_category` is a free
  string in the API, so the seed wrote catalog category keys straight through.
  Tab labels come from the catalog category of the same key, so no new i18n.

- feat(odontogram): process clinical types — `consultation`, `checkup`,
  `imaging`, `hygiene`. The visit itself, rather than work on a structure:
  billable, plannable, attached to no tooth. Without them a first visit had to
  map to `extraction` to satisfy the odontogram mapping. Same treatment as the
  skeletal block: absent from the per-tooth palette and the drawing rules,
  reached as `global_mouth` catalog items, with their own glyphs.

  `clinicalTypeParity.test.ts` now also pins the clinical-category union to the
  Python enum and checks that every therapeutic key is a real category.

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
