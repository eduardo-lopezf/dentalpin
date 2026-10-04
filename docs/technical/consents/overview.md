---
module: consents
last_verified_commit: 0d60d45
---

# Consents — technical overview

Consent letters. Part of the **Clinical record** App, and the first piece
of the product's answer to NOM-004-SSA3-2012 (*cartas de consentimiento
informado*) and Ley General de Salud Art. 51 Bis 1
([ADR 0045](../../adr/0045-a-consent-is-a-record-entry.md)).

Two kinds, one mechanism — a text, a signature, a revocation:

| Kind | Authorises | Must name a professional |
|---|---|---|
| `informed` | Performing a procedure, after its risks and alternatives were explained | Yes, to be signed |
| `data_use` | The clinic processing the patient's personal data, against a privacy notice | No |

**Lifecycle.** `draft` → `signed` | `declined`; `signed` → `revoked`;
`draft` → `discarded`. A draft can be edited. Anything else is a record:
never edited, never deleted. A revocation keeps the text and the signature.

**The text is the clinic's.** A consent is written from a *template* the
clinic maintains (Settings → Clínica → Plantillas de consentimiento) and
keeps its own copy, plus the template version — which is what answers
"which privacy notice did they accept". Nothing here ships legal wording.

**Two ways to sign.** On screen (`signature_method = "screen"`, the
drawing kept on the row), or on paper (`"paper"`): `GET /{id}/pdf` prints
the letter as a form — the patient's data and the text already on it;
diagnosis, plan, names, dates and signatures as ruled lines — which is
filled in and signed by hand, scanned, uploaded to the patient's documents
(Media) and passed to `POST /{id}/sign` as `document_id`. The consent
checks through the `PatientDocuments` contract that the file belongs to
the same patient, and keeps its id — no foreign key (ADR 0042). With
Media off, a letter can be printed and signed on screen, not filed as a
scan.

**Where it shows.** The patient record's *Consentimientos* tab (slot
`patient.detail.tabs`), and the composed clinical record, under the
`consents` section, for signed, declined and revoked letters.

**What it does not do yet.** No remote signing by link, no automatic
"this plan needs a consent", and nothing *requires* a data-use
consent before the clinic messages a patient.

## API surface

- `GET /api/v1/consents/patients/{patient_id}`
- `GET /api/v1/consents/templates`
- `GET /api/v1/consents/{consent_id}`
- `GET /api/v1/consents/{consent_id}/pdf`
- `POST /api/v1/consents/patients/{patient_id}`
- `POST /api/v1/consents/templates`
- `POST /api/v1/consents/{consent_id}/decline`
- `POST /api/v1/consents/{consent_id}/discard`
- `POST /api/v1/consents/{consent_id}/revoke`
- `POST /api/v1/consents/{consent_id}/sign`
- `PUT /api/v1/consents/templates/{template_id}`
- `PUT /api/v1/consents/{consent_id}`

## Frontend

_This module ships no Nuxt pages._

## Permissions

`read`, `write`, `templates.write`
See [`./permissions.md`](./permissions.md) for the full role mapping.


## See also

- Module CLAUDE notes: `backend/app/modules/consents/CLAUDE.md`
- [Documentation portal contract](../../technical/documentation-portal.md)
