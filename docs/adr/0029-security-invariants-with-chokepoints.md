# 0029 — Security is a set of invariants with chokepoints, not a list of practices

- **Status:** proposed
- **Date:** 2026-09-01
- **Deciders:** Eduardo
- **Tags:** security, auth, testing, compliance

## Context

DentalPin has real security controls and no security *model*. `require_permission`
gates endpoints, every service filters by `clinic_id`, SQLAlchemy parameterises
queries, Vue escapes by default, and [ADR 0006](0006-budget-public-link-2-factor-auth.md)
gives the patient-facing budget link two factors, a lockout and an access log. What
holds these together is convention: a rule written in `CLAUDE.md` and repeated by
hand across 24 modules.

Convention has already failed here at least once. The 2026-07-03 adversarial audit
found `POST /auth/users` writing a caller-supplied `clinic_id` verbatim into a new
`ClinicMembership` — an admin of Clinic A could mint themselves an admin membership
in Clinic B. The permission check was present and correct; the *object* the
permission applied to was never checked. It was fixed, and what makes it stay fixed
is `tests/test_auth_create_user_scope.py`, not the fix.

That is the whole argument. This codebase already knows it: PII is not "remembered",
it is classified on the column and `test_pii_redaction_contract.py` fails on an
unclassified one ([ADR 0025](0025-pii-is-classified-on-the-column.md)). Egress is not
remembered, it is declared in the manifest and CI fails on drift
([ADR 0027](0027-egress-is-declared-in-the-manifest.md)). Events are not remembered,
`test_event_transaction_boundary.py` holds the allowlist
([ADR 0019](0019-events-publish-after-commit.md)). Security is the last cross-cutting
concern still governed by discipline alone.

## Decision

**Every security guarantee in DentalPin is stated as an invariant, enforced at a
single chokepoint, and pinned by a test that fails CI when the invariant is broken.
A control with no chokepoint is an intention; a chokepoint with no test is a
regression waiting for a release.**

Six invariants. Each row names where the guarantee is *made* and what *breaks* when
it stops being true.

| # | Invariant | Chokepoint | Test that fails |
|---|-----------|------------|-----------------|
| 1 | No mounted route serves without a declared permission | `require_permission` | `test_route_authorization_coverage.py` |
| 2 | No row leaves the database without a tenant filter | the request's DB session | `test_cross_tenant_isolation.py` |
| 3 | No session outlives its revocation | `auth_sessions` + rotation | `test_refresh_rotation.py` |
| 4 | No SQL is built by string concatenation | the ORM | `test_no_dynamic_sql.py` |
| 5 | No access to clinical data goes unrecorded | audit middleware | `test_clinical_access_audit.py` |
| 6 | No weak secret boots in production | `config.Settings` validators | `test_production_secrets.py` |

### 1 — Authorization is proven for every route, not per route

`require_permission` is sound. What is unproven is its *coverage*: nothing today can
answer "which mounted routes have no permission dependency?" The test enumerates the
mounted app and fails on any route lacking one, against an explicit allowlist —
`/login`, `/setup`, `/health`, `/ready`, and the public budget router, each with a
one-line reason next to it.

Enumeration goes through `app.openapi()["paths"]`, not `app.routes`: since FastAPI
0.141 the latter holds lazy `_IncludedRouter` wrappers, as
`tests/test_module_state_gating.py:62` already documents.

