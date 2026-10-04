# Commitments register — what was promised, and where each promise stands

> Status: living document. Last verified against the working tree: 2026-10-03
> (commitments 2, 4, 8, 14, 15, 17, 18, 19, 20 and 21; the rest as of 2026-09-30).
>
> This is the single place where a stated commitment is tracked against
> the codebase. It does not replace the specs and ADRs it links to — it
> exists so that "what did we promise, and how much of it is real?" has
> one honest answer instead of nine scattered ones.
>
> `docs/technical/todos.md` remains the broader product roadmap. This
> register covers only commitments that were stated explicitly, and it
> wins over `todos.md` where the two disagree about status.

## Status vocabulary

| Term | Meaning |
|---|---|
| **Done** | Shipped and verifiable on `main` |
| **Partial** | Some of it shipped; the remainder is named below |
| **Decided, not built** | The rule or design is settled in an ADR; no implementation |
| **Not started** | Understood and scoped, nothing built |
| **Undefined** | Named as a commitment, scope not yet decided |

## Summary

| # | Commitment | Status |
|---|---|---|
| 1 | Electronic clinical record (*expediente clínico electrónico*) | **Partial** |
| 2 | NOM-004-SSA3-2012 | **Partial** |
| 3 | ASA classification on the patient profile | **Not started** |
| 4 | Medical record per Ley General de Salud Art. 51 Bis 1 | **Partial** — informed consent letters exist; nothing requires one |
| 5 | Catalogue generation for all specialties | **Partial** — 10 of 17 |
| 6 | Periodontogram integrated with Periodontics | **Partial** — API only |
| 7 | Settings menu working on tablet | **Not started** (unverified) |
| 8 | Agenda ↔ Google Calendar sync | **Not started** |
| 9 | Platform-owner control panel | **Decided, not built** |
| 10 | Inventory control | **Undefined** |
| 11 | Per-dentist productivity dashboard | **Partial** — data on four axes, no view |
| 12 | Accounting / accountant connects to the system | **Partial** — file export only |
| 13 | Laboratories (prosthetics, radiology, tomography) | **Not started** |
| 14 | SAT-compliant invoicing (CFDI) | **Not started** |
| 15 | Module separation + per-tenant module selection | **Partial** — Apps catalog and core Apps decoupled; selection is per deployment, not per tenant |
| 16 | RBAC granularity: per module *and* per view | **Partial** — per module yes, per view no |
| 17 | Customisable widgets — home and Informes | **Partial** — the clinic arranges the home page; Informes and per-user not |
| 18 | Recalls and reminders over WhatsApp (Communications App) | **Not started** — declared, nothing sends |
| 19 | Classify the optional Apps | **Undefined** |
| 20 | Apps switched on and off by the user, taking effect at once | **Not started** — today a file edit and a restart |
| 21 | Consent to the use of personal data, and the privacy notice | **Partial** — the letter and its versioned text exist; nothing requires it |

---

## 1. Electronic clinical record — **Partial**

Spec: [`../features/expediente-clinico.md`](../features/expediente-clinico.md).
Decisions: [ADR 0032](../adr/0032-clinical-record-is-append-only.md),
[ADR 0033](../adr/0033-disclosure-requires-a-recorded-authorisation.md).

**Done.** Phase 0 — the part that turns stored data into a *record*:
`patients_clinical` stopped hard-deleting (`pc_0002`), amendments append
instead of overwriting in `clinical_notes` (`cn_0005`), and clinical
entries carry an authoring professional (`pro_0003`, `pc_0003`,
`cn_0006`). Both migrations are covered against seeded rows by
`backend/tests/test_clinical_record_migrations_with_rows.py`.

**Remaining.** Emergency contacts and legal guardians are still 1:1 rows
and still deleted; the contract test that keeps `db.delete()` out of
clinical tables is not written; and phases 3–4 (coding, interchange)
have not started.

**Composition (phase 1) is done as of 2026-10-03.** The `record` module
composes thirteen sections from eight modules — identification,
antecedents and medical context, dental chart, periodontal chartings,
evolution notes, plans and prescriptions, imaging, consents — and the
patient record has an *Expediente* tab that reads them in order.

