# Architecture Decision Records

Why we record decisions here:

- The repo grows; the *why* behind a constraint stops being obvious.
- AI agents and new contributors need durable, searchable context for
  rules they will otherwise question or accidentally undo.
- `git log` carries the *what*. ADRs carry the *why* + the *trade-offs
  considered* + the *consequences* if you break the rule.

## Convention

- Filename: `NNNN-kebab-title.md` — zero-padded sequence, never reused.
- One decision per file. Short. ≤1 page when possible.
- Every ADR uses the same structure: see `TEMPLATE.md`.
- Status: `proposed` → `accepted` → optionally `superseded by NNNN` /
  `deprecated`. Never delete an ADR; supersede it.
- Date: the date status changed (ISO `YYYY-MM-DD`).
- Cite source files (`path:line`) and tests so the rule is verifiable.

## ADR vs `features/` / `technical/`

- `docs/adr/` — historical decisions that shape today's code. Read to
  understand why a rule exists.
- `docs/features/` — forward-looking product / UX briefs. *What* and
  *why* of a feature being shaped.
- `docs/technical/` — implementation plans and cross-cutting tech
  reference. *How* a feature is being built.

A design brief or tech plan may graduate to an ADR once the decision
is locked in and worth defending against future drift.

## When to write a new ADR

Triggers (any one):

- A rule has been broken once and we want to make sure it isn't again.
- A reviewer asked "why is it this way?" and the answer isn't in code.
- We chose between two reasonable approaches and the loser will keep
  resurfacing.
- A constraint is imposed by an external system (regulator, vendor,
  licensor) and we need to capture it once.

## Index

| #    | Title | Status | Date |
|------|-------|--------|------|
| 0001 | [Modular plugin architecture](0001-modular-plugin-architecture.md) | accepted | 2026-04-27 |
| 0002 | [Per-module Alembic branches](0002-per-module-alembic-branches.md) | accepted | 2026-04-27 |
| 0003 | [Event bus over direct cross-module imports](0003-event-bus-over-direct-imports.md) | accepted | 2026-04-27 |
| 0004 | [BSL 1.1 license, Apache 2.0 after 4 years](0004-bsl-license.md) | accepted | 2026-04-27 |
| 0005 | [Relative permissions, registry-prefixed namespacing](0005-relative-permissions.md) | accepted | 2026-04-27 |
| 0006 | [Budget public link two-factor authentication](0006-budget-public-link-2-factor-auth.md) | accepted | 2026-04-28 |
| 0007 | [Polymorphic attachment owner registry in `media`](0007-polymorphic-attachment-registry.md) | accepted | 2026-05-02 |
| 0008 | [Photo storage retention is documented but not enforced (yet)](0008-photo-storage-retention-stub.md) | accepted | 2026-05-02 |
| 0009 | [Documentation portal: VitePress, filesystem-as-contract, in-app help](0009-documentation-portal.md) | accepted | 2026-05-02 |
| 0010 | [Payments as a primitive module; billing depends on payments](0010-payments-as-primitive-module.md) | accepted | 2026-05-13 |
| 0011 | [Detail-page shared components](0011-detail-page-shared-components.md) | accepted | 2026-05-13 |
| 0012 | [Multi-tenancy en DentalPin core — brief](0012-multi-tenancy-brief.md) | proposed | 2026-05-17 |
| 0013 | [Periodontogram snapshots are immutable dated rows, not an event stream](0013-periodontogram-snapshot-model.md) | accepted | 2026-05-26 |
| 0014 | [Copilot proactivity v1: deterministic morning digest email](0014-copilot-proactivity.md) | accepted | 2026-06-11 |
| 0015 | [Aggregate the copilot "Pendientes" feed through the tool registry](0015-copilot-pending-aggregation.md) | accepted | 2026-06-15 |
| 0016 | [Channel-adapter architecture for the notifications gateway](0016-channel-adapter-architecture.md) | accepted | 2026-06-26 |
| 0017 | [Inbound replies + conversation thread in communication_messages](0017-inbound-conversation.md) | accepted | 2026-06-26 |
| 0018 | [Install state is the authority on what runs](0018-install-state-is-the-mount-authority.md) | accepted | 2026-08-26 |
| 0019 | [Events are published after the transaction commits](0019-events-publish-after-commit.md) | accepted | 2026-08-26 |
| 0020 | [Handler failures are recorded, not just logged](0020-handler-failures-are-recorded.md) | accepted | 2026-08-26 |
| 0021 | [Module layers are typechecked, behind a shrinking baseline](0021-module-layers-are-typechecked.md) | accepted | 2026-08-26 |
| 0022 | [Touch adaptation is capability-driven, not width- or UA-driven](0022-touch-adaptation-is-capability-driven.md) | accepted | 2026-08-27 |
| 0023 | [Custody is a tenant property, declared in three modes](0023-privacy-policy-and-custody-modes.md) | accepted | 2026-08-28 |
| 0024 | [The control plane holds what constrains the customer](0024-control-plane-holds-what-constrains-the-customer.md) | accepted | 2026-08-28 |
| 0025 | [PII is classified on the column, and the classification is enforced](0025-pii-is-classified-on-the-column.md) | accepted | 2026-08-28 |
| 0026 | [Subject rights are a module contract, and erasure must be justified](0026-subject-rights-are-a-module-contract.md) | accepted | 2026-08-29 |
| 0027 | [Egress is declared in the manifest, and reported before it is blocked](0027-egress-is-declared-in-the-manifest.md) | accepted | 2026-08-29 |
