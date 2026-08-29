# 0024 — The control plane holds what constrains the customer

- **Status:** accepted
- **Date:** 2026-08-28
- **Deciders:** Eduardo
- **Tags:** security, privacy, tenancy, database, compliance

## Context

ADR 0012 split isolation in two: a **tenant** is a database (physical
isolation, one connection string) and a **clinic** is a row scope
(`clinic_id` on every multi-tenant table). ADR 0023 then hung custody off
the tenant: `PrivacyPolicy.custody_mode` says whether an operator of the
deployment can reach the data at all.

That raises a question the two ADRs left unanswered: **where does each of
these facts physically live?** Today the answer is accidental rather than
decided.

- There is no `tenant_id` column anywhere in the schema. The tenant is
  the database; its identity exists only in the connection string.
- `custody_mode` is resolved at boot into an in-memory `TenantContext`
  and is never persisted.
- `clinics.account_tier` (renamed from `tenant_type` in migration `0009`
  precisely because the old name collided with ADR 0012's "tenant") sits
  in the tenant's own database and describes what that clinic contracted.

The last one is the tell. A commercial fact — what the customer paid for
— lives inside the database the customer controls. It is harmless today
because nothing gates on it, and it stops being harmless the moment
something does. The same shape would be far worse for `custody_mode`: a
claim about *who can read this database*, stored in that database, is a
claim its own subject can rewrite. An operator in `managed` mode could
set it to `self` and the system would assert it cannot read what it is
reading.

There is also a real gap in the other direction. Because no tenant
identity is stored anywhere in the data plane, **a restored backup does
not know whose it is.** A dump, an export, or a support artifact cannot
name its own tenant.

## Decision

**The data plane holds what the customer owns. The control plane holds
what constrains the customer.**

Concretely:

| Fact | Grain | Authoritative location |
|---|---|---|
| `tenant_id`, `slug`, `db_url` | deployment | control plane, `tenants` |
| `custody_mode` + the rest of `PrivacyPolicy` | deployment | control plane, `tenants` |
| `clinic_id` | row | data plane, `clinics.id` |
| `account_tier` | clinic | data plane, `clinics.account_tier` |

Four rules follow.

1. **The tenant→clinic relation is never a foreign key.** It crosses a
   database boundary and is materialized by the connection string. This
   is the isolation guarantee, not a missing constraint: with
   DB-per-tenant a mis-written `SELECT` cannot reach another tenant
   because there is no connection to reach it through. Reintroducing
   `tenant_id` as a column on every table would put isolation back into a
   `WHERE` clause somebody can forget.

2. **Nothing that constrains the customer is authoritative in the
   customer's own database.** `custody_mode` never moves down.
   `account_tier` may stay down only while it remains descriptive — the
   product *shape* of a clinic. If a tier ever decides what runs, that
   decision moves to the control plane first.

3. **`modules_enabled` is the enforcement axis, `account_tier` is
   not.** `modules_enabled` is per-tenant (ADR 0012 §6); `account_tier`
   is per-clinic, so a tenant with three clinics could otherwise carry
   three contradictory answers to one commercial question. A tier may
   act as a provisioning template that yields a module set; it is never
   consulted at runtime.

4. **Each tenant database carries a signed identity, as a mirror.** One
   single-row table:

   ```
   tenant_identity
     tenant_id         uuid          -- mirror of the control plane
     slug              text
     policy_assertion  bytea         -- (tenant_id, custody_mode, issued_at)
                                     -- signed by the control plane
     issued_at         timestamptz
   ```

   This closes the backup-identity gap without reopening rule 2: the
   assertion is verifiable by anyone and forgeable by nobody inside the
   tenant, so an operator who edits the row breaks the signature and the
   tampering is detectable. **It is a mirror, never the source of a
   runtime access decision** — those are taken from the `TenantContext`
   the control plane resolved. An unsigned copy of the same data would be
   exactly the self-certification this ADR rejects, wearing the face of
   authority.

**Break-glass sessions are recorded in both planes.** In the tenant
database so the clinic can audit operator access without asking us for
it, and in the control plane because an operator holding an open session
can delete the tenant-side copy. Neither record alone is sufficient.

**Self-hosted collapses the two planes, and that is correct.** In
`CustodyMode.SELF` there is no control plane: `SingleTenantResolver`
hardcodes the policy rather than reading it from settings, precisely so a
misconfigured managed deployment cannot declare itself self-hosted and
switch off the controls it needs. Tier and modules are whatever the
operator sets, because the operator *is* the customer. Self-certification
stops mattering when there is nobody to mislead.

## Consequences

### Good

- The question "can you read my patients' records?" has an answer stored
  where the answerer cannot edit it.
- Backups and exports become self-identifying, and their custody claim is
  verifiable offline.
- The `account_tier` trap is documented before something gates on it.
- The control-plane schema is now specified enough that the
  `dentalpin-saas` module can be built against it without renegotiating
  the boundary.

### Bad / accepted trade-offs

- **None of this exists yet.** There is no control plane, no `tenants`
  table, no `tenant_identity`, no signing key, and no break-glass
  mechanism. This ADR fixes the shape; it does not deliver a control.
- Signing introduces key management (a control-plane signing key, its
  rotation, and the verifier's trust anchor) before the first managed
  tenant. That cost is the price of a local copy that is worth having.
- Cross-tenant queries — fleet telemetry, aggregate reporting — have no
  join available by construction. They must be built as fan-out over
  tenants in the SaaS module, never as a query in core.
- Two records of every break-glass session can diverge. Divergence is
  itself the signal, but reconciling them needs tooling nobody has
  written.

## Alternatives considered

- **`tenant_id` as a column on every table (shared-schema)** — rejected
  by ADR 0012 and again here: it converts a physical guarantee into a
  predicate, and duplicates the role `clinic_id` already plays.
- **`custody_mode` in `clinics.settings` JSONB** — wrong grain (custody
  is per-deployment, not per-clinic), untyped, and squarely the
  self-certification failure above.
- **An unsigned `tenant_identity` mirror** — cheaper and solves the
  backup gap, but it would be read as authority within a release or two,
  and it is trivially editable by exactly the actor it describes.
- **No mirror at all** — the status quo. Keeps the data plane purely
  customer-owned, at the cost of backups and exports that cannot name
  themselves.

## How to verify the rule still holds

- `grep -rn "tenant_id" backend/app` returns nothing in model
  definitions. A `tenant_id` column on a domain table means rule 1 was
  broken.
- `grep -rn "account_tier" backend/app` shows reads for display only. A
  branch on `account_tier` that changes what runs means rule 3 was
  broken; the check belongs on `modules_enabled`.
- `backend/tests/test_privacy_policy.py` pins that a policy cannot be
  built claiming operator access under `SELF`.

## References

- [ADR 0012](0012-multi-tenancy-brief.md) — tenant vs clinic isolation
- [ADR 0023](0023-privacy-policy-and-custody-modes.md) — the custody modes
- `backend/alembic/versions/0009_clinic_account_tier.py` — the rename
- `backend/app/core/tenancy/single.py` — why `SELF` is hardcoded
- `backend/app/core/auth/models.py:57` — `account_tier`
