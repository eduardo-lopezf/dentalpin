# Changelog — whatsapp_kapso module

## Unreleased

- feat(privacy): declara su egress en el manifest
  ([ADR 0027](../../../../docs/adr/0027-egress-is-declared-in-the-manifest.md)):
  `kapso` — api.kapso.ai y Meta por detrás. Salen el número del
  paciente y el contenido del mensaje.

- fix(privacy): classified this module's personal columns with `pii()`
  so the copilot's PHI boundary derives them from the schema instead of a
  hand-kept list ([ADR 0025](../../../../docs/adr/0025-pii-is-classified-on-the-column.md)).
  `display_phone_number` was not redacted before.

- fix(ui): "send test" is now single-shot (in-flight flag + `:loading`).
  Kapso bills per message, and the button had no guard at all (audit S5).

- feat: initial release. WhatsApp delivery for the notifications gateway via
  Kapso (Meta Cloud API). Community, installable/removable (issue #63).
- `KapsoAdapter` (template + free-form session sends) registered into the
  notifications channel registry at import time; unregistered on uninstall.
- Public signed `/webhook` (HMAC-SHA256 per clinic, resolved by
  `phone_number_id`): inbound → `record_inbound_reply`, status →
  `record_delivery_status`. Idempotent on the Kapso message id.
- Per-clinic credentials (`WhatsappKapsoSettings`) + template cache
  (`WhatsappKapsoTemplate`); secrets Fernet-encrypted. Alembic branch
  `wak_0001`.
- Template auto-sync from Kapso + type→template mapping written into
  `notification_templates` via the gateway's public seam.
- Frontend connect/settings layer (credentials, webhook URL, template sync +
  mapping, test send). i18n ES/EN.