**Disclosure (phase 2) is partly done as of 2026-10-03.** The record can
be printed or handed over, and only by recording to whom, why, on what
evidence and with which sections; the PDF is kept as it left, with its
digest, and the disclosure is an entry of the record (ADR 0033, now
accepted). Still to build: authorisations as structured, time-boxed,
revocable records (the evidence is free text today), the guardian as
authoriser, digest chaining, and remote delivery. The blocking open question is who
supplies clinical authorship when the acting account has no professional
profile — the column exists, nothing asks for it.

Full detail lives in the spec under *Phase 0, where it actually stands*.

## 2. NOM-004-SSA3-2012 — **Partial**

Coverage table: [`../features/expediente-clinico.md`](../features/expediente-clinico.md) §9.

**Done.** The norm's *custody* requirements are largely met and were the
target of phase 0: entries are attributed to a named professional,
corrections are annotated rather than erased, and retention is expressed
through the existing `retention_reason` contract.

**Remaining.** The *content* requirements split cleanly: everything a
dental practice records natively is present (identification, personal
pathological history, therapeutic indication, evolution notes);
of what a general medical history carries, family history and prognosis
were added on 2026-10-03; the systems review and laboratory results are
out of scope by decision.

**Informed consent is no longer missing** (2026-10-03): the `consents`
module of the Clinical record App holds the *cartas de consentimiento
informado* — written from the clinic's templates, naming the professional
who explained, signed on screen, revoked rather than deleted, and part of
the composed record ([ADR 0045](../adr/0045-a-consent-is-a-record-entry.md)).

**Scope decided, 2026-10-03:** the product answers NOM-004 for the
*dental* record, plus family history and prognosis. The systems review and
laboratory results of a general *expediente* are out.

**Built, 2026-10-03:** family history (in the medical history form),
prognosis (on the treatment plan, editable there), the health
questionnaire with its chief complaint, vital signs on evolution notes,
and a per-patient check — ten requirements, shown at the top of the *Expediente* tab — of what the
record holds and lacks.

**Still open.**

- The check is an engineering reading of the norm, and one of presence
  only. It needs legal review before a clinic relies on it.
- "No family history" cannot be recorded as an answer, so a patient with
  none reads the same as one nobody asked.
- The health questionnaire is one fixed form (12 questions, 67
  conditions); a clinic cannot change it. Filled in on paper, its answers
  stay on the scan — they are not transcribed.
- A questionnaire and the curated medical history are separate: an allergy
  the patient declares is not added to their allergies.
- The patient's signature when a treatment changes is not captured as
  such; a new consent letter is the way to record it.

## 3. ASA classification on the patient profile — **Not started**

Design: [`../features/expediente-clinico.md`](../features/expediente-clinico.md) §2,
*ASA physical status is an assessment, not a profile field*.

Nothing exists: no column, no enum, no reference anywhere in the
codebase. The inputs a clinician weighs are already recorded in
`patients_clinical_medical_context` — pregnancy, anticoagulants with INR,
smoking, alcohol, prior adverse reactions to anaesthesia — so what is
missing is the conclusion, not the evidence for it.

The design point that matters is recorded in the spec: an ASA class is a
dated, attributed clinical judgement, so it is an appended entry under
[ADR 0032](../adr/0032-clinical-record-is-append-only.md), never a
mutable field on the profile. Two decisions are open — who may assess,
and whether class III+ raises an alert on the same surface as allergies.

## 4. Medical record per Ley General de Salud Art. 51 Bis 1 — **Partial**

Analysis: [`../features/expediente-clinico.md`](../features/expediente-clinico.md) §5,
*Two consents, not one*. Decision: [ADR 0045](../adr/0045-a-consent-is-a-record-entry.md).

Art. 51 Bis 1 concerns the patient's right to sufficient, clear, timely
and truthful information about their condition and about the risks and
alternatives of the procedures indicated for them. It is an obligation on
the **clinical act**, distinct from the data-protection consent of
commitment 21.

**Done (2026-10-03).** The `consents` module (Clinical record App) records
the act: a letter of kind `informed`, written from the clinic's template
for a procedure, that cannot be signed without naming the professional
who explained it, captures the patient's (or guardian's) signature on
screen, and records a refusal as a fact too. Signed letters are never
edited or deleted — only revoked — and appear in the composed record.

