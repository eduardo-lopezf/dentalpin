# Comunicaciones (`communications`)

- **Tier:** optional  ·  **Version:** 0.1
- **Declared in:** `backend/apps.json`  ·  **Composition and requirements:** [Apps catalog](../../apps-catalog.md)

## What it is for

Messages to patients: today, email notifications for appointments, budgets and invoices.

## Modules

- [`notifications`](../../technical/notifications/overview.md) — code in `backend/app/modules/notifications/` ([notes](../../../backend/app/modules/notifications/CLAUDE.md))
- [`whatsapp_kapso`](../../technical/whatsapp_kapso/overview.md) — code in `backend/app/modules/whatsapp_kapso/` ([notes](../../../backend/app/modules/whatsapp_kapso/CLAUDE.md))

## With this App off

Not verified. Nothing is sent.

## Notes

- Requires Patients, Agenda, Budgets & payments, Treatments and Professionals — more than it should; decoupling is pending.
- API declared: WhatsApp (planned), through the `whatsapp_kapso` module, not installed by default.

## Decisions

- [0040](../../adr/0040-widgets-are-read-from-the-registry-apis-are-declared-in-apps-json.md)
