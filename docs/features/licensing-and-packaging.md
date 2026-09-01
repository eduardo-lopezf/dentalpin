# Licensing and packaging — tiers, delivery models, licence lifecycle

> Status: draft. Spec last updated: 2026-08-31.
> Decision behind it: [ADR 0028](../adr/0028-self-hosting-is-the-premium-tier.md).
>
> **Everything commercial in this document is marked `TBD` and is not
> decided.** Prices, currencies, billing periods, seat limits,
> evaluation caps, trial lengths and every duration in the lifecycle are
> open, as is the whole of §4. What is
> decided is the *shape*: which axes exist, what a licence may gate, and
> what it may never gate. Do not quote a number from this file to a
> customer — there are none, on purpose.

## Why

[ADR 0028](../adr/0028-self-hosting-is-the-premium-tier.md) settled one
question: self-hosting is the premium tier, sold, and activated by a
signed licence key. It deliberately said nothing about what a customer
actually sees — how many packages exist, what each contains, what the
key costs, how long it lasts, or what happens the morning after it
expires.

That gap is worth writing down before it gets filled by accident. The
recurring failure in this area is not mispricing; it is letting a
commercial question collapse into an engineering one, so that a package
becomes whatever a flag happens to gate. Two habits prevent it:

1. **The axes stay separate.** Product shape and delivery model are two
   independent choices, not one ladder.
2. **The compliance floor is never a package feature.** Some things a
   clinic gets because the law says so, not because it paid.

## 1. Two axes, never one ladder

`ACCOUNT_TIERS` (`backend/app/core/auth/models.py:24`) and
`CustodyMode` (`backend/app/core/privacy/policy.py`) answer different
questions, live at different grains, and are stored in different places.
Collapsing them into a single "plan" column is the mistake this section
exists to prevent.

| | **Product shape** (`account_tier`) | **Delivery** (`CustodyMode`) |
|---|---|---|
| Answers | what the software does for this clinic | who runs it and who holds the keys |
| Grain | per clinic | per deployment (tenant) |
| Stored in | data plane, `clinics.account_tier` | control plane / the licence key |
| Values | `basic`, `medium`, `advanced`, `clinic`, `clinic_pro`, `hospital` | `self`, `managed`, `byok` |
| Runtime role | **none** — display only ([ADR 0024](../adr/0024-control-plane-holds-what-constrains-the-customer.md) rule 3) | resolves into `TenantContext.modules_enabled` |

A commercial offer is therefore a **cell**, not a row: *(product shape)
× (delivery)*. The price of a cell is `TBD`.

### The matrix

Rows are the reserved tiers; only `clinic` has real functionality today.
`medium` and `advanced` are deliberately undefined — see §7.

| | `self` (premium) | `managed` | `byok` |
|---|---|---|---|
| **`basic`** | **not offered** | TBD | **not offered** |
| **`medium`** | **not offered** | TBD (tier undefined) | **not offered** |
| **`advanced`** | TBD (tier undefined) | TBD (tier undefined) | TBD (tier undefined) |
| **`clinic`** | TBD | TBD | TBD |
| **`clinic_pro`** | TBD | TBD | TBD |
| **`hospital`** | TBD | TBD | TBD |

Three shape decisions inside the matrix that are *not* TBD:

- **The entry tiers are sold hosted, and only hosted.** `basic` and
  `medium` are always `managed`. They exist to be cheap, and `self` is
  the opposite of cheap for the clinic — it carries infrastructure,
  backups, upgrades and the licence — so offering them there would sell
  the most demanding delivery model to the customers least equipped to
  run it. **This rule is implemented**: see §6.
- **`byok` requires a dedicated tenant database.** Customer-held keys
  over a shared deployment would be theatre. It is also out of scope
  until envelope encryption exists ([ADR 0023](../adr/0023-privacy-policy-and-custody-modes.md)
  status table), so every `byok` cell is unsellable today regardless of
  price.
- **`byok` is priced per deployment, not per seat.** Its cost to us is
  key management and operational risk, both of which are per-deployment.
  A per-user price would model nothing real.

## 2. What may be charged for, and what may not

The distinction is between *obligation* and *service*. A clinic is the
*responsable* of its patients' data; we are at most an *encargado*.
Obligations of either party are not features.

**Never gated by a package or a licence state:**

- clinical reads, writes, backups and export — see *The export
  guarantee* below
