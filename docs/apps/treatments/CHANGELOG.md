# Changelog — Tratamientos (`treatments`)

The App's own version, which moves independently of its modules' (ADR 0036). Each module keeps its own `CHANGELOG.md`.

## 0.1

- `treatment_plan` + `odontogram` + `periodontogram`; `catalog` joined, then `clinical_notes` on 2026-10-03.
- Decoupled from Budgets & payments, Professionals, Agenda and Media (ADR 0042): requires only the Patients App.
- 2026-10-03: a plan states its diagnosis and prognosis and they can be edited on it; clinical notes carry vital signs.