**Remaining.**

- **Nothing requires it.** A treatment can be planned and performed with
  no consent on file; the screen does not say that one is missing.
- **The wording is not supplied.** What a letter must say per procedure is
  the clinic's, and needs clinical and legal authorship.
- **Remote signing** (expiring link with second factor, as budgets have)
  is not built. A letter can be printed, signed by hand and filed as a
  scan; the printed sheet carries the lines of NOM-004 §10.1.1 (who
  informs, who accepts, two witnesses, place and date) — an engineering
  reading, pending legal review.
- **Guardians** are typed in as the signer; they are not read from
  `patients_clinical_legal_guardian`.
- The reading of the article is an engineering one, pending legal review.

`budget_signatures` remains what it was: evidence that a price was
accepted, never a substitute.

## 5. Catalogue generation for all specialties — **Partial (10 of 17)**

**Done.** Seventeen specialties are recognised, with a suggestions
endpoint offering the ones a clinic has not yet added, specialty
management and inline price editing in the catalogue screen (shipped
2026-09-25), and a specialty↔treatment mapping on `catalog_item_specialties`.

**The measured state**, counted in the seeded database rather than from
source:

| Seeded with a catalogue (10) | Treatments |
|---|---|
| `general` | 47 |
| `rehabilitacion` | 28 |
| `cirugia` | 21 |
| `implantologia` | 16 |
| `periodoncia` | 16 |
| `ortodoncia` | 15 |
| `endodoncia` | 11 |
| `odontopediatria` | 11 |
| `estetica` | 10 |
| `higiene` | 9 |

**Remaining (7).** `radiologia`, `patologia_oral`, `medicina_oral`,
`dolor_orofacial`, `odontologia_sueno`, `protesis_laboratorio` and
`odontogeriatria` exist as *suggestions* a clinic can add, with **no
treatments behind them**. A clinic adding one today gets an empty
specialty, which is worse than not offering it — the promise is only kept
when a suggestion arrives with a catalogue.

Note that a clinic seeded before a catalogue grows does not receive the
new entries: seeding bails on existing databases, so new baseline data
needs a backfill script.

## 6. Periodontogram integrated with Periodontics — **Partial (API only)**

Module: `backend/app/modules/periodontogram/`.
Design: [ADR 0013](../adr/0013-periodontogram-snapshot-model.md),
[`periodontogram-plan.md`](periodontogram-plan.md).

**Done.** The backend is real: ten endpoints on the router, SEPA-standard
charting with dated immutable snapshots, six probing sites per tooth, and
computed BoP/PI/CAL indices. It pre-fills tooth presence from the
odontogram at draft creation.

**Remaining**, and this is the whole gap between "a module exists" and
"Periodontics is supported":

- **No frontend.** `periodontogram/frontend/` ships no pages. A charting
  surface that a periodontist cannot open is not usable by one, and
  charting six sites per tooth is the most input-dense screen in the
  product — it is a chairside tablet surface, so it lands squarely on
  [ADR 0022](../adr/0022-touch-adaptation-is-capability-driven.md).
- **No link to the specialty.** The `periodoncia` specialty carries 16
  catalogue treatments and the periodontogram module knows nothing about
  it; nothing connects a charted diagnosis to the treatments that answer
  it, or routes the chart to professionals of that specialty.
- The module's `CLAUDE.md` still says "PR-1 ships an empty router;
  endpoints land in PR-2", which stopped being true — stale, worth a
  correction pass.

## 7. Settings menu working on tablet — **Not started (unverified)**

Rule: [ADR 0022](../adr/0022-touch-adaptation-is-capability-driven.md).

The global baseline does apply — `main.css` enforces the 44 px minimum
under `(pointer: coarse)` for every surface, settings included — so the
floor is not zero. What is missing is any evidence that the settings
screens actually work at tablet size: `frontend/tests/e2e/tablet-touch.spec.ts`
covers plans, appointments, finance and the cashbox, and mentions
settings **zero times**.

Until a settings route is asserted there, the honest status is "untested,
therefore unknown", not "works". The root `CLAUDE.md` checklist already
requires adding routes that matter on tablet to that spec; this is that
requirement, unmet.

