# Profesionales (`professionals`)

- **Tier:** optional  ·  **Version:** 0.1
- **Declared in:** `backend/apps.json`  ·  **Composition and requirements:** [Apps catalog](../../apps-catalog.md)

## What it is for

The directory of the clinic's professionals: who they are, their licence, specialties and signature.

## Modules

- [`professionals`](../../technical/professionals/overview.md) — code in `backend/app/modules/professionals/` ([notes](../../../backend/app/modules/professionals/CLAUDE.md))

## With this App off

The menu entry and the directory go. Agenda books with no professional, plans and recalls are assigned to nobody, a clinical entry names no professional.

## Notes

- Requires Patients (`media`, for photo and signature) and Treatments (`catalog`, for specialties).
- Meant to be a core App for workspaces of the Clinic kind; the catalog cannot yet say so.
- It offers the `ProfessionalDirectory` contract.

## Decisions

- [0039](../../adr/0039-modules-reach-each-other-through-core-contracts.md)