**The first run of this test was the deliverable, and it has now run.** Of **400
mounted method+path pairs, 18 carry no permission** — and every one of the 18 turned
out to be legitimate: fourteen deliberately public (the auth bootstrap, the two
probes, ADR 0006's six patient-facing budget routes, and the Kapso webhook, which is
authorized by a per-clinic HMAC signature rather than by a role) and four that need a
user but no permission (`/auth/me`, the two clinic-metadata reads that answer from the
caller's own context, and the sidebar inventory, whose nav entries are already filtered
by the caller's permissions).

The scan did produce one genuine surprise, and it went the other way. Six
`schedules` routes — every `/professionals/{professional_id}/…` read and write —
appeared ungated and are not: they call `_require_professional_access` in the handler
body, because the permission depends on whether you are managing your own calendar or
somebody else's, which is not known until the path parameter resolves. Reading those
six as gaps and "fixing" them would have broken working authorization. So the marker
has two forms: the `require_permission` dependency, which stays the default, and a
`@declares_permissions(...)` decorator for the object-dependent case, which changes no
behaviour and exists so that in-body enforcement is *declared* rather than merely
present. It is not a way to quiet the test, and its docstring says so.

Corollary, non-negotiable and worth writing down because it is the mistake juniors
make: `frontend/app/middleware/auth.global.ts` is **user experience, not security**.
It stops a receptionist from seeing a broken page. It stops nobody from calling the
endpoint.

### 2 — Tenant isolation moves from convention into the session

Invariant 1 covers function-level access. Object-level access — the caller has
`patients.read` but for *another clinic's* patient — is where the audit found its
worst finding and where the current design offers no structural help. A single
forgotten `.where(Model.clinic_id == ctx.clinic_id)` in any of 24 modules is a
cross-tenant leak, and nothing catches it.

Two steps, in order.

First, a cross-tenant sweep, which **has now landed**. It is driven by the route
table rather than by a hand-kept list: 35 mounted GET endpoints across 13 modules take
a `{patient_id}`, so one foreign patient exercises nearly every module holding patient
data. The caller is an admin — the role with `*` — so nothing it finds can be a
permission failure in disguise: if a response comes back, authorization allowed it and
only scoping could have stopped it.

**No disclosure was found.** Three routes did answer about a patient in another
tenant, and the distinction between them matters:

- `billing/patients/{id}/summary` and `payments/patients/{id}/ledger` aggregated under
  a correct `clinic_id` filter, so they returned zeros and leaked nothing. What they
  never did is check that the patient was the caller's, so they answered a question
  they should not have understood. Each now calls an `_ensure_patient` helper mirroring
  the one odontogram and periodontogram already carry — minus its `status != "archived"`
  clause, because money outlives the chart and an archived patient's ledger still has
  to be readable.
- `notifications/preferences/patient/{id}` was a different animal: it called
  `get_or_create_patient_preferences`, which **writes** a `notification_preferences`
  row carrying the caller's `clinic_id` and the unvalidated `patient_id` — a column
  whose FK points at `patients.id`. A GET therefore created a row in clinic A
  referencing clinic B's patient: not a disclosure, but a cross-tenant write performed
  by a read. Its guard went into the service rather than either handler, because all
  three call sites — the GET, the PUT, and the inbound-message gateway — reach the
  write through it.

A second sweep followed, over the verb with the worse ending. 32 mounted DELETE
routes take an id in the path, and a cross-tenant delete does not disclose another
clinic's data — it destroys it. Seven of them, one per module holding patient data,
are now swept with a foreign row seeded for each. **All seven refuse.** The assertion
that carries the weight is not the status code but the snapshot: a 404 that deleted
anyway would pass a status check and fail the clinic, so the row's existence *and* its
soft-delete markers are compared before and after — `patients` is soft-deleted by
convention, and "the row is still there" is not the same claim as "the row is
untouched".

**All three findings were fixed rather than recorded, so the `KNOWN_UNSCOPED` baseline
is empty.** It stays in the file because `strict=True` makes it honest in both
directions, in the spirit of [ADR 0021](0021-module-layers-are-typechecked.md): an
entry added there to quiet a failure becomes a failure of its own the day the route is
fixed. A baseline nobody can park anything in quietly is worth more than no baseline.

Second, and this is the one that actually changes the shape of the problem:
**PostgreSQL row-level security**, with the request session issuing
`SET LOCAL app.clinic_id` from `ClinicContext`. Under RLS a forgotten filter returns
nothing instead of returning somebody else's patients. It is the only version of this
invariant that does not depend on the author of the next module.

RLS is real work and it interacts with the per-module Alembic branches
([ADR 0002](0002-per-module-alembic-branches.md)), so it lands after the test — the
usual order in this codebase: observe, then enforce.

### 3 — Sessions become revocable

This is the largest gap in the current system, and the shape of it is uncomfortable:
**the patient-facing budget link is better protected than the clinic's own admin
login.** ADR 0006 gave the patient a second factor, a persistent attempt log, a
lockout that notifies reception, and an independently-rotatable secret. Staff auth has
a 5/minute rate limit held in process memory.

Concretely, today:

- Access and refresh tokens live in **JS-readable cookies**
  (`frontend/app/composables/useAuth.ts:39`). A single XSS anywhere in the app is a
  seven-day refresh token, which is what turns a contained defect into a full
  compromise. This is also why invariant 4's CSP is not cosmetic.
- **Refresh tokens do not rotate and cannot be revoked individually.** A stolen one is
  indistinguishable from the legitimate one for its whole lifetime.
- `token_version` (`app/core/auth/dependencies.py:72`) is the only revocation
  mechanism and it is a global switch — it logs the user out of every device, and it
  is incremented in exactly one place, when an account is deactivated
  (`app/core/auth/router.py:527`).
- There is **no server-side logout**. `useAuth.logout()` clears a cookie; the token
  stays valid until it expires.
- `slowapi`'s limiter is in-memory: it resets on restart and is not shared across
  workers or replicas.

The invariant: a session that has been revoked — by logout, by password change, by an
admin, or by detected theft — stops working at the next request. That requires
persisted refresh tokens keyed by `jti`, rotation on every use, and **reuse
detection**: a refresh token presented twice means one of the two holders is an
attacker, so the whole session family dies and the event is recorded.

**The backend half has landed.** `auth_sessions` holds one row per refresh token, keyed
by the token's `jti`, with every row descending from one login sharing a `family_id`.
Rotation stamps `rotated_at` and issues a successor; presenting a spent or revoked token
revokes the family and logs it. `/auth/logout` exists and reaches the server — until now
`useAuth.logout()` cleared a cookie and left the refresh valid for its full seven days,
so logging out ended the tab and not the session.

Three deliberate limits. A refresh token minted before the table names no row and is now
refused, which logs its holders out once. The **access token paired with a revoked
refresh keeps working until it expires** — 15 minutes — because an access token is
stateless by design and checking a table on every request is precisely what
statelessness buys; `token_version` remains the switch for the case where those minutes
matter. And the table holds no IP and no user agent: both are personal data needing
classification and retention ([ADR 0025](0025-pii-is-classified-on-the-column.md)), and
neither is needed to *end* a session, only to label one in a UI that does not exist yet.

**The frontend half has not.** Tokens still live in JS-readable cookies, so an XSS still
hands an attacker a working refresh — it now gets caught the second time it is used,
which is detection rather than prevention.

Note one thing that already works and should not be "fixed": role changes take effect
immediately, because `get_clinic_context` reads `membership.role` from the database on
every request rather than trusting a claim in the token.

### 4 — Injection is closed by construction, and kept closed by a test

SQL injection is, today, close to a non-risk: everything goes through SQLAlchemy 2.0
with bound parameters. There are three raw-SQL sites and all three are safe. The one
worth naming is `app/modules/treatment_plan/service.py:1452` and `:1461`, which
interpolate `tab_where`, `extra_where` and `order_by` into f-strings — safe because
those three come from a closed `if/elif` of literals and every user value travels as
`:params`, and fragile the moment someone wires a `?sort=` parameter to it.

So the control is not "write careful SQL". It is a test with a reasoned allowlist —
the `test_event_transaction_boundary.py` pattern applied to a second rule — and it has
now landed. An AST walk rather than a grep, because what matters is not that `text()`
appears but that its argument was assembled from parts: `sa.text("… WHERE id = :id")`
must not be flagged and `sa.text(f"… {table}")` must be, even when `table` is a literal
three lines up. Entries are keyed `path.py::function`, so an unrelated edit above does
not invalidate them and a *new* interpolation elsewhere in an already-listed file is
still caught.

Nine call sites exist. Eight are safe and listed with the reason. The ninth was not:
`migration_import`'s `compute_logical_hash` interpolated a DPMF entity table name into
SQL trusting a comment that said the writer validates it — except that for an uploaded
file the writer is the clinic's old export tool, not us, and `reader.entity_iter`
already validated the identical value from the identical source before its own
interpolation. One validated, one trusted: an asymmetry, not a decision. Fixed rather
than listed. The blast radius was narrow — SQLite, on a throwaway connection over the
uploaded file — which is why it survived a read-through and not a scan.

XSS is the same story from the other side. Vue escapes by default; the five `v-html`
sites are accounted for (`CopilotMarkdown.vue` sanitises with DOMPurify, the
odontogram ones inject module constants). What is missing is the backstop: **the API
sends no security headers at all** — no CSP, no `X-Content-Type-Options`, no
`frame-ancestors`, no HSTS, no `Referrer-Policy`. ADR 0006 says the public budget link
is "mitigated separately with `noindex` headers"; that header does not exist anywhere
in the codebase. Roughly fifteen lines of middleware in `app/main.py` closes all of it,
and it is the highest-yield change in this ADR per line written.

One narrower point: `CopilotMarkdown` renders LLM output as HTML with DOMPurify's
default profile, which permits `<a href>`. Link schemes get restricted to
`http`/`https`/`mailto`.

### 5 — Access to clinical data is recorded

There is an audit trail for the copilot (`agent_audit_logs`) and one for the public
budget link (`budget_access_logs`). There is **none for staff opening a patient
chart**.

For dental software this is not a hardening nicety. Art. 30 and 32 GDPR expect it, and
the realistic incident is not an external attacker — it is an employee reading the
record of a neighbour, an ex-partner, or a local celebrity. Without a log, that event
is not merely unpunished; it is undetectable, and the clinic cannot answer the
question a regulator will ask.

The invariant follows the shape of
[ADR 0026](0026-subject-rights-are-a-module-contract.md): a module holding patient data
records reads of it, and a module that skips the hook is silently absent from the
trail — so the contract is tested, not trusted. The log is append-only, carries the
subject id rather than the subject's data, and gets a retention policy from day one,
the way `purge_budget_access_logs` already does.

### 6 — Production refuses to boot on a weak secret

`SECRET_KEY: str` in `app/config.py:13` accepts anything. `CLAUDE.md` promises a
32-character minimum and nothing enforces it. `BUDGET_PUBLIC_SECRET_KEY` falls back to
`SECRET_KEY` silently (`app/config.py:21`), which quietly dissolves the blast-radius
separation ADR 0006 was explicit about wanting.

Under `ENVIRONMENT=production`, a Pydantic validator refuses to start on a secret that
is short, is a known default or example value, or is derived from another secret.
Refusing to boot is the correct failure here and it is a deliberate departure from the
posture of ADR 0027 and [ADR 0028](0028-self-hosting-is-the-premium-tier.md), which
warn rather than block: those protect a commercial rule and a working clinic's day,
while this one means every JWT the deployment ever issues is forgeable. A deployment
that will not start is visible in thirty seconds; a weak signing key is visible after
the breach.

While in there: JWTs get a `kid` header, so key rotation is possible later without a
flag day.

### Owed: activation keys and entitlement tokens

[ADR 0028](0028-self-hosting-is-the-premium-tier.md) closes by deferring trials and
temporary tier upgrades to "the security model, which is pending", and
[`licensing-and-packaging.md`](../features/licensing-and-packaging.md) §4 has a
subsection headed *What the security model has to state*. This is that document, and
until now it said nothing — so both references dangled. They should not, and the gap
is wider than the deferral implies.

**None of the licensing machinery exists — not the trials, the licence key itself.**
There is no `DENTALPIN_LICENSE`, no signature verification, no public key shipped in
the release, and no entitlement resolution: `TenantContext.modules_enabled` is filled
from `module_registry.list_modules()` (`core/tenancy/single.py:128`), which is the
install state and nothing else. ADR 0028 is `accepted` and describes machinery nobody
has written. That is a legitimate state for an ADR — the decision is made, the code is
not — but it belongs next to the invariants, because a reader who finds `account_tier`
on the `clinics` table will reasonably assume something enforces it. Nothing does, and
per [ADR 0024](0024-control-plane-holds-what-constrains-the-customer.md) rule 3 nothing
in the data plane should: the tier is a per-clinic fact in the customer's own database
and is never consulted at runtime.

**They are two artifacts, and the security model's first job is to keep them apart.**
The licence key is issued once, read at boot, scoped to a deployment, verified offline.
An entitlement token is issued repeatedly, redeemed by a user, scoped to a clinic, and
expires on its own. Building the second as a variation on the first carries the wrong
assumptions across — offline verification of a *self-expiring* grant with no issuer to
ask is where replay and clock skew bite, and it is the hard problem of the two.

When it is specified, it owes answers to what §4 already lists: what issues and signs a
token and whether it is single-use; offline versus control-plane verification; replay,
and reuse of one token across deployments; who may redeem one — an admin, or a
permission of its own; and revocation before expiry, including what a revoked-but-unexpired
token does.

Two rules constrain the answer before it is written, and both are this ADR's business
rather than the feature brief's:

1. **A token that gates data access has stopped being a commercial control.** ADR 0028
   rule 4 accepts that the licence check is patchable in an afternoon, because what it
   protects is a contract, not a boundary. That acceptance does not transfer to anything
   standing between a user and a patient record. The line gets hard to see exactly where
   a higher-tier feature is one that reads clinical data, which is where it will first be
   tested.

2. **Expiry never takes the clinic's data**, and this is the constraint a naive
   implementation breaks first. A higher-tier module writes rows during a trial; the
   token expires; those rows are still part of a patient's clinical record. Reading them,
   backing them up, exporting them and answering subject rights over them
   ([ADR 0026](0026-subject-rights-are-a-module-contract.md)) must all survive expiry.
   A trial that ends by making its own output unexportable is a trap, not a trial.

Unscheduled, and deliberately not given an invariant number: an invariant here would be a
chokepoint and a test for a mechanism that does not exist, which is the failure mode this
ADR opens by naming. It gets one when the mechanism is specified.

### Not in scope, deliberately

Named so they are not mistaken for oversights, and because two of them are more likely
to hurt a clinic than anything above: **encrypted, restore-tested backups** (the
realistic catastrophic scenario for a dental practice is ransomware, not XSS);
**dependency scanning** in CI (`pip-audit` / `npm audit` — today the likeliest route to
an incident is a transitive dependency); **file-upload hardening** in `media` (magic-byte
MIME validation, `Content-Disposition: attachment`, a serving origin separate from the
app); and **prompt injection into copilot tools**, where an agent acts with the user's
full authority on text that arrived in a patient note. Each is real, each needs its own
decision, and none of them is an invariant of the kind this ADR is about.

## Consequences

### Good

- Security stops being knowledge held by whoever wrote a module and becomes something
  CI can answer. A new module author gets the guarantees without reading this file.
- The first runs of invariants 1 and 2 are a *measurement* of the current codebase.
  That number does not exist today.
- Invariant 3 makes "the laptop was stolen" an operation the clinic can actually
  perform, rather than a global logout of every device.
- Invariant 5 gives the clinic an answer to the question a regulator or a complaining
  patient will ask, which is the one compliance question the current system cannot
  answer at all.
- Six named invariants make it obvious what is *not* claimed. A security posture that
  only lists strengths is not a posture.

### Bad / accepted trade-offs

- **Half of this is implemented.** Invariants 1 and 6 have landed, invariant 2's test
  half with them, and invariant 4's headers (`app/config.py`, the `security_headers_middleware` in
  `app/main.py`, `frontend/nuxt.config.ts` `routeRules`,
  `app/core/auth/dependencies.py`). Still an intention: invariant 4's dynamic-SQL
  test and the frontend CSP — which needs per-request nonces before it can be
  anything but decorative — plus invariants 2, 3 and 5 entirely. That remainder is
  precisely the failure mode this ADR argues against. It earns `accepted` when
  invariant 4 is complete.
