# Record — overview

The clinical record as a composition. One module, no clinical tables.

## What it is

A patient's *expediente* is spread across the modules that treat them:
demographics in `patients`, antecedents in `patients_clinical`, evolution notes
in `clinical_notes`, tooth status in `odontogram`, charting in
`periodontogram`, therapeutic plans in `treatment_plan`, radiographs in
`media`. This module assembles those into a header plus ordered sections of
dated, attributed entries — the shape of a paper record, and of both
interchange formats worth targeting later, so an export becomes a mapping
rather than a rewrite.

**It owns none of that data**, and the design says so out loud
([`docs/features/expediente-clinico.md`](../../features/expediente-clinico.md)):

> The temptation is to add an `expediente` table and copy data into it. That is
> the failure this spec exists to prevent. The record is not a new place to
> keep clinical data; it is a *view* of data seven modules already own, and the
> moment it becomes a copy it starts drifting from the source and there are two
> truths about a patient's allergies.

So the module has no models and no migrations, like `reports`.

## The contract

A contributing module returns `RecordSection` objects from
`get_record_sections()`. The vocabulary lives in `app.core.record`, not in this
module, for the reason that settled the same question for subject rights: a
contributing module would otherwise have to import from an **optional** module
and declare it in `manifest.depends`, which inverts the dependency and makes
`record` required by `patients_clinical`, which is not removable. Core owning
the types keeps every arrow pointing inward.

```python
RecordSection(
    name="allergies",                      # unprefixed; the registry adds the module
    title_key="record.section.allergies",  # i18n, never a literal
    category=SectionCategory.ANTECEDENTS,
    collect=_collect_allergies,            # (db, clinic_id, patient_id) -> [RecordEntry]
    order=10,
)
```

Each `RecordEntry` carries clinical time (`occurred_at` — a surgery recorded
today that happened in 2019 sorts into 2019), a lifecycle `status` (active /
ended / retracted, the distinction ADR 0032 settled), the professional
responsible and the account that typed it, where the fact lives
(`source_table` / `source_id`), and a `codes` list that stays empty until the
coding phase — the field exists from the start so adding coding is not a
migration of every section.

### It is not `SubjectContributor`

Same pattern, different contract, because they answer different questions:

| | `SubjectContributor` | `RecordSection` |
|---|---|---|
| Question | "What do you hold about this person?" | "What of yours belongs in a clinical record?" |
| Audience | The data subject, a regulator | Another clinician |
| Billing data | Yes — it is their data | **No** — a referral is not a financial document |
| Ordering | By module | Clinically, by section |
| Erasure | Central to it | Not applicable (ADR 0032) |

A module may implement both, one, or neither. `billing`, `payments`,
`verifactu` and `accounting_export` implement only the subject contract, and a
test pins that they contribute nothing here.

## Composition rules

- **Installed modules only.** The fan-out asks `module_registry.list_modules()`
  (ADR 0018), so an uninstalled module makes the record shorter, not broken.
- **Empty sections are returned.** "This module holds nothing about this
  patient" is an answer; a missing section leaves the reader unable to tell it
  was asked.
- **A failing section is logged and returned empty.** One module's bug must not
  deny a clinician the rest of the chart mid-consultation.
- **Retracted entries are excluded by default**, reachable with
  `include_retracted=true`. Never deleted — "what did the chart say that day"
  has to stay answerable — but not part of what a colleague is handed.
- **Entries sort by clinical time**, not by when they were typed.

## What this module does not do yet

Phases 1–4 of the spec. The composition and its read endpoint exist; the
patient-level view, the exports (PDF/A-3, DPMF), the disclosures and
authorisations, the coding and the interchange formats do not. See
*Phase 0, where it actually stands* in the spec for what is blocking what.
