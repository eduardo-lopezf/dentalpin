---
module: consents
last_verified_commit: 0d60d45
---

# Consents

The patient's consent letters. Part of the **Clinical record** App.

## What it does

- **Informed consent.** The letter in which a professional explains a
  procedure, its risks and its alternatives, and the patient accepts or
  declines. It cannot be signed without naming the professional who
  explained it.
- **Use of personal data.** The patient accepts the clinic's privacy notice.

## Where it is

- **Patient record → Consents.** Lists the patient's letters. *New consent*
  writes a draft from a template; *Sign* shows the text to the patient and
  captures their signature on screen (or records that they decline).
- **Settings → Clinic → Consent templates.** The clinic's texts: one per
  procedure, and the privacy notice. Editing a template creates a new
  version; letters already written do not change.

## Worth knowing

- A draft can be edited or discarded. **A signed letter is never edited or
  deleted**: if the patient takes their consent back it is **revoked**, and
  what they signed and when they withdrew it stay on record.
- Signed, declined and revoked letters appear in the patient's clinical
  record.
- The wording of the templates is the clinic's and its legal adviser's; the
  program ships no legal text.
- With the Professionals app disabled nobody can be named as having
  explained the procedure, so an informed consent cannot be signed.

## Permissions

- `consents.read`
- `consents.write`
- `consents.templates.write`

## Technical references

- [Technical overview](../../../technical/consents/overview.md)
- [Permissions](../../../technical/consents/permissions.md)
