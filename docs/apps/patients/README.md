# Pacientes (`patients`)

- **Tier:** core  ·  **Version:** 0.1
- **Declared in:** `backend/apps.json`  ·  **Composition and requirements:** [Apps catalog](../../apps-catalog.md)

## What it is for

The patient record: identity and contact, medical history and alerts, the activity timeline, and documents and photos.

## Modules

- [`patients`](../../technical/patients/overview.md) — code in `backend/app/modules/patients/` ([notes](../../../backend/app/modules/patients/CLAUDE.md))
- [`patients_clinical`](../../technical/patients_clinical/overview.md) — code in `backend/app/modules/patients_clinical/` ([notes](../../../backend/app/modules/patients_clinical/CLAUDE.md))
- [`patient_timeline`](../../technical/patient_timeline/overview.md) — code in `backend/app/modules/patient_timeline/` ([notes](../../../backend/app/modules/patient_timeline/CLAUDE.md))
- [`media`](../../technical/media/overview.md) — code in `backend/app/modules/media/` ([notes](../../../backend/app/modules/media/CLAUDE.md))

## With this App off

The Patients menu entry and the record go. Other Apps offer no patient to pick.

## Notes

- Its backend imports nothing outside the App; the professional behind a history entry is asked of `ProfessionalDirectory`.
- The record hosts other Apps through slots (tabs, summary cards, header alerts) and never names them.
- Widgets: recent patients, medical history, medical alerts, quick actions.

## Decisions

- [0041](../../adr/0041-a-screen-hosts-other-apps-through-slots.md)
- [0039](../../adr/0039-modules-reach-each-other-through-core-contracts.md)