- Invariant 1 arrives with an allowlist, and an allowlist is a place to hide. Two
  mitigations, one social and one not: every entry carries a written reason, and the
  list is split into "needs no credentials" and "needs a user but no permission",
  with each bucket verified against the route's own dependency tree. An entry parked
  in the wrong bucket fails as loudly as a missing gate. What no test can catch is a
  reason that is simply wrong.
- Invariant 2's RLS half is genuinely expensive and touches every module's migration
  branch. It may stall at the test half for a long time, which leaves the structural
  guarantee unmade — and the test half only covers the routes it enumerates. The
  `{patient_id}` and `{professional_id}` GET sweeps are in, and seven of the 32
  DELETE routes; `{budget_id}`, `{invoice_id}`, `{appointment_id}` reads and the
  remaining 25 destructive routes are not, because each needs its own seed chain.
  **PUT and PATCH are untouched entirely** — 53 mounted routes — because unlike DELETE
  they need a valid body per endpoint, which is the sweep's next real cost. Nothing at
  all covers the service layer, where `patients_clinical.get_allergy(db, allergy_id)`
  still takes no `clinic_id` and is kept honest only by its router: correct today,
  and one direct caller — a copilot tool, an event handler — away from not being.
- Invariant 3 changes the login contract, so it costs a coordinated frontend and
  backend release and logs every user out once.
