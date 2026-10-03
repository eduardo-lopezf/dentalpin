# consents

Consent letters: informed consent to treat, and consent to the use of
personal data. Part of the **Clinical record** App
([`docs/apps/clinical_record/`](../../../../docs/apps/clinical_record/README.md)).

## Public API

Routes mounted at `/api/v1/consents`. See
[`docs/technical/consents/`](../../../../docs/technical/consents/overview.md).

- Templates: `GET/POST /templates`, `PUT /templates/{id}`.
- Consents: `GET/POST /patients/{patient_id}`, `GET/PUT /{id}`,
  `POST /{id}/sign`, `/decline`, `/revoke`, `/discard`.

## Dependencies

`manifest.depends = ["patients"]`, `manifest.integrates = ["professionals"]`.

Neither is imported. The patient is validated through `PatientDirectory`
and the professional who explained a consent is read through
`ProfessionalDirectory` and stored as a **snapshot** — id, name, licence —
with no foreign key (ADR 0039, ADR 0042). `plan_id` is likewise an id
without a foreign key.

## Permissions

`consents.read`, `consents.write`, `consents.templates.write`.

## Tools exposed

None. Reading a consent to an agent hands it a signature and free text;
writing one is a clinical act with a person's name on it.

## Events emitted / consumed

None.

## Frontend slots

Registers the *Consentimientos* tab in `patient.detail.tabs` and a settings
page (`consent-templates`, category `clinical`). No pages of its own.

## Rules that are not obvious

- **A consent is a record entry** ([ADR 0045](../../../../docs/adr/0045-a-consent-is-a-record-entry.md),
  ADR 0032). Only a `draft` is edited. `signed`, `declined` and `revoked`
  are never edited or deleted; a revocation is a state and a date on the
  same row. There is no delete endpoint, and there must not be one.
- **The body is a copy.** A consent stores the text the patient saw and
  the template version. Editing a template bumps its version and reaches
  no letter already written.
- **An informed consent cannot be signed without naming who explained
  it** — Art. 51 Bis 1 puts the duty on a person. With the Professionals
  App off, drafts and data-use consents still work; naming a professional
  is refused, so informed consents wait.
- **No legal text ships with the module.** Templates are the clinic's.
  Do not seed wording that reads as legal advice.
- **Two consents, not one.** `informed` and `data_use` share a mechanism
  and nothing else; neither substitutes for the other, and a signed budget
  substitutes for neither.
- **Subject rights:** exported, never erased (`privacy.py` states the
  retention reason).

## Not built yet

Remote signing by expiring link; a PDF of the letter; "this plan needs a
consent" from Treatments; enforcement of a data-use consent before
messaging a patient; guardians read from `patients_clinical`.

## CHANGELOG

See `./CHANGELOG.md`.
