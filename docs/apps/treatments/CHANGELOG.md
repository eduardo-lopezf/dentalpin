# Changelog — Tratamientos (`treatments`)

The App's own version, which moves independently of its modules' (ADR 0036). Each module keeps its own `CHANGELOG.md`.

## 0.1

- `treatment_plan` + `odontogram` + `periodontogram`; `catalog` joined, then `clinical_notes` on 2026-10-03.
- Decoupled from Budgets & payments, Professionals, Agenda and Media (ADR 0042): requires only the Patients App.
- 2026-10-03: a plan states its diagnosis and prognosis and they can be edited on it; clinical notes carry vital signs.
- 2026-10-04: specialties are reference packs — 17 disciplines, 260 treatments, 20 plan templates — enabled, disabled and restored from the App's own settings page (ADR 0047).
- 2026-10-04: the reference catalogue is one JSON file per discipline, organised in sub-areas; the settings page lists each discipline's treatments by sub-area (ADR 0048).
- 2026-10-04: every discipline's reference catalogue taken to its full range — 706 treatments, up from 260.
- 2026-10-04: plan templates for every discipline — 125, up from 20.