- Invariant 5 writes a row per clinical read. On a busy day that is the highest-volume
  table in the system, and its retention policy is load-bearing rather than tidy.
- A test suite that asserts coverage will be *felt*: adding a route now means adding a
  permission or arguing for an allowlist entry. That friction is the product.

## Alternatives considered

- **Keep it as guidance in `CLAUDE.md`.** The status quo. It is how the `create_user`
  cross-tenant hole shipped: the rule was written down, correct, and not applied at one
  call site.
- **A periodic external audit instead of tests.** The 2026-07-03 audit was valuable and
  is already partly stale. An audit is a snapshot; an invariant is a ratchet. They
  answer different questions and the audit does not replace this.
- **A WAF or gateway in front of the API.** Buys generic injection filtering and buys
  nothing at all against the two risks that matter here — cross-tenant object access
  and a stolen refresh token — because both are perfectly well-formed authenticated
  traffic.
- **Encrypt PII at the column level instead of auditing access.** Solves a different
  threat (stolen disk) and would break search, sorting and the existing redaction
  design ([ADR 0025](0025-pii-is-classified-on-the-column.md)). Backup encryption
  covers the disk case at a fraction of the cost.
- **Do invariant 2's RLS first, since it is the strongest.** Rejected on sequencing:
  the coverage tests are days of work and tell us where we actually stand, and RLS
  designed before that measurement would be designed blind.

