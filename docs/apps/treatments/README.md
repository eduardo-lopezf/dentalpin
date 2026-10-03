# Tratamientos (`treatments`)

- **Tier:** core  ·  **Version:** 0.1
- **Declared in:** `backend/apps.json`  ·  **Composition and requirements:** [Apps catalog](../../apps-catalog.md)

## What it is for

The treatment catalog, the odontogram and periodontogram, treatment plans and the clinical notes written on them.

## Modules

- [`catalog`](../../technical/catalog/overview.md) — code in `backend/app/modules/catalog/` ([notes](../../../backend/app/modules/catalog/CLAUDE.md))
- [`treatment_plan`](../../technical/treatment_plan/overview.md) — code in `backend/app/modules/treatment_plan/` ([notes](../../../backend/app/modules/treatment_plan/CLAUDE.md))
- [`odontogram`](../../technical/odontogram/overview.md) — code in `backend/app/modules/odontogram/` ([notes](../../../backend/app/modules/odontogram/CLAUDE.md))
- [`periodontogram`](../../technical/periodontogram/overview.md) — code in `backend/app/modules/periodontogram/` ([notes](../../../backend/app/modules/periodontogram/CLAUDE.md))
- [`clinical_notes`](../../technical/clinical_notes/overview.md) — code in `backend/app/modules/clinical_notes/` ([notes](../../../backend/app/modules/clinical_notes/CLAUDE.md))

## With this App off

The Treatments menu entry, the Clínico tab of the patient record and the catalog settings go. Agenda books without treatments. Invoices have no VAT type to pick and a professional no specialty to choose, because both live in `catalog`.

## Notes

- Requires only the Patients App. Budgets & payments, Professionals, Agenda are integrations: with Budgets off a confirmed plan goes straight to *in treatment*; with Professionals off nobody is assigned and no prescription is issued.
- A plan never writes a budget: it announces what happened to it and Budgets & payments reacts.

## Decisions

- [0042](../../adr/0042-core-apps-must-stay-separable.md)
- [0039](../../adr/0039-modules-reach-each-other-through-core-contracts.md)