## 8. Agenda ↔ Google Calendar sync — **Not started**

Declared and nothing more: `backend/apps.json` lists `google_calendar` as
a `planned` API of the Agenda App, and Settings → Apps → APIs shows it as
"Próximamente" ([ADR 0040](../adr/0040-widgets-are-read-from-the-registry-apis-are-declared-in-apps-json.md)).
There is no integration and no adapter. Credentials will never live in
that file.

Two constraints that must shape the design rather than be discovered
during it:

1. **It is egress carrying clinical data.** Under
   [ADR 0027](../adr/0027-egress-is-declared-in-the-manifest.md) the
   module declares Google as a `subprocessor`, with a purpose a clinic
   can show a patient. An appointment title carrying a patient name makes
   Google a processor of identifiable health-adjacent data. The
   defensible default is to sync **busy blocks without patient
   identity**, with identity as an explicit opt-in the clinic makes
   knowingly — not the reverse.
2. **It conflicts with the premium tier's promise.** Under
   `CustodyMode.SELF` ([ADR 0028](../adr/0028-self-hosting-is-the-premium-tier.md))
   the clinic is paying precisely so that no third party sits in the
   path. A sync that silently reintroduces one contradicts what was sold.
   Behaviour per custody mode is a decision to make before building.

The channel-adapter architecture ([ADR 0016](../adr/0016-channel-adapter-architecture.md))
is the shape to copy: a declared adapter behind a stable interface.

## 9. Platform-owner control panel — **Decided, not built**

Decision: [ADR 0024](../adr/0024-control-plane-holds-what-constrains-the-customer.md) (accepted).
Commercial shape: [`../features/licensing-and-packaging.md`](../features/licensing-and-packaging.md).

**Done.** The hard part is settled on paper: what belongs in the control
plane versus the tenant database, and why a fact that constrains the
customer cannot live in a database the customer controls.

**Remaining: all of it.** There is no `control_plane` package, no
implementation of licence keys or tenant records — the grep returns
nothing. The ADR is a rule waiting for a product.

Scope is **undefined** and worth settling before building: tenant
provisioning, licence issuance and revocation, custody-mode
administration, subscription state, cross-tenant operational visibility,
and break-glass session management are all candidates, and they are not
one screen.

## 10. Inventory control — **Undefined**

Nothing exists and the scope has not been decided.

Before it becomes a backlog item, three questions determine whether it is
one module or three: whether it tracks *consumables* (gloves, anaesthetic
— which mostly wants purchasing and stock levels), *implantable or
traceable materials* (implants and lots — which is a clinical traceability
requirement with a patient link and a regulatory flavour entirely unlike
stock control), or *lab work in flight* (prostheses out at a laboratory —
which is workflow, not inventory).

The middle one is the only one that touches the clinical record: an
implant placed in a patient is part of that patient's record, with its lot
and manufacturer, and if it is ever recalled the clinic must find every
patient carrying it. If inventory is built to cover that case it is a
clinical module with a `RecordSection`; if it is built for consumables it
is an operations module that never touches a patient. Deciding which
comes first is the actual open question.

## 11. Per-dentist productivity dashboard — **Partial**

This one is further along than it looks: **the data exists on four axes
and the view does not.**

| Axis | Where it already is |
|---|---|
| Invoiced per professional | `GET /api/v1/reports/billing/by-professional` |
| Quoted per professional | `GET /api/v1/reports/budgets/by-professional` |
| Schedule and occupancy | `GET /api/v1/reports/scheduling/by-professional`, plus punctuality, duration-variance, funnel and waiting-times |
| Produced and collected | `liquidations` — `earned` from `PatientEarnedEntry.professional_id`, `collected` via `LedgerService.coverage_by_earned_entry` |

**Remaining.** `reports` ships four frontend pages (index, billing,
budgets, scheduling) and **none of them is per-professional**;
`liquidations` ships eight endpoints and **no frontend at all**. So the
work is mostly composition, not computation — after two decisions that
have to be made first, because getting them wrong makes the dashboard
worse than nothing.

