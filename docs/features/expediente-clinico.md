# Expediente clínico electrónico — composition, disclosure and interchange

> Status: draft. Spec last updated: 2026-09-22.
> Decisions behind it: [ADR 0032](../adr/0032-clinical-record-is-append-only.md)
> (the record is append-only) and
> [ADR 0033](../adr/0033-disclosure-requires-a-recorded-authorisation.md)
> (disclosure requires a recorded authorisation).
>
> **Every regulatory statement here is an engineering reading, not legal
> advice, and is marked for local review before it ships.** What is
> settled is the *shape*: what the record is, which module answers for
> which part, and what may never leave without an authorisation.

## Why

A clinic that cannot hand a patient their record, or send a colleague the
relevant part of it, is not running a clinical system — it is running a
database with a nice interface over it. Today DentalPin is the second
thing. Everything a dental record needs is already stored, and none of it
can leave the building as a record.

The temptation is to add an `expediente` table and copy data into it.
That is the failure this spec exists to prevent. The record is not a new
place to keep clinical data; it is a *view* of data seven modules already
own, and the moment it becomes a copy it starts drifting from the source
and there are two truths about a patient's allergies.

Two things genuinely are new: the **authorisations** that permit a
disclosure, and the **artifacts** produced by one. Everything else is a
projection.

## 1. The record is a composition, not a table

A composition has a header and ordered sections, each holding dated
entries. That is the shape of a paper *expediente*, and — not
coincidentally — of both interchange formats worth targeting later: HL7
CDA R2 and FHIR `Composition`. Building the internal model in that shape
means the export formats are mappings rather than rewrites.

| Part | Content | Source |
|---|---|---|
| Header | Patient, clinic (custodian), responsible professional + licence, date, jurisdiction, purpose | `patients`, `clinics`, `professionals`, `PrivacyPolicy` |
| Sections | Identification, antecedents, odontogram status, periodontal charting, evolution notes, therapeutic plan, imaging, consents | one per contributing module (§2) |
| Entries | A dated, attributed clinical fact | the owning module's rows |

`patient_timeline` is already the chronological spine — it carries
`source_table`, `source_id`, `occurred_at` and an `event_data` JSONB
across 35 event types. The record does not replace it; it groups the same
material **clinically** (by section and episode) where the timeline
groups it **chronologically** (by event). Both views ship.

**Non-goal:** a `record` module that owns clinical rows. It owns the
composition logic, the disclosures and the produced artifacts — nothing
that another module is already the authority on.

## 2. The contract: `get_record_sections()`

Modules already answer for their own data through
`get_subject_contributors()` ([ADR 0026](../adr/0026-subject-rights-are-a-module-contract.md)),
and 16 of them implement it. The clinical record uses the same *pattern*
and a **separate contract**, because it answers a different question:

| | `SubjectContributor` (exists) | `RecordSection` (new) |
|---|---|---|
| Question | "What do you hold about this person?" | "What of yours belongs in a clinical record?" |
| Audience | The data subject, a regulator | Another clinician |
| Includes billing | Yes — it is their data | **No** — a referral is not a financial document |
| Ordering | By module | Clinically, by section and episode |
| Needs coding | No | Yes, for interchange (§7) |
| Erasure semantics | Central to it | Not applicable — see ADR 0032 |

A module may implement both, one, or neither. `billing`, `payments`,
`verifactu` and `accounting_export` implement only the subject
contract — a clinical disclosure that carries invoice data is a privacy
defect, not a feature.

Sketch — the sharp edges, not the full signature:

```python
RecordSection(
    name="allergies",                    # unprefixed; registry adds the module
    title_key="record.section.allergies",  # i18n, never a literal
    category=SectionCategory.ANTECEDENTS,
    collect=_collect_allergies,          # (db, clinic_id, patient_id, scope) -> [RecordEntry]
)
```

Each `RecordEntry` carries, at minimum:

- `occurred_at` — **clinical time, not row-creation time.** A surgery
  recorded today that happened in 2019 sorts into 2019.
- `authored_by` — the professional and licence per
  [ADR 0032](../adr/0032-clinical-record-is-append-only.md), distinct
  from the account that typed it.
- `status` — active, ended, or retracted. Retracted entries are excluded
  from disclosures by default and never silently dropped from the record.
- `codes` — empty until §7; the field exists from the start so adding
  coding is not a migration of every section.

