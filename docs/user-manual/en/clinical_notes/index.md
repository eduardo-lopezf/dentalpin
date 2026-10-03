---
module: clinical_notes
last_verified_commit: 0d60d45
---

# Clinical Notes

> _Scaffolded stub — replace with proper documentation when this module is next touched._

Landing page for the `clinical_notes` module in the end-user manual.

## Screens

This module ships no Nuxt pages of its own.

## Correcting a note

A note is amended, not rewritten. Editing the text **keeps the previous one as
a version**: with its number, the moment it stopped being current, who replaced
it and the reason, if one was written.

It used to be overwritten in place. The prior text was gone, so a correction
and an original were the same thing, and there was no way to answer what the
note said on the day of the procedure — which is exactly what a complaint or an
insurance review asks.

- The note still shows **the current text**; the history sits behind
  `GET /notes/{id}/versions`, under the same permission as reading the note.
- **Saving without changing anything is not a correction.** If it were, opening
  a note and pressing save would fill the record with identical versions and
  bury the real amendments.
- **The reason is optional.** Demanding one would fill the record with the word
  "correction"; the reasons worth having are written when there is something to
  say.
- **Amending does not change the author.** If an admin corrects someone else's
  note, the note still belongs to whoever wrote it; the version records who
  replaced the text.

## Permissions

- `clinical_notes.notes.read`
- `clinical_notes.notes.write`

## Technical references

- [Technical overview](../../../technical/clinical_notes/overview.md)
- [Permissions](../../../technical/clinical_notes/permissions.md)
- [Events](../../../technical/clinical_notes/events.md)