1. **Which number is "productivity".** `liquidations` already documents
   that *earned* and *collected* are different numbers that can be months
   apart on a large case, and that neither can be judged without the
   other. A dashboard showing one of them alone will be argued with by
   the person it measures, and they will be right. Show both, as
   liquidations already decided to.
2. **It crosses the off-books boundary on purpose.** `accounting_export`
   deliberately never juxtaposes the collection axis against the invoice
   axis (ADR 0010 and its own *Off-books boundary* section). A
   productivity view that puts `earned` next to `billed` recreates
   exactly that juxtaposition. That is defensible for internal
   management and unsafe the moment it is exported or handed to the
   accountant — so the boundary must be a stated property of the screen,
   not an accident of who opens it.

A third, smaller decision: this measures people. Whether a dentist sees a
colleague's numbers is an RBAC question with no current answer. **TBD.**

## 12. Accounting — the accountant connects to the system — **Partial**

**Done.** `accounting_export` exists: `/preview` and `/run` produce a ZIP
with `facturas.csv` + `cobros.csv` for a period, with an Excel-ES
separator option. It is model-free, reads billing only through
`InvoiceService.list_for_export`, and holds a deliberate invoice-centric
boundary — the raw `Payment` ledger is never surfaced and drafts are
excluded.

**The gap is precisely the promise.** Today the *clinic* exports a file
and sends it to the gestoría. "An accountant connects to the system" is a
different thing, and it changes three properties rather than adding a
screen:

- **A role that does not exist.** The export is admin-only today. Every
  role in the system is a clinical-staff role; an external accountant
  needs to read fiscal data and *nothing clinical*, which is a shape
  `ROLE_PERMISSIONS` has never had to express.
- **A design discipline becomes an access-control boundary.** The
  off-books separation currently holds because one module's author kept
  it. With an outside user reading through an API it has to hold at a
  chokepoint ([ADR 0029](../adr/0029-security-invariants-with-chokepoints.md)),
  enforced rather than observed.
- **A third category of party.** Under
  [ADR 0023](../adr/0023-privacy-policy-and-custody-modes.md) and
  [ADR 0027](../adr/0027-egress-is-declared-in-the-manifest.md) an
  accountant is neither clinic staff nor a subprocessor. Which one they
  are contractually determines what they may hold.

**Undefined:** whether this is a scoped role, a token-scoped API, or a
connector to the accounting software the market actually uses (Contpaqi,
Aspel, Alegra in Mexico). Those are three different products.

## 13. Laboratories — prosthetics, radiology, tomography — **Not started**

Nothing exists as a workflow. Three fragments touch it: `cashbox` has a
`lab` expense category ("pagado al mensajero del laboratorio") — so the
money leaving is tracked while the work is not; `protesis_laboratorio` is
one of the seven suggested specialties with no catalogue behind it (§5);
and `professionals` has a `collaborator` type that could hold a lab as a
directory entry.

`docs/technical/todos.md` anticipates `lab-orders`, `lab-tracking`,
`digital-impressions` and `shade-management` — but as **third-party**
opportunities, for labs to build. Restating them as a commitment moves
them first-party, which is a change of ownership worth making
deliberately rather than by drift.

**The design point that has to be settled first: this promise bundles two
workflows that share only the phrase "send out, get back".**

| | Prosthetic lab work | Imaging referral |
|---|---|---|
| What leaves | An impression or a scan | The patient |
| What returns | A physical object | A file (DICOM/JPEG) |
| Attaches to | A plan item and a tooth | The record's imaging section |
| Needs | Stages, shade, try-ins, due date, remakes | Acquisition date, study type, report |
| Fails by | Arriving late or wrong | Not arriving, or not being readable |

Modelling them as one entity produces a table where half the columns are
always null. They are two modules, or one module with two genuinely
separate case types.

Two further notes. **"Internal or external" is an egress question**: an
in-house lab moves nothing outside, while an external one that receives
files electronically is a declared subprocessor under
[ADR 0027](../adr/0027-egress-is-declared-in-the-manifest.md) carrying
clinical data. And the **returned object connects to commitment 10**: an
implant or prosthesis that comes back with a lot and manufacturer belongs
in the patient's record, which is the traceability case inventory would
have to cover anyway.

## 14. SAT-compliant invoicing (CFDI) — **Not started**

