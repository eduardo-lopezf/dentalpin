# Record — permissions

| Permission | What it allows | Endpoints |
|---|---|---|
| `record.read` | Read a patient's composed clinical record, including the entries that were taken back when asked for explicitly. | `GET /patients/{patient_id}` |
| `record.configure` | Change how the clinic lays its record out: sections shown, their order, the points reviewed. Admin only. | `PUT /format` |
| `record.disclose` | Print or hand the record over — produces the document and records the disclosure — and re-open a document already handed over. | `POST /patients/{patient_id}/disclosures`, `GET /disclosures/{id}/document` |

`record.read` also lists a patient's disclosures (`GET /patients/{patient_id}/disclosures`)
and reads the clinic's format (`GET /format`).

The letterheads card of the settings page is the clinic's, guarded by
`admin.clinic.read` / `admin.clinic.write`. A professional reads and
changes **their own** letterhead without either — *Mi membrete*, under
Settings → Account — and no one else's.
`record.disclose` is granted to `admin` and `dentist` only.

`record.read` is granted by default to `admin` (wildcard), `dentist` and `hygienist`. **Not** to
assistant or receptionist: the record is what one clinician hands another, and
the conservative default is clinical staff. Review this with the clinic's own
governance — it is a policy question, not a technical one.

## Not declared yet

`record.authorise` appears in the spec and is absent from
`get_permissions()` until an endpoint uses it.
