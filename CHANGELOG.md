# Changelog

All notable changes to DentalPin are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/) and the project
uses [Semantic Versioning](https://semver.org/).

The `v2.0` line is the first to ship with the post-Fase-B module
architecture: the monolithic `clinical` module is gone, replaced by
four purpose-built modules, and every official module now ships its
frontend as a Nuxt layer under its own Python package.

## [Unreleased]

### Added

- **Every route's authorization is now proven, not assumed** — invariant 1
  of [ADR 0029](docs/adr/0029-security-invariants-with-chokepoints.md).
  `tests/test_route_authorization_coverage.py` walks all 400 mounted
  method+path pairs and fails on any that carries no permission, against
  an allowlist split into "needs no credentials" and "needs a user but no
  permission" — each entry with a reason, and each verified against the
  route's own dependency tree so an entry in the wrong bucket fails too.
  The first run found no unguarded route: all 18 exemptions are
  legitimate. It did find six `schedules` routes that authorize in the
  handler body rather than through a dependency, because the permission
  depends on the path parameter; those now carry a
  `@declares_permissions(...)` marker so the enforcement is declared
  rather than merely present. No behaviour change.

- **Security headers on every response, and secrets that must be real in
  production** — the first two invariants of
  [ADR 0029](docs/adr/0029-security-invariants-with-chokepoints.md).
  The API previously sent no security headers at all; it now sends
  `X-Content-Type-Options`, `X-Frame-Options`, a `default-src 'none'`
  CSP, `Referrer-Policy`, `X-Robots-Tag`, and HSTS in production. The
  rendered app sends the same minus the CSP, plus `no-referrer` and
  `noindex` on `/p/**` — the patient-facing budget link carries its
  token in the path, and
  [ADR 0006](docs/adr/0006-budget-public-link-2-factor-auth.md) assumed
  a `noindex` header that had never existed. Separately,
  `ENVIRONMENT=production` now refuses to boot on a `SECRET_KEY` that is
  short, still the `.env.example` placeholder, or not plausibly random,
  and on a `BUDGET_PUBLIC_SECRET_KEY` that is unset or equal to it —
  two names for one key is not two keys.

- **Privacy settings screen** — a *Privacidad* category in settings with a
  page that handles a patient's access or erasure request and shows the
  log of the ones already handled
  ([ADR 0026](docs/adr/0026-subject-rights-are-a-module-contract.md)).
  Until now the three `/api/v1/privacy` endpoints could only be reached
  with curl, which is not a procedure a clinic can follow. The screen is
  shaped by the two things that make this unlike other settings: the
  reason is required before either action runs (on an erasure it is the
  only record of the request that survives it), and the erasure sits
  behind a confirmation that restates what will happen, then reports the
  sections that legally refused — that refusal is part of the answer the
  clinic owes the patient, not an error. The export downloads as JSON,
  because a portability response is meant to leave the browser.

- **`PrivacyPolicy` — custody and regime declared per tenant**
  ([ADR 0023](docs/adr/0023-privacy-policy-and-custody-modes.md)). Three
  custody modes: `self` (the customer runs the deployment, so no operator
  of ours can reach the data), `managed` (we run it and hold the keys,
  with break-glass operator access that expires, states a reason and
  notifies the clinic) and `byok` (we run it against keys the customer
  holds). The mode determines operator access and key custody rather than
  coexisting with them as flags, so an incoherent policy cannot be
  built. Also carries `jurisdictions` (which documents exist) separately
  from `regulations` (which obligations apply), and a default-deny
  `egress_allowed` set. The policy rides on `TenantContext`;
  `SingleTenantResolver` returns the self-hosted profile, so nothing
  changes for existing deployments. **Declarative only — no component
  enforces it yet.**

- **First-time setup assistant** (issue #85). A fresh install (no users)
  now bootstraps from the UI: `GET /api/v1/auth/setup/status` reports
  whether the system is initialized, and `POST /api/v1/auth/setup`
  atomically creates the first clinic + admin user + admin membership and
  returns tokens. The endpoint is self-closing (409 once any account
  exists). The frontend redirects unauthenticated visitors of an empty
  system to a 2-step `/setup` wizard (admin account → clinic basics);
  remaining configuration is handled by the existing onboarding checklist.

### Changed

- **`LICENSE` gains a real Additional Use Grant.** The file carried a
  non-standard "Use Limitation" field and no Additional Use Grant at all,
  so its Terms granted only non-production use while ADR 0004 and the
  README promised free self-hosting — the licence and the documentation
  described different products. The grant now permits production use on
  exactly two routes: a trial authorization the Licensor issues (which
  ties the licence to the token mechanism the packaging brief plans,
  rather than freezing a trial length into licence text) or a separate
  commercial licence. "Production use" is defined as running a clinic on
  real records, self-hosted or hosted for you, so the line does not turn
  on who owns the server. The competing-managed-service exclusion moves
  inside the grant instead of floating as a stray field, and the Change
  Date now reads per version, which is what ADR 0004 always intended.
  **A draft, not legal advice**: it has not been reviewed by counsel, and
  it inherits one question drafting cannot fix — the Licensor is named
  "DentalPin Contributors", which is not an entity that can grant a
  commercial licence or sign a key.

- **`account_tier` is mandatory at creation, and paired with a custody
  mode.** `clinics.account_tier` carried `server_default='clinic'`, so a
  clinic could come into existence without anyone deciding its tier and
  be silently sold as the current product. The default is gone
  (migration `0011`), a `CHECK` restricts the column to the taxonomy, and
  `POST /api/v1/auth/setup` now requires the tier in its payload —
  the first-run wizard grew a selector for it.

  The tier is one half of a commercial pairing whose other half is the
  deployment's custody mode, and **the entry tiers are sold hosted and
  only hosted**: `basic` and `medium` are always `managed`, every other
  tier may be `self`, `managed` or `byok`
  (`backend/app/core/privacy/tiers.py`). The pairing is deliberately
  *not* a database constraint — only one half lives in this database, and
  [ADR 0024](docs/adr/0024-control-plane-holds-what-constrains-the-customer.md)
  rule 2 keeps `custody_mode` out of the data plane precisely so a claim
  about who can read a database is not stored where its own subject can
  rewrite it. It is enforced where both halves are known at once: at
  clinic creation (`422` with the modes that tier is sold under) and at
  boot, where a lifespan audit **warns** if the custody mode was changed
  under clinics whose tier it does not serve. Warns rather than refuses,
  for the reason ADR 0028 rule 3 gives: taking a working clinic offline
  over a commercial rule is worse than the rule being briefly untrue.
  `GET /api/v1/auth/setup/status` now also reports the custody mode and
  the tiers it may create, so the wizard offers a choice that will be
  accepted. This deployment declares `clinic` + `managed` explicitly
  rather than inheriting either.

- **Self-hosting becomes the premium tier, activated by a signed licence
  key** ([ADR 0028](docs/adr/0028-self-hosting-is-the-premium-tier.md),
  with amendments to [ADR 0004](docs/adr/0004-bsl-license.md) and
  [ADR 0023](docs/adr/0023-privacy-policy-and-custody-modes.md)).
  Documentation only — nothing is implemented. The previous implicit
  model had `self` free and `managed` paid, which prices custody
  backwards: `self` is the one mode whose guarantee holds without a
  control behind it (ADR 0023's status table), and it is the mode where
  we hold none of the clinic's data, so charging for `managed` instead
  meant earning more the more patient records we custody. The key is
  verified **offline** — a phone-home would put an outbound channel into
  the one mode sold on the absence of any channel — and it gates only
  what we supply (updates, module installs, support, regulatory
  currency). It never gates clinical reads, backups, or the
  subject-rights endpoints from
  [ADR 0026](docs/adr/0026-subject-rights-are-a-module-contract.md):
  suspending those on non-payment would make the clinic breach LFPDPPP
  on our schedule. A deployment with no key runs in a labelled
  evaluation state, which is the non-production use the BSL already
  grants. Two things this exposes: `LICENSE` carries no *Additional Use
  Grant*, so its Terms grant only non-production use while ADR 0004 and
  the README were promising free self-hosting — the file needs redrafting
  by counsel, and existing production self-hosters should be
  grandfathered by name rather than argued with. The packaging side —
  the tier × delivery matrix, what may and may not be gated, and the
  four licence states — is drafted in
  [`docs/features/licensing-and-packaging.md`](docs/features/licensing-and-packaging.md),
  with every price, unit and duration explicitly left open. That brief
  also records two mechanisms as **pending**: a trial period per
  `account_tier`, and temporary access to a higher tier's features. Both
  activate through a token, and the token is deliberately *not* the
  licence key — issued often rather than once, redeemed by a user rather
  than read at boot, expiring on its own — so it is handled separately in
  the security model. Two constraints on it are not pending: expiry never
  takes away data created while the feature was available (reads,
  exports and subject rights over it must survive), and a trial is never
  the reason a clinic has the compliance floor. That floor now names an
  **export guarantee**: a clinic can always take its own data out as CSV,
  under any tier, in any licence state, with every trial and token
  expired. Recorded as a promise with its gap stated — the only export
  that ships today is the per-patient subject-rights one and it returns
  JSON, while the only CSV in the codebase belongs to the optional
  `accounting_export` module, which is precisely the kind of tier-gated
  placement the guarantee forbids. The gap is tracked in
  [`docs/technical/todos.md`](docs/technical/todos.md), together with the
  tension it has to resolve: `modules_enabled` gates what runs, so a tier
  that excludes a module would otherwise leave that module's data
  unexportable.

- **Two-plane data model recorded**
  ([ADR 0024](docs/adr/0024-control-plane-holds-what-constrains-the-customer.md)):
  the data plane holds what the customer owns, the control plane holds
  what constrains them. Fixes where `tenant_id`, `custody_mode`,
  `clinic_id` and `account_tier` are each authoritative, rules out a
  tenant→clinic foreign key (it crosses a database boundary by design),
  and specifies a signed single-row `tenant_identity` mirror so a
  restored backup can name its tenant without becoming a forgeable
  custody claim. Design only — no control plane exists yet.

- **`clinics.tenant_type` renamed to `clinics.account_tier`** (migration
  `0009`, API field and locale key `auth.accountTiers` renamed with it).
  The column holds a commercial tier for one clinic; "tenant" in this
  codebase is the DB-isolation unit a clinic lives inside (ADR 0012). With
  custody landing on the tenant (ADR 0023), a control plane would have put
  `tenants.custody_mode` next to `clinics.tenant_type` and the two would
  have read as one axis. Renamed while nothing gates on the column. The
  migration is a rename, so tiers already stored survive.

- Recorded the pending compliance work for the primary market in
  [todos](docs/technical/todos.md): the **LFPDPPP obligations** with no
  implementation at all (express written consent for health data as a
  *dato personal sensible*, the *aviso de privacidad*, and the processing
  contract that hosting implies), the **retention policies** that would
  replace each contributor's `retention_reason` prose with an actual
  window from NOM-004-SSA3-2012 and CFF art. 30, and the shape problem
  ARCO poses for `core_subject_request` — it records requests already
  executed, while statutory deadlines need them recorded on arrival.
  Flagged as unverified: Mexico's law was replaced in March 2025 and
  oversight moved away from INAI.

- Recorded the clinical-record **access log** and **break-glass operator
  access** as deliberately deferred, and deferred *together*
  ([todos](docs/technical/todos.md), amendment in
  [ADR 0023](docs/adr/0023-privacy-policy-and-custody-modes.md)).
  Break-glass built in the application alone would be theatre while an
  operator keeps a standing `psql` connection, so making `managed` true
  starts with infrastructure; and the access log is that mechanism's
  prerequisite, since an emergency session with no access log records
  nothing. Order when picked up: remove standing DB access → access log →
  break-glass sessions.

- **Modules declare where they send data**
  ([ADR 0027](docs/adr/0027-egress-is-declared-in-the-manifest.md)).
  `manifest.egress` names each external destination — its id, the
  subprocessor's legal name, the purpose, which `DataClass`es leave, and
  whether the module works without it — which finally gives
  `PrivacyPolicy.egress_allowed` something to compare against. Four
  destinations were declared: `openai` (copilot), `kapso`
  (whatsapp_kapso), `aeat` (verifactu) and `smtp` (notifications). That
  last one was the easiest to miss: reminders leave through whatever SMTP
  server the clinic configures, so the receiving party is configuration
  rather than a vendor named in code. `docs/subprocessors-catalog.md` —
  the register a clinic attaches to its DPA — is now **generated** from
  the manifests, and CI fails on drift. A boot audit names every module
  whose destination `TENANT_EGRESS_ALLOWED` does not permit, and a test
  fails when a module imports an HTTP or SMTP client without declaring.
  **Reported, not blocked**: enforcing a default-deny field nobody has
  had a release to fill in would unplug the copilot and stop reminders on
  every existing deployment.

- **Subject rights have an HTTP surface** at `/api/v1/privacy`
  ([ADR 0026](docs/adr/0026-subject-rights-are-a-module-contract.md)):
  export a patient's data, erase it, and read the log of exercised
  rights. Gated on three new core permissions
  (`privacy.subject.{read,export,erase}`) rather than on `patients.read`,
  because an export hands out every module's data on one patient in a
  single response and an erasure cannot be undone. Both require a stated
  reason, and both write a `core_subject_request` row (migration `0010`)
  recording who acted, when, why and what each section did — but **not
  what the data said**, so the record survives the erasure it documents.
  Without it, an erasure would be indistinguishable from a bug that
  emptied the columns. The export also reports, per section, whether an
  erasure would reach it and the retention reason when it would not, so a
  patient can see what cannot be removed without asking twice.

- **Every module that holds patient data now answers a subject request.**
  Coverage went from 3 modules to 16, 21 contributors in total, wired on
  the principle that decides each one: *identity is erased, the record is
  retained and thereby becomes pseudonymous*. Clinical modules (`agenda`,
  `odontogram`, `periodontogram`, `treatment_plan`, `clinical_notes`,
  `media`) and fiscal ones (`billing`, `payments`, `verifactu`) export and
  retain with a stated reason; outreach and working data (`recalls`,
  `notifications`, `patient_timeline`, `budget`, `migration_import`) are
  erased, free text included. `migration_import` was the easiest blind
  spot to miss — it keeps the source system's patient row verbatim in
  JSON, reachable only through the canonical-id mapping. A test now fails
  when a module contributes nothing and is not on an explicit
  silent-by-design list, and every contributor's queries are executed
  against a real patient so a broken parent/child chain cannot ship.
  `copilot` stays an honest gap: its transcripts hold patient names but
  its `context` blob has no shape to query. **The retention calls are a
  first pass, not settled law.**

- Classified `communication_messages.to_address` (the patient's email or
  phone) under a new `PiiKind.CONTACT`. The PII contract's name-based
  heuristic could not see it.

- **Subject rights are a module contract**
  ([ADR 0026](docs/adr/0026-subject-rights-are-a-module-contract.md)).
  `BaseModule.get_subject_contributors()` lets each module answer for its
  own data when a patient asks for a copy of their record or for it to be
  erased — core cannot, since ADR 0001 forbids it from importing module
  code. Export is unconditional; erasure is not: a contributor either
  supplies `anonymize` or states a `retention_reason`, and supplying
  neither raises at construction, so a module cannot stay silent about
  whether its data is erasable. `billing` is the case that shapes the
  design — an issued invoice is a fiscal document and declines erasure
  with a reason written for the patient. `anonymize_instance()` scrubs
  the columns ADR 0025 classified and skips `DataClass.FINANCIAL`, giving
  that field its first enforcer. Wired in `patients`,
  `patients_clinical` and `billing`; **the other 19 modules contribute
  nothing yet, and there is no HTTP surface** — see the ADR's trade-offs.

- **The deployment declares its own custody mode**
  (`TENANT_CUSTODY_MODE`, default `managed`; see *Amendment 1* of
  [ADR 0023](docs/adr/0023-privacy-policy-and-custody-modes.md)). The
  resolver previously hardcoded `self`, which meant the system asserted
  no operator could read data an operator was in fact reading. Two
  companion settings: `TENANT_JURISDICTIONS` (default `MX,ES`, which also
  widens the copilot's PHI boundary to Spanish document names) and
  `TENANT_DATA_RESIDENCY` (empty resolves to `on-prem` under `self`,
  `unspecified` otherwise — reporting `on-prem` for a hosted deployment
  would be a lie rather than a gap). An unrecognised mode refuses to
  start. **The modes state who holds what, not an enforced control:**
  `managed` names break-glass operator access and no such mechanism
  exists yet, `byok` is out of scope for this stage, and both log a
  warning naming the gap on every boot.

- **Imported patients could not be saved.** `PatientMapper` labels every
  identifier it imports from Gesdén `nif`, and the patients schema
  accepted only `curp`/`ine`/`passport`. The mapper writes to the model
  directly, so the bad value landed silently and surfaced later: the
  demographics edit modal loads `national_id_type` into its form and
  sends it back untouched, so the first save of any imported patient
  returned 422 until the user changed the dropdown by hand. The accepted
  set is now the union of both markets the deployment serves, grouped by
  jurisdiction (`NATIONAL_ID_TYPES_BY_JURISDICTION`), with the Spanish
  documents added to the edit form and both locales. Existing rows become
  valid without a data migration.

- **PII is classified on the column, and the classification is enforced**
  ([ADR 0025](docs/adr/0025-pii-is-classified-on-the-column.md)). A column
  holding personal data declares it —
  `mapped_column(..., info=pii(PiiKind.NATIONAL_ID))` — and the copilot's
  redactor derives its key map from those declarations instead of a list
  kept alongside it, which had drifted from the schema every time either
  side moved. `tests/test_pii_redaction_contract.py` fails when a
  personal-looking column carries neither a classification nor a reasoned
  allowlist entry, in the same shape as
  `test_event_transaction_boundary.py`. Writing that test found nine
  columns that were reaching the cloud model in cleartext:
  `invoices.billing_name`/`billing_tax_id`/`billing_email`,
  `budget_signatures.signed_by_name`/`signed_by_email`,
  `verifactu_settings.producer_nif`/`producer_name`,
  `verifactu_certificates.nif_titular` and
  `whatsapp_kapso_settings.display_phone_number`. The check imports every
  table-declaring file itself instead of reading `Base.metadata` as it
  finds it, so it sees all 92 model tables regardless of which tests ran
  first and ignores the synthetic tables other tests register there. The companion
  `DataClass` axis (identifier / clinical / financial / operational) is
  recorded now for the retention and subject-rights work; nothing reads
  it yet.

- **The copilot's PII redaction now follows the tenant's jurisdictions.**
  `Redactor.for_policy()` builds its key map from
  `PrivacyPolicy.jurisdictions` (ADR 0023) instead of a module-level
  constant, so an `ES` tenant tokenizes a NIE and an `MX` one a CURP. The
  field names this schema defines (`national_id`, `tax_id`,
  `billing_tax_id`, `dni`, `nif`) stay redacted under every jurisdiction.
  A redactor built without a policy falls back to every known
  jurisdiction — over-redacting rather than leaking — and an unmodelled
  country logs a warning instead of failing silently. The tenant reaches
  the request through a new `get_tenant` dependency, installed on
  `app.state` by the lifespan (the read half of ADR 0012 Fase 2a;
  `get_db` is untouched).

- **Jurisdiction wording aligned with the market.** Several Spanish
  strings still named Spanish documents over columns that hold Mexican
  ones: the `search_patients` tool description ("DNI/NIE"), the
  legal-guardian ID label, the patient billing tax-id label, and the
  clinic-info onboarding hint. They now name the documents the schema
  actually accepts (CURP / INE / passport, RFC). English strings were
  already jurisdiction-neutral and are untouched.

- **PHI redaction now covers Mexican identifiers.** The copilot's PII key
  denylist (`backend/app/core/agents/redaction.py`) carried Spanish
  document names only, so a CURP or an RFC named as such reached the cloud
  LLM in cleartext, and `Patient.billing_tax_id` was never tokenized at
  all. The keys are now split in two families: `_SCHEMA_ID_KEYS`
  (`national_id`, `tax_id`, `billing_tax_id`, `dni`, `nif` — field names
  this codebase actually uses, redacted unconditionally because the
  deployment serves both markets) and the per-jurisdiction document names,
  of which `_MEXICO_ID_KEYS` (`curp`, `rfc`, `ine`) is the active profile
  and `_SPAIN_ID_KEYS` is declared for when the selection becomes
  geography-driven.

- Removed the public `POST /api/v1/auth/register` endpoint. It created
  orphan users with no clinic membership (unusable, and unused by the UI);
  the first-run setup assistant replaces it.

- Alembic history squashed. The 29-migration main-linear chain
  inherited from Fase A collapsed into one `0001_core_initial` for
  core tables + 11 module-owned initials under
  `backend/app/modules/<name>/migrations/versions/<mod>_0001_initial.py`.
  Each module's initial lives in its own package so community module
  authors can pattern-match their own migrations on the official
  examples. Cross-module FKs live on the "late" side — the only
  circular dep (`appointment_treatments.planned_treatment_item_id`
  → `planned_treatment_items`) is created in `tp_0001` after both
  tables exist. Round-trip `upgrade head → downgrade base → upgrade
  head` is clean and `test_alembic_roundtrip` no longer xfails.

## [2.0.0] - 2026-04-21

First release on the post-Fase-B module architecture. Covers the
full Fase B refactor (B.1 → B.6), the hardening pass (B.7), and the
Playwright E2E smoke suite (B.8). `main` is stable against the
12-module layout; the `clinical` module is gone.

### Added

- **Module `patients`** (`auto_install: True, removable: False`) —
  Patient identity, demographics, billing info. Endpoints under
  `/api/v1/patients/*`. Permissions under `patients.*`.
- **Module `patients_clinical`** (`auto_install: True, removable: True`)
  — normalized medical history with 7 tables
  (`patients_clinical_medical_context`, `_allergy`, `_medication`,
  `_systemic_disease`, `_surgical_history`, `_emergency_contact`,
  `_legal_guardian`). Endpoints under `/api/v1/patients_clinical/*`.
  Alerts (`/alerts`) now derive from real rows — actual SQL analytics
  over allergies / diseases is possible.
- **Module `agenda`** (`auto_install: True, removable: True`) —
  Appointment, AppointmentTreatment, Cabinet. Cabinets promoted from
  the `clinic.cabinets` JSONB to a real table with FK
  (`appointments.cabinet_id`). Endpoints under `/api/v1/agenda/*`.
- **Module `patient_timeline`** (`auto_install: True, removable: True`)
  — cross-module audit log, populated via event subscriptions.
  Endpoints under `/api/v1/patient_timeline/*`.
- Clinic metadata endpoints moved into core auth:
  `GET/PUT /api/v1/auth/clinics`.
- Nuxt layer support for every official module. Each module now ships
  `<module>/frontend/{pages,components,composables,i18n}` and is
  auto-discovered at boot via `modules.json`.
- New pytest marker `alembic_roundtrip` for the full
  `base → head → base → head` migration-chain check; excluded from
  the default pytest run, executed as a dedicated CI step.
- CI pipeline gains `manifest-consistency` and `frontend-typecheck`
  jobs (Nuxt `prepare` pass that catches broken Vue/TS imports across
  module layers).
- Playwright browser E2E suite under `frontend/tests/e2e/` — 16
  smoke tests covering admin navigation across every module layer,
  patient detail rendering, and per-role sidebar visibility. CI `e2e`
  job boots docker-compose + seeds demo + runs Playwright.
  `./scripts/e2e.sh` wrapper for local runs.

### Changed

- **Breaking — API paths**
  - `GET /api/v1/clinical/patients/*` → `GET /api/v1/patients/*`
  - `.../medical-history`, `.../alerts`, `.../emergency-contact`,
    `.../legal-guardian` → `/api/v1/patients_clinical/patients/{id}/...`
  - `GET /api/v1/clinical/appointments/*` → `/api/v1/agenda/appointments/*`
  - `GET /api/v1/clinical/clinics/*` → `/api/v1/auth/clinics/*`
  - Patient timeline read at `/api/v1/patient_timeline/patients/{id}`
- **Breaking — permissions**
  - `clinical.patients.*` → `patients.*`
  - `clinical.patients.medical.*` → `patients_clinical.medical.*`
  - `clinical.patients.emergency.*` → `patients_clinical.emergency.*`
  - `clinical.appointments.*` → `agenda.appointments.*`
  - `clinical.appointments.cabinets.*` → `agenda.cabinets.*`
- Every official module manifest's `depends` rewritten against the
  real modules (patients / agenda / catalog / budget) instead of the
  now-removed `clinical`.
- `Patient.active_alerts` property removed (alerts compute via
  `PatientsClinicalService.compute_alerts`).
- Dashboard + Settings sidebar entries are host-owned (see
  `frontend/app/utils/moduleRegistry.ts::HOST_NAV`); modules no
  longer publish `/` or `/settings`.
- Auth rate limiter only activates in `ENVIRONMENT=production`.
  Dev + test runs were tripping the 5/min `/login` cap during manual
  reloads and Playwright runs; production semantics unchanged.

### Removed

- **Breaking — module `clinical`** — fully deleted. All downstream
  depends point at the real owning modules.
- `patients.medical_history`, `patients.emergency_contact`,
  `patients.legal_guardian` JSONB columns dropped — data migrated to
  the normalized `patients_clinical_*` tables in
  `w3x4y5z6a7b8_add_patients_clinical_tables.py`.
- `clinic.cabinets` JSONB column dropped — replaced by the `cabinets`
  table in `v2w3x4y5z6a7_add_cabinets_table.py`.

### Frontend layer conventions

- Each layer's `nuxt.config.ts` must register
  `components: [{path: './components', pathPrefix: false}]`; the host
  overrides Nuxt's default auto-scan so this is load-bearing.
- Cross-layer type imports use `~~/app/types` (rootDir-relative, = host
  frontend) instead of `~/types` (srcDir-relative, which would scope
  to the current layer).

### Known gaps (deferred)

- Alembic chain still lives as a single main-linear list. The squash
  that breaks it into per-module branches (one clean initial per
  module) is deferred; `test_alembic_roundtrip` is `xfail` until
  then and exists purely to hold the infrastructure in place.
- Docs (`docs/diagrams/*`, `CLAUDE.md` examples) still reference the
  old `/api/v1/clinical/*` paths in a handful of illustrative spots;
  the primary `docs/technical/creating-modules.md` and `docs/technical/core-api.md` are
  up to date.