Contributing modules: `patients`, `patients_clinical`, `clinical_notes`,
`odontogram`, `periodontogram`, `treatment_plan`, `media`, `agenda`.
Whether `recalls` contributes a "recommended follow-up" section is **TBD**
— clinically meaningful, arguably commercial.

### Confirming a plan contributes an episode

The request that started this spec was "create the record from a
treatment plan". The relationship is the other way round: the plan is one
section of a lifelong, patient-scoped record, and a patient with no plan
still has allergies and radiographs.

What does hold is the pattern already established when budget creation
moved behind plan confirmation: **confirming a treatment plan appends an
episode** — a structured entry with diagnosis, therapeutic plan and
responsible professional — to the record. The plan contributes to the
record; it does not create it.

## 3. Where it appears

A top-level *Expediente* entry sitting next to *Pacientes* forces a
choice every time — they are the same thing seen twice. The split that
avoids it:

- **The record itself lives inside the patient**, as a view on the detail
  page ([ADR 0011](../adr/0011-detail-page-shared-components.md)),
  alongside the existing timeline. Default axis: what happened and when.
  Density uses the existing `compact` mode — a record is dense by nature
  and the design system's calm is achieved by subtraction, not by
  spacing a chart until it needs scrolling.
- **The new menu entry is for record *operations***, which are global and
  fit nowhere on one patient's page:

  | Screen | Purpose |
  |---|---|
  | Disclosures | Outgoing and incoming, with status and scope |
  | Authorisations | Pending signature, active, revoked, expiring |
  | Imports | External records being reconciled (§6) |
  | Access log | Who read or exported which record, when |

Permissions follow [ADR 0005](../adr/0005-relative-permissions.md), so
the module returns them unprefixed: `record.read`, `record.export`,
`record.disclose`, `record.authorise`. Who gets `disclose` is **TBD** and
is a clinical-governance question, not a technical one — the defensible
default is that it is not a reception-desk permission.

Every screen added here owes a user-manual page in **both** locales per
the root `CLAUDE.md` checklist.

## 4. Formats: three layers, one composition

Reaching for FHIR first is the common mistake. Nothing in a dental
referral circuit consumes it today, and Mexico's NOM-024-SSA3-2012 asks
for CDA R2 with CIE-10, not FHIR.

| Layer | Format | Role | Phase |
|---|---|---|---|
| Legal / human | **PDF/A-3**, signed | What the patient receives, what gets printed, what survives an archive. A-3 because it *embeds* the structured payload — one file, both audiences | 1 |
| Portable / own | **DPMF** (`.dpm`), extended | DentalPin↔DentalPin transfer and backup. The format and its reader already exist in `migration_import` | 1 |
| Interoperable | **FHIR R4 Bundle** (`type=document`); **CDA R2** | Only when a real counterparty needs it, or NOM-024 certification is pursued | 3 |

**The rule that makes this affordable: all three are projections of one
composition, never three independent serialisers.** A section added once
appears in every format.

**Imaging is referenced, not embedded.** Dentistry means periapicals,
panoramics and CBCT; `docs/technical/todos.md` already scopes a DICOM
phase. A disclosure carries a pointer plus a web-viewable rendering, and
the DICOM original travels on request. Embedding studies in a document
produces files nobody can email.

## 5. The authorisation protocol

Governed by [ADR 0033](../adr/0033-disclosure-requires-a-recorded-authorisation.md):
nothing leaves without a `Disclosure` naming recipient, purpose, scope
and basis. This section is the flow that produces one.

### The four flows

**A — Referral for continuity of care** (the common case, and the one
that must stay fast). The dentist picks the recipient, the sections and a
clinical justification; the disclosure is recorded and sent. No patient
signature, because the basis is provision of care — but the patient is
notified that it happened, through the existing notifications gateway.
If this flow is slower than attaching a PDF to a personal email, the
feature has failed.

**B — Share at the patient's request** (second opinion, third party,
insurer). Requires express authorisation. Two capture paths, both already
built here:

- *In clinic*: signed on a tablet, reusing the signature capture behind
  budget acceptance (`budget_signatures`) and the touch rules of
  [ADR 0022](../adr/0022-touch-adaptation-is-capability-driven.md).
