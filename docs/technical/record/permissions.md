# Record — permissions

| Permission | What it allows | Endpoints |
|---|---|---|
| `record.read` | Read a patient's composed clinical record, including the entries that were taken back when asked for explicitly. | `GET /patients/{patient_id}` |

Granted by default to `admin` (wildcard), `dentist` and `hygienist`. **Not** to
assistant or receptionist: the record is what one clinician hands another, and
the conservative default is clinical staff. Review this with the clinic's own
governance — it is a policy question, not a technical one.

## Not declared yet

`record.export`, `record.disclose` and `record.authorise` appear in the spec
and are deliberately absent from `get_permissions()` until the endpoints that
use them exist. A permission with nothing behind it is a promise the UI starts
making on its own, and `disclose` in particular is an open governance question:
the spec's own defensible default is that it is not a reception-desk
permission.