**Product decision, 2026-10-03:** SAT invoicing is to *replace* Veri*Factu
in the product. `verifactu` sits in the Budgets & payments App for now
(not installed by default) and is the shape to copy, not the base.

**What is already in place** is the jurisdiction-neutral plumbing, and it
is genuinely MX-ready: `clinics.tax_id` is documented as "RFC in Mexico,
CIF/NIF in Spain", and both `patients.billing_tax_id` and the invoice's
own `billing_tax_id` carry the same neutrality. The default currency is
already MXN.

**What is missing is everything CFDI-specific**: régimen fiscal for
issuer and receiver, uso del CFDI, the SAT catalogues for forma and
método de pago and for clave de producto/servicio, XML 4.0 generation,
**timbrado through a PAC**, the cancellation flow with its acceptance
step, and complemento de pago — which is not optional here, because the
product already supports partial payments.

Three structural notes:

- **`verifactu` is the shape, not the base.** It proves the pattern for a
  country compliance module — hash chain, QR, submission, rejection
  alerts — but it is Spain-specific (AEAT, RD 1007/2023). CFDI is a
  sibling module, not an extension. And as `migration_import` already
  does, code that cares should detect the installed fiscal module at
  runtime rather than depend on it; two fiscal modules must never both be
  authoritative for one invoice.
- **The PAC is a subprocessor** carrying fiscal and identifying data, so
  it is declared under [ADR 0027](../adr/0027-egress-is-declared-in-the-manifest.md).
  Under `SELF` custody the clinic contracts its own PAC, which changes
  who holds that relationship.
- **The roadmap had Mexico missing.** `docs/technical/todos.md` listed
  compliance modules for Spain, France, Italy and Slovenia while the
  product defaults to MXN. Corrected there; this register is the status
  of record.

## 15. Module separation and per-tenant selection — **Partial**

**Done.** The module system is enforced ([ADR 0018](../adr/0018-install-state-is-the-mount-authority.md)):
`core_module.state` decides what runs. On top of it, since October 2026,
the product is organised as **Apps**:

- Switching off is `disable`, never `uninstall`: tables and data stay, the
  schema is complete in every database ([ADR 0035](../adr/0035-apps-are-disabled-not-uninstalled.md)).
  *Configuración → Apps* is read-only.
- `backend/apps.json` is the catalog: one **base** App (the workspace,
  never disabled), four **core** Apps (Agenda, Patients, Recalls,
  Treatments) and eight **optional** ones. Every module belongs to exactly
  one App ([ADR 0036](../adr/0036-an-app-is-a-declared-group-of-modules.md),
  [0038](../adr/0038-apps-json-switches-apps-for-the-whole-deployment.md),
  [0043](../adr/0043-the-workspace-is-the-base-app.md);
  generated list in [`../apps-catalog.md`](../apps-catalog.md)).
- The core Apps are separable in fact, not only on paper: Agenda and
  Patients import no other App, Treatments only Patients. What they need
  from others they ask of a core contract or hear in an event
  ([ADR 0037](../adr/0037-a-module-integrates-with-what-it-can-live-without.md),
  [0039](../adr/0039-modules-reach-each-other-through-core-contracts.md),
  [0042](../adr/0042-core-apps-must-stay-separable.md)). Verified by
  switching each off in a running instance and by
  `backend/tests/test_app_isolation.py`, which pins what every App may
  import and require.

**Remaining.**

- **Selection is per deployment, not per tenant.** `apps.json` switches an
  App for every clinic of the installation. Per-tenant selection at
  provisioning is still blocked on commitment 9 (the control plane that
  would hold the choice).
- **The optional Apps are not decoupled.** Budgets & payments, Cash desk,
  Communications, Reports and Data migration require other Apps
  (`test_app_isolation.py` records exactly which); switching one off has
  not been verified as a whole. Known cases are listed in
  `docs/technical/todos.md` (§7, Apps).
- **Their classification is open** — commitment 19.
- **`removable` flags were not audited.** The earlier finding stands: for
  several modules the flag says "untested", not "impossible". It matters
  less now that an App is disabled rather than uninstalled.

## 16. RBAC granularity — per module and per view — **Partial**

