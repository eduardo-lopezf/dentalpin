# 0046 — Letterheads belong to the clinic, and a document carries its own professional's

- **Status:** accepted
- **Date:** 2026-10-04
- **Deciders:** Eduardo
- **Tags:** core, printing, modules

## Context

Three modules print clinical documents: `record` (the clinical record),
`consents` (the consent letters) and `patients_clinical` (the blank health
questionnaire). Each built its own head — the clinic's name in one, the
professional's in another — so three sheets handed to the same patient
looked like they came from three places.

The letterhead was first added to the record's format, in the `record`
module. That fixed one document. The other two could not use it: `consents`
and `patients_clinical` may not import `record`, and a clinic with the
record module off would have had no letterhead at all.

## Decision

**Letterheads are the clinic's, owned by the core: one of the clinic's own
and one per professional who wants theirs. A printed clinical document
carries the letterhead of the professional it answers to, the clinic's
when they have none, and never another professional's.**

- `clinic_letterheads` (core migration `0013`): one row per owner —
  `owner_key` is `"clinic"` or a professional's id — with the words
  (heading, an extra line, whether address and contact show) and the logo.
  The professional is an id without a foreign key: the directory is a
  module, and the core chain cannot point into a module's branch.
- A module that prints calls `render_letterhead(db, clinic_id,
  professional_id)` and includes `LETTERHEAD_CSS`. It never builds a head
  of its own.
- **Which professional is not a choice made at print time.** It is the one
  the document answers to: who explained a consent; the professional
  profile of whoever hands a record over or prints a blank questionnaire.
  `render_letterhead` takes no letterhead id — there is no way to ask for
  somebody else's — and that is how "never another doctor's" holds.
- A professional with no letterhead gets the clinic's. A clinic with none
  gets its bare name.
- **Who may change one**: whoever runs the clinic's settings
  (`admin.clinic.write`) manages them all; a professional manages their
  own — theirs and nobody else's, not the clinic's and not a colleague's.
  "Their own" is the directory profile their account is linked to. The
  check is made in the handler (`declares_permissions`), because whose
  letterhead it is depends on the path.
- A letterhead can only be created for a professional of the clinic's
  directory. All at `/api/v1/auth/clinic/settings/letterheads`.
- The screen that edits them is the Clinical record App's settings page,
  because that is where a clinic looks for it. Where it is edited and who
  owns it are different questions.

## Consequences

### Good

- A clinic of several doctors prints each one's documents under their
  own head, without anybody choosing — and without the chance of one
  doctor's record leaving under another's name.
- A solo practice sets up the clinic's letterhead and nothing else.
- It survives any module being switched off.
- A new printed document gets the letterhead with two lines.

### Bad / accepted trade-offs

- A professional edits their own only once an admin has linked their
  account to their directory profile. An unlinked account has no
  letterhead of its own, and the demo seed links nobody.
- A document printed by an account with no professional profile — a
  receptionist, an admin — carries the clinic's letterhead, not the
  treating doctor's.
- A stored disclosure keeps the letterhead it left with; changing a
  letterhead later does not rewrite it.
- The page that edits it belongs to an optional App. With Clinical record
  off there is no screen for it yet; the endpoints still work.
- Budgets, invoices and prescriptions keep their own headers. They are
  commercial documents with their own layout; bringing them in is a
  separate decision.
- The logo accepts PNG and JPEG only. SVG is refused on purpose: nothing
  scriptable reaches the PDF renderer.

## How to verify the rule still holds

`backend/tests/test_letterhead.py`: each professional's documents carry
their own letterhead and not a colleague's; one with none falls back to
the clinic's; a consent prints under the letterhead of who explained it;
and the three printers use `render_letterhead` and reach for a letterhead
by no other road. A dentist changes their own letterhead and is refused
the clinic's, a colleague's and the list of everybody's.
