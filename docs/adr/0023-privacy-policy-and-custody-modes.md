# 0023 — Custody is a tenant property, declared in three modes

- **Status:** accepted (amended 2026-08-28, see *Amendment 1*)
- **Date:** 2026-08-28
- **Deciders:** Eduardo
- **Tags:** security, privacy, tenancy, compliance

## Context

Two questions keep getting answered implicitly, in scattered places.

**Who can read the data?** DentalPin's answer today is RBAC
(`backend/app/core/auth/permissions.py`), and RBAC answers a different
question. It governs what a *user of the application* may do. It says
nothing about whoever holds a database shell: an operator running the
deployment reads every clinic's clinical history without touching a
permission check. That is fine when the clinic runs the deployment
themselves and is exactly the risk a clinic evaluates before letting
anyone else host it. The distinction is not a setting we have — it is a
consequence of who runs the process and who holds the keys, and nothing
in the codebase says which of those is the case.

**Under which regime is it held?** That answer is currently hardcoded
field by field. `backend/app/core/agents/redaction.py` pinned its
government-ID key list to one country's document names; the Spanish
locale labelled a field "NIF/CIF" over a column holding an RFC;
`Patient.national_id_type` accepts `curp`/`ine`/`passport` while
`migration_import` writes `"nif"` into it. Every one of those is the same
defect: a jurisdiction decided at the point of use instead of read from
one place. The deployment already spans two regimes — `verifactu` files
with the Spanish AEAT while the default currency is MXN — so "just pick
one" is not available.

`TenantContext` (ADR 0012, Fase 1) already exists as the per-deployment
value object, and nothing consumes it yet. It is the cheapest moment this
will ever be to give it a custody field.

## Decision

**Custody is a property of the tenant, expressed as one of three modes,
declared in a `PrivacyPolicy` that core enforces and modules read.**

```python
class CustodyMode(StrEnum):
    SELF = "self"        # customer runs it; no operator of ours exists
    MANAGED = "managed"  # we run it, we hold the keys; break-glass only
    BYOK = "byok"        # we run it; the customer holds the keys
```

Four clarifications, each of which is the part that matters:

1. **The mode determines operator access and key custody; it does not
   coexist with them as separate flags.** `operator_access` and
   `key_custody` are derived properties, so a policy claiming "managed
   with no operator access" cannot be constructed. The three modes *are*
   the three supported combinations; a fourth combination is a new mode.

2. **`SELF` means absence, not restraint.** Operator access is `NONE`
   because there is no path, not because we promise not to use one. A
   `SELF` policy carrying break-glass terms is rejected at construction —
   describing bounds on an access route that does not exist would be a
   claim we cannot honour. This is also the mode's commercial point: we
   supply software, so there is no processing agreement to sign.

3. **Operator access, where it exists, is break-glass and never
   standing.** `BreakGlassPolicy` carries the terms — the session
   expires on its own, the operator states a reason, the customer is
   told. These are contract terms a clinic is asked to accept, so they
   live in the policy rather than in an internal runbook.

4. **Jurisdiction and regulation are separate sets.** `jurisdictions`
   (ISO 3166-1 alpha-2) drives *vocabulary*: which identity documents and
   tax identifiers exist. `regulations` drives *obligations*. They do not
   map one-to-one — a Spanish clinic answers to both GDPR and LOPDGDD
   over one jurisdiction — and conflating them is what makes a compliance
   model unable to absorb the next regime.

`egress_allowed` is default-deny: a destination absent from the set is
not permitted. Every module that sends data off-premises (`copilot` →
OpenAI, `whatsapp_kapso` → Kapso, `verifactu` → AEAT) is one of these
names.

**The policy is data, not behaviour.** It declares; enforcement lives in
the component being constrained. It is introduced ahead of its consumers
so the seam exists before the first non-self-hosted tenant does. The
deployment declares its own mode through `TENANT_CUSTODY_MODE` — see
*Amendment 1*, which replaced the hardcoded self-hosted policy this ADR
originally specified.