**Done: per module.** Permissions are namespaced `module.resource.action`
([ADR 0005](../adr/0005-relative-permissions.md)), merged at runtime from
each manifest's `role_permissions`, and navigation is filtered by them —
so a module the role cannot use does not appear in the menu. Slot entries
also carry an optional `permission`, so an injected component can be
gated individually.

**Missing: per view.** Pages carry `auth` middleware and, in the module
layers checked, no permission gate — the backend refuses, the UI does
not. The visible consequence is that a user can navigate to a screen and
watch it fail, instead of never being offered it.

**Undefined, and worth settling before building:** what a "view" is. The
codebase already has three candidate grains, and they are not the same
decision.

| Grain | Gated today? |
|---|---|
| Route / page | **No** |
| Tab or section inside a page | Only where a slot entry carries a `permission` |
| Individual widget | Same — slot-level, inconsistent |

A route-level gate is cheap and coarse. A tab-level gate matches how this
product is actually shaped, since so much lives behind tabs on detail
pages. Widget-level already half-exists. Picking one as the primary grain
— and saying what the others inherit — is the design decision; doing all
three ad hoc is how permission strings end up hardcoded in components,
which the audit already found 26 of.

## 17. Customisable widgets — home and Informes — **Partial**

**Done — the home page, per clinic.**

- *Configuración → Apps → Espacio de trabajo* has an **Inicio** section
  where an administrator hides or shows each home widget and reorders it
  within its area of the page. One layout per clinic
  (`clinic.settings.home_layout`), read by every member's home page
  ([ADR 0043](../adr/0043-the-workspace-is-the-base-app.md)).
- A widget added by a newly enabled App appears on its own instead of
  staying hidden.
- *Configuración → Apps → Widgets* is the catalog: every widget grouped by
  App, with a title, a description, where it appears and a live example
  fed made-up data ([ADR 0040](../adr/0040-widgets-are-read-from-the-registry-apis-are-declared-in-apps-json.md)).
  A slot entry now carries a title and description, the first step of the
  richer contract named below.

**Missing.**

1. **Per-user or per-role layout.** The layout is per clinic. Whether it
   should also vary by user or by role is still **TBD**.
2. **The rest of the widget contract.** No size or span, no refresh
   policy, no moving a widget to another area of the page.
3. **Informes.** `reports.dashboard.widgets` exists as a canvas and has no
   arranging. Nothing was done there.
4. **The classification itself.** *Pending discussion — to be classified
   jointly*: which widgets exist, what each is for and who should see it
   by default. Agenda (5) and Patients (4) are listed; Recalls and Reports
   contribute home panels that are named but not catalogued.

**Financial indicators carry a boundary the other widgets do not.** The
*Informes* widgets draw on the same material as commitments 11 and 12,
so the off-books separation applies here too: a widget placing produced
revenue next to invoiced revenue is the juxtaposition `accounting_export`
deliberately avoids. On a shared home screen it also becomes a
who-sees-whose-numbers question, which is commitment 16's problem — the
two are linked and should be decided together.

**Documentation drift worth a pass:** the canonical slot list in
`useModuleSlots.ts` names five slots "v1", while the codebase registers
into at least `dashboard.hero`, `dashboard.timeline`,
`dashboard.attention`, `finance.summary`, `finance.tabs`,
`patient.summary.cards`, `patient.summary.feed`, `app.overlays` and more.
The registry outgrew its own comment.

## 18. Recalls and reminders over WhatsApp — **Not started**

Stated 2026-10-03. The pieces that exist:

- The **Communications App** (`notifications` + `whatsapp_kapso`,
  optional) declares `whatsapp` as a `planned` API in `backend/apps.json`.
- `whatsapp_kapso` already delivers WhatsApp for `notifications` through
  Kapso (Meta Cloud API) and declares that egress; it is not installed by
  default and needs the clinic's Kapso credentials.
- **Recalls sends nothing.** It is a call list; "WhatsApp" there is only
  the channel reception logs by hand.

What the commitment needs:

1. The API switched on: the module installed and its credentials set — in
   the clinic settings or the environment, never in `apps.json`.
