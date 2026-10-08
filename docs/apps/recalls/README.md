# Recordatorios (`recalls`)

- **Tier:** optional  ·  **Version:** 0.1
- **Declared in:** `backend/apps.json`  ·  **Composition and requirements:** [Apps catalog](../../apps-catalog.md)

## What it is for

Periodic check-ups: the recall list reception works through by phone, with contact attempts and outcomes.

## Modules

- [`recalls`](../../technical/recalls/overview.md) — code in `backend/app/modules/recalls/` ([notes](../../../backend/app/modules/recalls/CLAUDE.md))

## With this App off

The Recalls menu entry and page go; nothing else changes.

## Notes

- Requires Patients and Agenda. Professionals is optional: with it off a recall is created and worked with nobody assigned.
- It sends nothing itself. Sending over WhatsApp is pending and will go through Communications, as an integration.

## Decisions

- [0037](../../adr/0037-a-module-integrates-with-what-it-can-live-without.md)