- subject rights — access and erasure ([ADR 0026](../adr/0026-subject-rights-are-a-module-contract.md),
  `/api/v1/privacy/*`)
- PII redaction on the copilot path ([ADR 0025](../adr/0025-pii-is-classified-on-the-column.md))
- the subprocessor register and egress declarations ([ADR 0027](../adr/0027-egress-is-declared-in-the-manifest.md))
- RBAC, the aviso de privacidad, breach notification, the DPA
- the clinical-record access log, once it exists

### The export guarantee

**A clinic can always take its own data out, as CSV.** Under every tier,
in every licence state, with every trial and every temporary-upgrade
token expired, and in the evaluation state. It is not a feature of any
package and it is never a reason to renew anything.

The reasoning is the same one that shapes ADR 0028 rule 3 and §4's first
constraint, said in the form a customer can check: a promise that data
"stays accessible" is not verifiable, while *"you can download a CSV of
it right now"* is. It is also the thing a clinic asks about before it
signs — what happens if we leave — and the answer should not depend on
what they are paying at the time.

Three things this commits us to, stated so they can be held against us:

- **Scope is the clinic's own data**, not one patient's. This is
  distinct from the per-patient portability response of
  [ADR 0026](../adr/0026-subject-rights-are-a-module-contract.md), which
  answers a *patient's* request and is also never gated. Both exist; they
  answer different people.
- **Format is CSV**, and CSV specifically because it opens in whatever
  the clinic already has, with no reader of ours in the path. Offering it
  only in a format that needs our software would be a lock-in wearing an
  export's face.
- **Availability is unconditional.** No token, no tier, no valid licence
  is required to run it.