Retention windows, consent purposes and erasure semantics are
**deliberately absent**. They vary per regulation rather than per custody
mode, and their shape should be decided by the component that enforces
them, not guessed at now. Erasure semantics landed later in ADR 0026;
retention windows and consent are tracked as pending in
[`docs/technical/todos.md`](../technical/todos.md#retention-policies--pending--p1),
together with the LFPDPPP obligations that have no implementation at all
(consent for sensitive data, aviso de privacidad, the processing
contract that `managed` implies).

## Consequences

### Good

- The question a hosting customer actually asks — "can you read my
  patients' records?" — has a typed answer per tenant instead of a
  conversation.
- `BYOK` becomes expressible, which is the mode that lets us operate a
  deployment (backups, migrations, support) without being able to read
  the clinical fields. It needs envelope encryption to become real, but
  the vocabulary no longer blocks it.
- The jurisdiction defects above get one place to be fixed rather than
  one fix each. The copilot redactor is the first consumer: it builds
  its PII key map from `policy.jurisdictions` via
  `Redactor.for_policy()`, so a Spanish tenant tokenizes a NIE and a
  Mexican one tokenizes a CURP without either being hardcoded.
- Self-hosted stays the honest default: a tenant nobody configured is a
  tenant we cannot reach into.

### Bad / accepted trade-offs

- **Only `jurisdictions` is enforced.** The copilot redactor reads it;
  nothing reads the rest. Since Amendment 1 the default mode is
  `managed`, so an out-of-the-box deployment declares break-glass
  operator access that does not exist. A declared `egress_allowed` does not stop a
  module from calling out, and `MANAGED` does not yet imply a break-glass
  mechanism — there is no operator-access implementation at all. Those
  fields are a contract waiting for their enforcers, and until they land
  they describe a guarantee the code does not provide. The custody
  fields are therefore not something to put in front of a customer as a
  control.
- Deriving `operator_access` from the mode buys safety at the cost of
  flexibility: a combination we later need (managed hosting with no
  break-glass path) requires a new mode and an ADR amendment.
- `PrivacyPolicy` must stay hashable, because `TenantContext` is. That
  rules out mappings as fields — the retention table, when it arrives,
  cannot be a plain `dict`.

## Amendment 1 — the deployment declares its own mode (2026-08-28)

The ADR as accepted had `SingleTenantResolver` return a hardcoded
`self` policy, reasoning that a hardcoded value cannot be misconfigured
and that a managed deployment must not be able to declare itself
self-hosted.

That was wrong about which way this deployment actually points. DentalPin
is operated by us: `managed` is the truth for the normal case, and a
hardcoded `self` meant the system asserted that no operator could read
data an operator was in fact reading. A hardcoded lie is not safer than a
configurable truth.

**The mode is now read from `TENANT_CUSTODY_MODE`, defaulting to
`managed`.** Two settings come with it: `TENANT_JURISDICTIONS`
(default `MX,ES` — the deployment serves both markets) and
`TENANT_DATA_RESIDENCY`.

The original safety argument survives, inverted. The dangerous direction
is an operated deployment reporting `self`, so that now takes a
deliberate override, while the default over-states access: a self-hoster
who never sets the variable reports break-glass operator access nobody
has. Erring toward claiming *more* access is the right direction for a
privacy claim. An unrecognised mode is refused at startup rather than
defaulted — picking a custody claim on the operator's behalf is exactly
what this must not do.

`TENANT_DATA_RESIDENCY` resolves to `on-prem` under `self` (true by
definition) and to `unspecified` otherwise, with a warning. Reporting
`on-prem` for a deployment we host would be a lie; `unspecified` is a
gap, and a gap is an honest thing for a policy to contain. It is not
required, because requiring it for the *default* mode would stop every
existing deployment from booting.

### Implementation status of each mode

This is the part to read before showing any of this to a clinic.

| Mode | Status |
|---|---|
| `self` | **Real.** The only mode whose guarantee holds, because it is an absence rather than a control: there is no operator, so there is nothing to bypass. Commercially it is the *most expensive* option for the clinic — they carry infrastructure, backups and upgrades — and how it is offered is pending the business model. |
| `managed` | **Declared, not enforced.** The default. It names break-glass operator access — bounded, justified, expiring, disclosed — and **no such mechanism exists**; operator access today is standing. Deferred deliberately, and not only for want of time: see below. |
| `byok` | **Out of scope for this stage.** It needs envelope encryption and per-field key metadata, neither of which exists (`SECRET_KEY` derives one Fernet key and encrypted fields do not record which key encrypted them). The mode is kept as vocabulary so the model is complete and so building it later is wiring rather than redesign. |

#### Why break-glass is deferred, and what it is deferred with

Building break-glass in the application alone would be **theatre**. It
would bound access *through the app* while an operator keeps a standing
`psql` connection to the same database. Making `managed` true starts by
removing standing database access in production and routing support
through the application — infrastructure posture, not code. The code
piece comes after, and its job is then to record and bound whatever
access remains.

It is also deferred *together with* the clinical-record access log, in
that order: **infrastructure → access log → break-glass sessions**. An
emergency operator session with no access log records nothing, so
building the session mechanism first would produce a control with no
evidence behind it. The access log is the prerequisite, not the sequel.
Tracked in
[`docs/technical/todos.md`](../technical/todos.md#clinical-record-access-log--break-glass--deferred-as-one-piece).

Because two of the three modes claim more than the code delivers, the
resolver logs a warning at every boot naming the specific gap. A gap
printed on every boot is better than one discovered during an audit.

## Alternatives considered

- **Per-clinic settings in `Clinic.settings` JSONB** — wrong grain.
  Custody is a property of the deployment, not of a clinic inside it; a
  tenant with three clinics cannot have three different answers to who
  holds the keys. It would also be untyped and unvalidated.
- **Boolean flags (`is_self_hosted`, `can_operator_access`, …)** —
  permits incoherent combinations, and each new question adds a flag
  whose interaction with the others is undefined.
- **Putting it in `TenantContext.metadata`** — `metadata` is opaque to
  core by design (ADR 0012 §6). Anything core enforces has to be typed.
- **Encoding GDPR directly** — the codebase already serves two regimes
  and the primary market is a third. Hardcoding one regulation is how
  the current per-field mess happened; the point of `regulations` is to
  make the next regime a value rather than a refactor.

## How to verify the rule still holds

- `backend/tests/test_custody_settings.py` — the settings in Amendment 1:
  the `managed` default, the residency fallbacks, refusal of an unknown
  mode, and the boot warning each unenforced mode emits.
- `backend/tests/test_privacy_policy.py` — mode/access/custody mapping,
  the `SELF`-cannot-declare-break-glass rejection, jurisdiction
  validation, default-deny egress. `test_every_mode_is_covered` fails
  when a `CustodyMode` is added without deciding its access and custody.
- `backend/tests/test_tenancy_context.py`,
  `backend/tests/test_tenancy_resolver.py` — the policy rides on the
  tenant, participates in its identity, and defaults to self-hosted.
- A new field on `PrivacyPolicy` that is not hashable breaks
  `test_hashable_goes_in_set` in the tenancy tests.

## References

- `backend/app/core/privacy/policy.py`
- `backend/app/core/tenancy/context.py:44` — the `privacy` field
- `backend/app/core/tenancy/single.py` — self-hosted default
- [ADR 0012](0012-multi-tenancy-brief.md) — tenant vs clinic isolation
- `backend/app/core/agents/redaction.py` — `Redactor.for_policy()`, the
  first consumer
- `backend/app/core/tenancy/dependencies.py` — `get_tenant`, how a
  request reaches the policy