2. Recalls publishing an event when a recall falls due, and Communications
   reacting by sending — Recalls `integrates` Communications and never
   `depends` on it, so it stays a core App with a phone list when
   Communications or WhatsApp is off
   ([ADR 0037](../adr/0037-a-module-integrates-with-what-it-can-live-without.md),
   [ADR 0042](../adr/0042-core-apps-must-stay-separable.md)).
3. Message templates approved by Meta: WhatsApp does not allow a free-text
   first message to a patient.
4. The patient's "do not contact" flag honoured, and the send logged as a
   contact attempt.

The same channel would serve Agenda reminders and budgets, which is why
it sits in Communications and not in Recalls.

## 19. Classify the optional Apps — **Undefined**

Stated 2026-10-03. Every App that is neither the base nor one of the four
core Apps is `optional` for now, and the screen labels it "App opcional":
Budgets & payments, Cash desk, Communications, Professionals, Clinical
record, Reports, AI and Data migration.

Open: what the tiers beyond core are, and which App goes where. One case
is already known — **Professionals is meant to be core for workspaces of
the Clinic kind**, which the catalog cannot express yet (a tier that
depends on the kind of workspace).

## 20. Apps switched by the user, taking effect at once — **Not started**

Stated 2026-10-03: when a user can enable or disable an App by hand, the
change must show immediately — no restart.

**Today it is the opposite, by design.** An App is switched in
`backend/apps.json`, a file read once at boot
([ADR 0038](../adr/0038-apps-json-switches-apps-for-the-whole-deployment.md)):
routes, event handlers, agent tools, scheduled jobs and permissions are
mounted then and stay until the process restarts. *Configuración → Apps*
is read-only. Development softens it — the server restarts itself when
the file changes, and the screen flags an edit that is waiting — but
neither is "at once" for a user.

What the commitment needs:

1. **The switch moves out of the file**, into state the product can write:
   per clinic, which is also what per-tenant selection needs
   (commitment 15). `apps.json` stays as the catalog of what exists and
   its tier.
2. **Mounting becomes a check per request, not a decision at boot.** Every
   App's routes, handlers, tools and jobs are mounted always, and each
   asks "is this App on for this clinic?" when it runs. That is the real
   work: today "not mounted" is what makes a disabled App's API answer 404
   and its permissions disappear.
3. **The frontend re-reads what is active** after a switch — menu, route
   guard, slots and widgets already follow that list, so they would follow
   a change to it.
4. **Rules the switch must respect:** the base App is never offered; an
   App others require cannot be switched off while they are on; and
   whether core Apps can be switched off by a user at all is a product
   decision still to make.

The promise that makes this safe is already kept: a disabled App loses no
data and nothing else breaks ([ADR 0035](../adr/0035-apps-are-disabled-not-uninstalled.md),
[ADR 0037](../adr/0037-a-module-integrates-with-what-it-can-live-without.md)).

## 21. Consent to the use of personal data, and the privacy notice — **Partial**

Stated 2026-10-03. Health data is sensitive personal data; the
data-protection regime expects the patient's consent to its processing,
against a privacy notice with prescribed contents. Until now this lived
only in `docs/technical/todos.md` (LFPDPPP), with nothing built.

**Done.** The `consents` module records a consent of kind `data_use`: the
clinic keeps its privacy notice as a versioned template, the patient signs
a copy of it, and the consent stores which version was accepted and when.
It can be revoked, and the revocation is recorded, not erased
([ADR 0045](../adr/0045-a-consent-is-a-record-entry.md)).

**Remaining.**

- **Nothing requires it.** A patient can be registered, treated and
  messaged with no data consent on file. `notifications` sends email today
  with no recorded basis, and WhatsApp (commitment 18) would widen that.
  `Patient.do_not_contact` is an opt-out and does not substitute.
- **The notice's contents are the clinic's.** The transfers section is what
  [`../subprocessors-catalog.md`](../subprocessors-catalog.md) generates; no
  notice is assembled from it.
- **Purposes are not modelled.** One consent covers "the use of my data";
  consent per purpose (care, reminders, marketing) is not distinguished.
- **Unverified law.** Mexico's private-sector data-protection law was
  replaced in March 2025. What it requires of consent for sensitive data
  and of the notice needs checking with Mexican counsel before the product
  claims anything.