**Not implemented — this is a promise, not a description.** Today the
only export that ships is the per-patient subject-rights one, and it
returns **JSON** (`GET /api/v1/privacy/subjects/{id}/export`). The only
CSV in the codebase belongs to `accounting_export`, which covers invoices
and payments and is an **optional module** — so as things stand a tier
that did not include that module would remove the one CSV export there
is, which is exactly what this guarantee forbids. Whatever is built has
to sit outside the module set a tier controls, for the same reason the
rest of §2 does. Tracked, with the design tension it runs into, in
[`../technical/todos.md`](../technical/todos.md#clinic-wide-csv-export--pending--p1).

**Fair to charge for** — these cost us money or carry real operational
risk:

- the `self` licence itself, and the updates/regulatory currency behind
  it (Veri\*Factu against AEAT is the concrete recurring value)
- a dedicated tenant database; choice of data residency
- `byok` key management
- extended retention of logs and backups
- SSO/SAML, support tiers and response times, onboarding and data
  migration
- a negotiated DPA with non-standard terms

## 3. Licence lifecycle

Four states. **Every duration below is `TBD`** — grace windows,
evaluation caps and renewal lead times are open questions, and the
numbers should come from talking to the first three customers, not from
this file.

| State | How it is reached | What the clinic can do | What stops |
|---|---|---|---|
| **Evaluation** | no licence present | everything, against a cap (`TBD`: patients? clinics? days? all three?) | nothing is blocked; a persistent, non-dismissable label states the deployment is not licensed for production |
| **Active** | valid signature, not expired | everything in the purchased cell | — |
| **Expiring** | active, inside the renewal window (`TBD`) | everything | nothing; escalating notice to admins only, never to clinical staff mid-consultation |
| **Expired** | past `expires_at`, past grace (`TBD`) | **all clinical work continues** — reads, writes, backups, subject rights, and the CSV export of §2 | updates, module installation, support, and cloud-backed features whose cost is ours |

The **Expired** row is the load-bearing one and it is not TBD: it is
rule 3 of ADR 0028. A licence never takes a clinic's records away from
it. The pressure to renew comes from what stops arriving (regulatory
updates, support), not from what stops working.

Verification is **offline** — no phone-home, in any state. A call home
would put an outbound channel into the one mode sold on the absence of
one, and would break an air-gapped deployment.

## 4. Trials and temporary upgrades — pending

Two mechanisms with one shape. **Everything here is pending**; what
follows is the shape and the constraints, not a specification.

**A trial period per tier.** Every `account_tier` gets one. The duration
is `TBD`, and it is a *per-tier* number rather than one global figure —
the evaluation a `basic` clinic needs to make up its mind is not the one
a `hospital` needs.

**Temporary access to a higher tier.** A clinic on one tier may use
features from the tier above it for a bounded time without changing
tier. The tier itself does not move; what moves is what the clinic may
reach, and only until the clock runs out.

**Both are activated by a token, and the token is not the licence key.**
They are different artifacts answering different questions, and the
security model keeps them apart:

| | Licence key ([ADR 0028](../adr/0028-self-hosting-is-the-premium-tier.md)) | Entitlement token (pending) |
|---|---|---|
| Answers | is this deployment licensed for production | may this clinic use *X* until *when* |
| Grain | deployment | clinic (`TBD`) |
| Lifetime | the licence term | short, bounded, self-expiring |
| Issued | once, at purchase | on request, repeatedly |
| Verification | offline, no phone-home | `TBD` |

### What the security model has to state

Pending, and the part to specify before anything is built. Handling these
tokens as a variation on the licence key would be a mistake: the licence
key is issued once and read at boot, while these are issued often, redeemed
by a user, and expire on their own.

- What issues and signs them, and whether a token is single-use.
- Whether they verify offline like the licence key, or need the control
  plane. Offline is the harder problem here — a self-expiring grant with
  no issuer to ask is exactly where replay and clock skew bite.
- Replay, and reuse of one token across deployments.
- Who may redeem one: an admin, or an RBAC permission of its own.
- Revocation before expiry, and what a revoked-but-unexpired token does.
- **A token must not become a security boundary.** ADR 0028 rule 4 says
  the licence key is a commercial control, not a security one; the same
  holds here. A token that unlocks a *feature* is commercial. The moment
  one gates *data access*, it has become a security control and needs the
  analysis a commercial control never needed — that is the line to watch
  when the higher-tier feature is one that reads clinical data.

### Two constraints that are not pending

1. **Expiry never takes the clinic's data.** §2's floor and ADR 0028
   rule 3 apply unchanged. This is the sharpest edge in the whole
   feature: a higher-tier module writes rows during a trial, the token
   expires, and those rows are still part of the patient's clinical
   record. What ends is the ability to *create more* with that feature.
   Reading, backing up and answering subject rights over what already
   exists must survive expiry — as must the record's visibility in the
   patient's history, which is not the same thing as the module staying
   installed. In particular **the CSV export of §2 keeps covering rows
   written under an expired token**: data created during a trial is the
   clinic's data on the same terms as the rest, and a trial that ends by
   making its own output unexportable would be a trap rather than a
   trial. Whatever is built here has to answer that before it ships.
2. **A trial is never the reason a clinic has the compliance floor**, and
   its expiry is never the reason a clinic loses it. Subject rights, PII
   redaction, the CSV export and the rest of §2 sit outside every tier
   and every token.

## 5. Open questions

Everything here needs a decision before a price list exists. None of it
blocks engineering, because none of it changes the shape above.

**Pricing**

- Price per cell in the §1 matrix. Currency and whether MX and ES are
  priced separately (default currency is MXN; `verifactu` serves ES).
- Unit: flat per deployment, per chair/cabinet, per practitioner, or per
  active patient. `byok` is per deployment (§1); the rest is open.
- Billing period, and whether an annual commitment is required for
  `self` (it is the tier with the highest support cost per customer).
- Whether `basic` is free at all, and if so under which delivery. Free
  **hosted** is the highest-liability cohort: no revenue, full
  *encargado* obligations over health data. Free **self-hosted
  evaluation** carries none of that. The recommendation on record is to
  make the free thing evaluation, not production.

**Licence lifecycle**

- Evaluation cap: what is capped and at what number.
- Grace period after `expires_at`, and renewal notice window.
- Licence term and whether it is per released version or per calendar
  period (the BSL conversion is per version — the two clocks should not
  be confused).
- Issuance: who signs, where the signing key lives, how a key is
  delivered, revoked and re-issued. Key custody and rotation are an
  operational commitment we do not have yet.
- Grandfathering: existing production self-hosters get a named key
  rather than an argument ([ADR 0004](../adr/0004-bsl-license.md)
  Amendment 1).

**Trials and temporary upgrades** — see §4 for the full list; the
headline numbers are the trial duration per tier, the duration of a
temporary upgrade, and whether either may be granted twice.

**Product shape**

- Whether `medium` and `advanced` are ever defined — see §7.
- The module set each cell maps to, expressed as `modules_enabled`.
  A tier is a *provisioning template* that yields a module set; it is
  never consulted at runtime (ADR 0024 rule 3).
- Migration between cells: `self` → `managed` and back. This is a data
  export/import path with a custody change in the middle, and it should
  be specified before it is sold, not after a customer asks to leave.

**The export guarantee** (§2)

- Scope: which tables a clinic-wide CSV export covers, and whether it is
  one file per table or a single archive.
- Where it lives, given that it must not be inside the module set a tier
  controls.
- Whether it is offered in the UI, on a schedule, or both.

**Legal**

- `LICENSE` now carries an *Additional Use Grant* (non-production free,
  production only under a Licensor-issued authorization or a commercial
  licence). **It has not been reviewed by counsel, and that review is
  still the blocker for actually selling anything.** Two questions the
  drafting surfaced and cannot answer: the Licensor is "DentalPin
  Contributors", which is not a legal entity able to grant a commercial
  licence or issue a key — so *who signs* is unresolved — and the trial
  path in the grant is written to follow whatever authorization the
  Licensor issues, which ties the licence to §4's token mechanism and
  keeps the trial length a commercial parameter rather than a licence
  term. That is deliberate; confirm it is what you want before signing
  anything.
- The processing contract that `managed` implies is still missing
  ([`todos.md`](../technical/todos.md)).
- The Veri\*Factu *productor del SIF* role transfers to the operator. A
  self-hosted clinic becomes its own producer and needs to be told so in
  writing, at purchase.

## 6. Where the pairing rule is enforced

The one rule that is decided (§1) is also the one that is built. Both
halves are mandatory at creation and neither is defaulted, because a
default on either half decides a commercial offer by accident.

| Half | Where it is declared | Mandatory how |
|---|---|---|
| `account_tier` | the creation payload → `clinics.account_tier` | required field on `SystemSetup`; the column has **no server default** and a `CHECK` restricting it to the taxonomy |
| `custody_mode` | `TENANT_CUSTODY_MODE` → `TenantContext.privacy` | already refused at boot if unrecognised (ADR 0023 Amendment 1) |

The pairing itself is **not** a database constraint, and that is
deliberate: only one half is in the tenant's own database.
[ADR 0024](../adr/0024-control-plane-holds-what-constrains-the-customer.md)
rule 2 keeps `custody_mode` out of the data plane so that a claim about
who can read a database is not stored where its own subject can rewrite
it. A `CHECK` spanning both halves would require moving custody down,
which is the trade already refused. So the rule is enforced in the
application, at the two moments both halves are known at once:

1. **At clinic creation** — `POST /api/v1/auth/setup` validates the pair
   and answers `422` with the tiers that mode is sold under. The
   companion `GET /api/v1/auth/setup/status` reports the deployment's
   custody mode and the tiers it may create, so the first-run screen
   offers a choice that will be accepted rather than one that gets
   refused.
2. **At boot** — the custody half is an environment variable and can be
   changed under clinics that already exist. Flipping a deployment
   holding `basic` clinics to `self` would strand them silently, so the
   lifespan audits the tiers in use and **warns**. It warns rather than
   refuses for the same reason ADR 0028 rule 3 gives: taking a working
   clinic offline over a commercial rule is worse than the rule being
   briefly untrue.

Adding a tier to `AccountTier` without deciding its custody rule fails
`backend/tests/test_account_tier_custody.py::test_every_tier_is_covered`.

Code: `backend/app/core/privacy/tiers.py`.

## 7. Why `medium` and `advanced` stay undefined

They are reserved names in `ACCOUNT_TIERS` with no behaviour attached,
and that is their value. Defining them now means inventing the boundary
between them, and an invented boundary becomes a product commitment that
is expensive to move. `clinic` is what exists and what we know how to
build. The next row gets written by the first customer who says it does
not fit them.

## References

- [ADR 0028](../adr/0028-self-hosting-is-the-premium-tier.md) — self is
  the premium tier, activated by a signed key
- [ADR 0023](../adr/0023-privacy-policy-and-custody-modes.md) — the three
  custody modes and their real implementation status
- [ADR 0024](../adr/0024-control-plane-holds-what-constrains-the-customer.md) —
  why `account_tier` never gates anything at runtime
- [ADR 0004](../adr/0004-bsl-license.md) — BSL, and Amendment 1 on
  production use
- [`../technical/multi-tenancy.md`](../technical/multi-tenancy.md) —
  where a licence resolves into `TenantContext`
- [`../technical/todos.md`](../technical/todos.md) — the compliance gaps
  referenced in §2
