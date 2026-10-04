---
module: patients_clinical
last_verified_commit: 0000000
---

# Patients Clinical

> _Scaffolded stub — replace with proper documentation when this module is next touched._

Landing page for the `patients_clinical` module in the end-user manual.

## Health questionnaire

**Patient record → Health questionnaire.** What the patient declares at a
visit: reason for the visit, blood group, allergies, twelve yes/no
questions (with their cause) and the checklist of conditions.

- **On screen:** *New questionnaire*. A question left unanswered stays
  unasked, not "no".
- **On paper:** *Print blank form* produces the sheet with the patient's
  data; it is filled in by hand, scanned and uploaded from *New
  questionnaire → On paper*. The reason for the visit is typed separately
  so it shows in the record.
- A saved questionnaire is not edited: the next visit fills in another.
  One saved by mistake is taken back with *Retract*, leaving a trace.
- It does not replace the medical history: the allergies, medication and
  diseases the clinic keeps current stay where they are.

## Screens

This module ships no Nuxt pages of its own.

## Permissions

- `patients_clinical.medical.read`
- `patients_clinical.medical.write`
- `patients_clinical.emergency.read`
- `patients_clinical.emergency.write`

## Technical references

- [Technical overview](../../../technical/patients_clinical/overview.md)
- [Permissions](../../../technical/patients_clinical/permissions.md)
- [Events](../../../technical/patients_clinical/events.md)