## Implementation order

By yield per unit of work, not by severity:

1. ~~Security headers + `Referrer-Policy`/`X-Robots-Tag` on public routes~~ — **done**
   (invariant 4, headers half). The JWT `kid` was deliberately dropped from step 2: with
   one key and no resolver on the verifying side it adds nothing today, and it belongs
   with the rotation work it is for.
2. ~~Production secret validators~~ — **done** (invariant 6).
3. ~~Route authorization coverage test~~ — **done** (invariant 1); the finding is
   written up above.
4. ~~Cross-tenant isolation tests~~ — **done** (invariant 2, first half); findings
   above. Cheaper than feared: the sweep adds ~3 minutes to the suite, so it needs no
   marker of its own. The dynamic-SQL test landed with it, completing invariant 4
   except for the frontend CSP.
5. Refresh rotation, reuse detection, server-side logout, Redis-backed rate limiting
   (invariant 3).
6. Clinical access audit (invariant 5).
7. RLS (invariant 2, second half).

## How to verify the rule still holds

- `backend/tests/test_route_authorization_coverage.py` — every mounted path carries a
  permission dependency, or an allowlist entry with a reason.
- `backend/tests/test_cross_tenant_isolation.py` — clinic A's admin gets nothing of
  clinic B's on a foreign id, across every `{patient_id}` and `{professional_id}`
  route; `KNOWN_UNSCOPED` is the strict-xfail baseline, and a positive control proves
  the sweep would notice a leak rather than passing on a broken fixture.
