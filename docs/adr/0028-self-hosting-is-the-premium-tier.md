# 0028 — Self-hosting is the premium tier, activated by a signed key

- **Status:** accepted
- **Date:** 2026-08-31
- **Deciders:** Eduardo
- **Tags:** licensing, privacy, tenancy, business-model

## Context

[ADR 0023](0023-privacy-policy-and-custody-modes.md) defined three
custody modes and left one question open in writing: `self` is "the
*most expensive* option for the clinic — they carry infrastructure,
backups and upgrades — and how it is offered is pending the business
model."

The unstated assumption in everything written since is that `self` is
the free floor and `managed` is what gets paid for. That prices custody
backwards on both sides of the trade.

**On the customer's side**, `self` is the only mode whose guarantee is
real. ADR 0023's own status table says so: `managed` names a break-glass
mechanism that does not exist, `byok` is vocabulary without envelope
encryption, and `self` holds because it is an *absence* — there is no
operator, so there is nothing to bypass. The mode a clinic would pay
most for is the one currently marked free.

**On our side**, `self` is not cheap to supply. It costs no servers, but
it costs the support surface: an operator we cannot see, a version we
cannot upgrade, an incident we can only advise on, and — under
Veri\*Factu — a productor del SIF who is the clinic itself and needs the
software kept current against AEAT. Meanwhile the mode we were planning
to charge for is the one where we hold a clinic's patient records and
take on the *encargado* role, with the processing contract that implies
([`todos.md`](../technical/todos.md) lists it as missing). A funding
model that monetizes custody is a funding model that wants more custody.

There is also a plain drafting problem underneath. The `LICENSE` grants
"the right to copy, modify, create derivative works, redistribute, and
make **non-production** use of the Licensed Work", and notes that the
Licensor *may* make an Additional Use Grant permitting limited
production use. **No Additional Use Grant exists in the file.** The
"Use Limitation" line in the header is a non-standard field that reads
as if production self-hosting were granted, and
[ADR 0004](0004-bsl-license.md) states outright that the source is
"self-hostable by any clinic". Those describe a permission the licence
text never gave. Two problems, one answer.

## Decision

**`self` is the premium delivery tier. It is sold, and a deployment
activates it with a signed licence key.**

Six rules.

1. **`self` is priced above `managed`, not below.** What the clinic buys
   is the guarantee itself — the only custody claim that holds without a
   control behind it — plus the right to run in production with nobody
   else in the path. What we sell alongside it is the part a
   self-hoster cannot produce alone: updates, regulatory currency
   (Veri\*Factu against AEAT), and support.

2. **The key is a signed licence artifact, verified offline.** A
   detached signature over `(licensee, tier, custody_mode, issued_at,
   expires_at, entitlements)`, with the public key shipped in the
   release and the licence supplied as a file or `DENTALPIN_LICENSE`.
   **No phone-home.** A call to our servers at boot would contradict the
   exact property the clinic paid for — `SELF` means no operator path,
   and a path is no less a path for pointing outward — and it would
   break an air-gapped deployment. Offline verification also means we
   learn nothing about a deployment we have just promised we cannot see.

3. **The key gates what we supply. It never gates the clinic's own
   data.** This is the load-bearing rule. An absent, expired or invalid
   licence must never block:

   - reading, writing or backing up clinical records,
   - export and erasure under the subject-rights endpoints
     ([ADR 0026](0026-subject-rights-are-a-module-contract.md)),
   - anything already in a patient's record.

   Those are the clinic's obligations as *responsable*, and a vendor
   that suspends them on non-payment makes the clinic breach LFPDPPP or
   GDPR on the vendor's schedule. Expiry degrades **our** side of the
   contract instead: updates stop, module installation stops, support
   stops, and cloud-backed features whose cost is ours stop. For a
   Spanish clinic that is already a hard dependency — a Veri\*Factu
   deployment that stops receiving regulatory updates stops being
   compliant on its own — so the commercial pressure exists without
   anyone having to hold a record hostage.

4. **The key is a commercial control, not a security control.** The
   source is available and the check is patchable in an afternoon. That
   is accepted, on the same reasoning BSL already accepts: the point is
   that the licensed path is the default and the unlicensed one is a
   deliberate act, and that a licensed deployment holds an artifact
   naming its licensee — which the Veri\*Factu producer role needs
   anyway.

5. **The licence is the one control-plane fact that survives into a
   self-hosted deployment.** This amends
   [ADR 0024](0024-control-plane-holds-what-constrains-the-customer.md),
   which says `SELF` collapses the two planes. It still collapses them
   for everything that constrains data access; what remains is a signed
   statement of *what was sold*. It is signed for the same reason
   `tenant_identity` is — verifiable by the holder, forgeable by nobody
   inside the tenant — and it carries no operator access and no callback,
   so it does not reopen the custody question. A claim about a contract
   is not a channel into a database.