- *Remote*: an expiring link with second-factor verification, exactly the
  mechanism of [ADR 0006](../adr/0006-budget-public-link-2-factor-auth.md).
  Same infrastructure, different payload.

**C — Incoming request** from a hospital, colleague or insurer. The
clinic never answers directly. The request is logged, the patient is
asked to authorise (path B), and only then does a disclosure exist. An
unauthorised request expires visibly rather than sitting in someone's
inbox.

**D — The patient's own copy.** A subject access request, already
[ADR 0026](../adr/0026-subject-rights-are-a-module-contract.md) territory
— no third-party authorisation, but identity verification, and the
clinical projection rather than the raw subject export.

### What the patient signs

Scope in clinical language, not table names: *"Historia clínica y
antecedentes, radiografías del 2024 en adelante, plan de tratamiento
actual"*. Plus recipient, purpose, expiry, and the revocation right —
stated with its real limit, that revoking stops future sending and
cannot recall what was already sent. The signed artifact is filed **in
the record**, which is where NOM-004 expects the consent letter to live.

For minors and patients under guardianship the authoriser comes from
`patients_clinical_legal_guardian`, and the disclosure records the
capacity they acted in.

### Revocation

A new entry, never a deletion. It closes the authorisation for future
use; prior disclosures keep their manifest and digest, because "what did
they receive" must stay answerable after consent ends.

## 6. Import and export

**Export** runs the composition through a format projection (§4) under a
disclosure (§5). The produced artifact is retained with its digest —
a disclosure that cannot reproduce what it sent is not evidence.

**Import** reuses the workflow `migration_import` already proved: upload,
validate, **propose**, let an operator decide row by row, then execute,
with each `MappingDecision` persisted. An external record raises the same
problem a migration does — reconciling someone else's codes, teeth
notation and identities against yours — and the answer is the same:
never auto-merge clinical data, always let a human adjudicate.

Two dental-specific traps for the importer: **tooth notation** (DentalPin
uses FDI/ISO 3950; a US-origin record will be Universal) and units in
periodontal charting. Both must be declared on import, not inferred.

## 7. Clinical coding — the gate for interchange

There is no coding anywhere in the codebase today: no CIE-10, no SNOMED,
no SNODENT, no procedure codes. Without them a disclosure can only carry
prose, and prose is not interchange.

Minimum viable is far smaller than the full catalogues:

- **Diagnoses**: CIE-10 chapter **K00–K14** (oral cavity, salivary glands
  and jaws) — tens of codes, not thousands. NOM-024 asks for CIE-10.
- **Procedures**: map the existing treatment catalogue to one procedure
  code set. Which one is **TBD** and jurisdiction-dependent.

The catalogue already has a category/specialty structure to hang codes
on, so this is an additive mapping rather than a re-modelling. It gates
phase 3 entirely and nothing before it.

## 8. Phases

| Phase | Contents | Gate |
|---|---|---|
| **0 — Immutability** | [ADR 0032](../adr/0032-clinical-record-is-append-only.md): stop hard-deleting in `patients_clinical`, amendments append in `clinical_notes`, attribution carries the licence | Nothing else is worth building on mutable clinical data |
| **1 — Composition** | `record` module, `get_record_sections()`, patient-level view, new menu entry, PDF/A-3 + DPMF export with digest chaining | Phase 0 |
| **2 — Authorisation** | [ADR 0033](../adr/0033-disclosure-requires-a-recorded-authorisation.md): disclosures, the four flows, signature capture, access log | Phase 1 |
| **3 — Coding** | CIE-10 K00–K14, procedure mapping | Phase 1 |
| **4 — Interchange** | FHIR R4 Bundle, CDA R2 if certification is pursued, DICOM transport | Phases 2 and 3 |

Phase 0 is three bounded corrections to existing modules and carries the
one migration risk worth naming: it rewrites populated clinical tables,
which is the class of change that has already broken a deploy here. It
gets tested against a database with rows.

## Open questions

- Which role holds `record.disclose`. Clinical governance, not technical.
- Whether `recalls` contributes a clinical section.
- Which procedure code set, per jurisdiction.
- Retention floors per jurisdiction, expressed through the existing
  `retention_reason` — needs the counsel review this whole document is
  conditioned on.
- Whether a `SELF`-custody tenant gets the same disclosure UI when there
  is no subprocessor in the path ([ADR 0028](../adr/0028-self-hosting-is-the-premium-tier.md)).