- `backend/tests/test_refresh_rotation.py` — a reused refresh token kills the session
  family; logout invalidates server-side.
- `backend/tests/test_no_dynamic_sql.py` — fails on a new `sa_text(f"...")` outside the
  allowlist.
- `backend/tests/test_security_headers.py` — every response, success and error, carries
  the bounding headers; HSTS stays production-only.
- `backend/tests/test_clinical_access_audit.py` — a module holding patient data that
  does not record reads fails its contract.
- `backend/tests/test_production_secrets.py` — `ENVIRONMENT=production` plus a weak,
  default or derived secret raises at settings construction.

## References

- `backend/app/core/auth/dependencies.py:72` — `token_version`, the only revocation today
- `backend/app/core/auth/permissions.py` — `has_permission`, the RBAC chokepoint
- `backend/app/core/auth/router.py:527` — the single `token_version` increment
- `backend/app/config.py:13,21` — unvalidated `SECRET_KEY`, derived budget secret
- `backend/app/main.py` — CORS and rate limiting; no security headers
- `backend/app/modules/treatment_plan/service.py:1452` — the interpolated SQL
- `frontend/app/composables/useAuth.ts:39` — tokens in JS-readable cookies
- `frontend/app/middleware/auth.global.ts` — route guard: UX, not authorization
- `backend/tests/test_auth_create_user_scope.py` — the audit finding that made this ADR
- `docs/technical/audit-2026-07-03.md` — adversarial audit, RBAC H1
- [ADR 0006](0006-budget-public-link-2-factor-auth.md) — public-link two-factor design
- [ADR 0019](0019-events-publish-after-commit.md) — the allowlist-test pattern
- [ADR 0025](0025-pii-is-classified-on-the-column.md) — classify at the chokepoint
- [ADR 0026](0026-subject-rights-are-a-module-contract.md) — module-contract + test shape
- [ADR 0027](0027-egress-is-declared-in-the-manifest.md) — declare, observe, then enforce
