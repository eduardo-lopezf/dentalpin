# Changelog — notifications module

## Unreleased

- fix(security): `GET`/`PUT /preferences/patient/{patient_id}` accepted a
  patient from any clinic. Both funnel into
  `get_or_create_patient_preferences`, which created a
  `notification_preferences` row with the caller's `clinic_id` and the
  unvalidated `patient_id` — a column whose FK points at `patients.id` —
  so a **GET** planted a row in one clinic referencing another clinic's
  patient. No data was disclosed (the response is a fresh default
  record), but any authenticated user with `notifications.preferences.read`
  could seed cross-tenant rows at will. The ownership check now sits in
  the service, before the write, because all three call sites reach the
  write through it; both endpoints map the refusal to 404. Found by
  `tests/test_cross_tenant_isolation.py`
  ([ADR 0029](../../../../docs/adr/0029-security-invariants-with-chokepoints.md)).


- feat(privacy): declara su egress en el manifest
  ([ADR 0027](../../../../docs/adr/0027-egress-is-declared-in-the-manifest.md)):
  `smtp` — el servidor que configure cada clínica. Era el destino más
  fácil de pasar por alto: el receptor es configuración, no un proveedor
  nombrado en el código, y en cada recordatorio salen el correo y el
  nombre del paciente.

- feat(privacy): `get_subject_contributors()` — este módulo ya responde
  cuando un paciente ejerce portabilidad o supresión
  ([ADR 0026](../../../../docs/adr/0026-subject-rights-are-a-module-contract.md)).
  Mensajes enviados y preferencias de contacto. **Sí borra**. De paso se clasificó `to_address` (email o teléfono del destinatario) como `PiiKind.CONTACT`: no la veía el contrato de PII porque el nombre de la columna no lo delata.

- fix(privacy): classified this module's personal columns with `pii()`
  so the copilot's PHI boundary derives them from the schema instead of a
  hand-kept list ([ADR 0025](../../../../docs/adr/0025-pii-is-classified-on-the-column.md)).
  The clinic's own SMTP sending identity (`from_email`, `from_name`)
  is covered too.

- fix(ui): the conversation reply guards on `sending`. Enter bypassed the
  button's `:loading`, so two quick presses sent two WhatsApp messages —
  billed twice and read twice by the patient (audit S5).

- feat(conversation): inbound replies + bidirectional WhatsApp (Phase 2A,
  ADR 0017). ``communication_messages`` gains ``direction`` (outbound/inbound)
  and ``body_text``; it is now the full per-patient thread (Alembic
  ``notif_0003``). New gateway methods ``record_inbound_reply`` (idempotent,
  opens the 24h window via ``last_inbound_at``, publishes
  ``notification.reply_received``) and ``resolve_patient_by_phone``. The
  channel resolver allows free-form (``message_kind="session"``) WhatsApp only
  inside the 24h window. New conversation API (``GET /conversations/{patient_id}``,
  ``POST /conversations/{patient_id}/reply``) + ``ConversationThread`` card on
  the patient summary. New ``NotificationService.upsert_provider_template``
  public seam so vendor modules can register HSM template mappings.

- feat(multichannel): turn the email-only module into a channel-agnostic
  gateway. New ``channels/`` package (``ChannelAdapter`` protocol,
  ``OutboundMessage``/``AdapterResult``, idempotent ``channel_registry``,
  built-in ``EmailAdapter``). Vendor modules register adapters at import
  time. See ADR 0016.
- feat(outbox): ``gateway.NotificationGateway.enqueue`` persists a ``queued``
  row (no network in-request) and a ``dispatch_outbox`` scheduled job
  (every 45s) sends with ``FOR UPDATE SKIP LOCKED`` + exponential backoff.
  ``do_not_contact`` is now a hard block on every channel.
- refactor(models): ``email_logs`` → ``communication_messages`` (outbox +
  audit in one table, ``channel``/``attempts``/``next_attempt_at``/
  ``dedup_key``/delivery timestamps); ``email_templates`` →
  ``notification_templates`` (``channel`` + ``provider_template_name`` for
  WhatsApp HSM); per-channel WhatsApp opt-in on ``notification_preferences``;
  new generic ``clinic_channel_settings``. Alembic ``notif_0002`` (data
  preserved, ``channel`` backfilled to ``email``).
- refactor(send-path): handlers, the reminder cron, and the manual-send
  route now ``enqueue`` instead of sending synchronously; the reminder
  dedup moved from a ``context_data["appointment_id"]`` scan to a
  ``dedup_key`` unique index. Removed the dead ``send_notification``/
  ``create_log`` service methods.
- feat(events): ``notification.queued/sent/failed/delivered/reply_received``.
  ``EMAIL_SENT/FAILED`` are dual-published for ``channel=email`` for one
  release so ``patient_timeline`` keeps working unchanged.
- feat(agents): ``tools.py`` exposes ``send_notification`` (WRITE) wrapping
  the gateway; respects consent, never bypasses ``do_not_contact``.
- refactor(scheduler): declare the ``appointment_reminders`` interval job
  via ``get_scheduled_jobs()`` instead of being imported by name in
  ``app/core/scheduler.py``.
- refactor(types): drop the ``as unknown as Record<string, unknown>`` cast pattern (4 sites) in ``useNotificationSettings`` now that ``useApi`` accepts ``object`` payloads.
- fix(isolation): declare ``catalog`` in ``manifest.depends`` — the
  email-template handlers and the preview endpoint already imported
  catalog models to render line items. The dependency was real,
  just undeclared. ``KNOWN_VIOLATIONS`` allowlist trimmed
  accordingly.
- chore(events): subscribe via ``EventType.X`` constants instead of
  string literals — the events were already registered in the enum,
  the handler dict was the last drift site.
- Added per-module `CLAUDE.md` for AI-agent context (2026-04-27).

## 0.1.0 — initial

- Email templates, per-patient preferences, SMTP/console providers.
- APScheduler-backed sending queue (`tasks.py`).
- Subscribes to 6 events across patients, agenda, budget, billing.