6. **`account_tier` does not gate this.** ADR 0024 rule 3 stands: the
   tier is per-clinic, lives in the customer's own database, and is
   never consulted at runtime. Entitlements are resolved from the key
   into `TenantContext.modules_enabled` at boot, which is the enforcement
   axis. A deployment without a licence runs in a labelled
   **evaluation** state — which is precisely the non-production use the
   BSL already grants for free — not in a crippled production one.

**Not decided here: trials and temporary tier upgrades.** Both are
planned, both are activated by a token, and that token is a *different
artifact from this licence key* — issued often rather than once, redeemed
by a user rather than read at boot, and expiring on its own. Treating
them as a variation on the licence key would carry the wrong assumptions
across. They are handled separately in the security model, which is
pending; the shape and the constraints they inherit from rule 3 are in
[`../features/licensing-and-packaging.md`](../features/licensing-and-packaging.md)
§4. Rule 4 travels with them: a token that unlocks a feature is a
commercial control, and the moment one gates data access it has stopped
being one.

## Consequences

### Good

- The mode with the strongest privacy guarantee is the one that funds
  the project. We stop being in the position of earning more the more
  patient data we hold.
- The licence text and the documentation stop contradicting each other.
- A licensed deployment carries an artifact that names the licensee,
  which the Veri\*Factu *declaración responsable* needs regardless.
- Offline verification keeps `SELF` honest instead of quietly turning it
  into a mode with one outbound connection.

### Bad / accepted trade-offs

- **The `LICENSE` has been redrafted to match, but not reviewed.** The
  non-standard "Use Limitation" line is now a proper Additional Use Grant
  pointing production use at an authorization the Licensor issues or at a
  commercial licence ([ADR 0004](0004-bsl-license.md) Amendment 1). It is
  a draft written alongside this ADR, not legal advice, and it inherits an
  unresolved question it cannot answer itself: "DentalPin Contributors" is
  not an entity that can grant a commercial licence or sign a key.
- ADR 0004 and the README have been telling readers for months that any
  clinic may self-host. Narrowing that reads as a rug-pull even where it
  is not one legally. Anyone already running a production deployment
  should be grandfathered by name in an issued key rather than argued
  with.
- **None of it exists.** No key format, no signing key, no verifier, no
  issuance path, no evaluation state. This ADR fixes the shape.
- A key that blocks nothing the clinic owns is a soft control by
  construction. The real lock is the recurring value — updates,
  regulatory currency, support — and the contract behind it.
- We now operate a signing key, with the rotation, offline custody and
  compromise plan that implies, before the first licence is issued.

## Alternatives considered

- **`self` free, `managed` paid** — the previous implicit model.
  Rejected above: it funds development through the mode where we hold
  the data, and leaves the strongest guarantee as the unpaid, unsupported
  one.
- **Online activation / periodic phone-home** — the standard way to make
  a key enforceable. Rejected: it puts an outbound channel into the one
  mode sold on the absence of any channel, and breaks air-gapped
  installs. A licence that undermines the guarantee it licenses is not a
  licence anyone in this market should buy.
- **Hard kill-switch or read-only lockout on expiry** — rejected under
  rule 3. It holds clinical records hostage and makes us the proximate
  cause of the clinic's own subject-rights breach.
- **Gating on `clinics.account_tier`** — rejected by ADR 0024 rule 3.
  Wrong grain and, worse, authoritative inside the database of the party
  it constrains.
- **Contract only, no key** — cheaper and honest, but indistinguishable
  from free in practice and it produces no artifact naming the licensee.

## How to verify the rule still holds

- `LICENSE` carries an Additional Use Grant consistent with this ADR: the
  trial/token path of rule 3 and the commercial licence are the only two
  routes to production use, and the definition of "production use" is the
  one this ADR prices.
- [ADR 0004](0004-bsl-license.md) Amendment 1 and the README licence
  section describe production self-hosting as licensed, not free.
- `grep -rn "account_tier" backend/app` still shows reads for display
  only. A licence check that branches on it breaks rule 6.
- When implemented: a test that the subject-rights endpoints
  (`/api/v1/privacy/*`) and clinical reads answer normally with an
  absent and with an expired licence. That test is rule 3, and it is the
  one that must exist before any enforcement ships.

## References

- [ADR 0004](0004-bsl-license.md) — the BSL choice and its Amendment 1
- [ADR 0023](0023-privacy-policy-and-custody-modes.md) — the three
  custody modes; Amendment 2 records the commercial reversal
- [ADR 0024](0024-control-plane-holds-what-constrains-the-customer.md) —
  rule 3 (`account_tier` never gates) and the collapsed planes under
  `SELF`, amended by rule 5 here
- [ADR 0026](0026-subject-rights-are-a-module-contract.md) — the
  endpoints rule 3 protects
- `LICENSE` — the Additional Use Grant, drafted and awaiting counsel
- `backend/app/core/tenancy/single.py` — where a licence would resolve
  into `TenantContext`
- [`../features/licensing-and-packaging.md`](../features/licensing-and-packaging.md) —
  the packaging brief this decision feeds: the tier × delivery matrix,
  the licence lifecycle, and the pending trial/temporary-upgrade tokens
  (§4), with every price and duration still open
