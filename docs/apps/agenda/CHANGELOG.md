# Changelog — Agenda (`agenda`)

The App's own version, which moves independently of its modules' (ADR 0036). Each module keeps its own `CHANGELOG.md`.

## 0.1

- First App of the catalog: `agenda` + `schedules`.
- No required dependency: Patients, Professionals and Treatments became integrations; an appointment may have neither patient nor professional.
- Imports no other module; offers `AppointmentBook`.
- Google Calendar declared as a planned API.
