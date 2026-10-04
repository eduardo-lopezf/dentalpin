---
module: record
screen: settings_apps_clinical-record
route: /settings/apps/clinical-record
related_endpoints:
  - GET /api/v1/record/format
  - PUT /api/v1/record/format
  - GET /api/v1/auth/clinic/settings/letterheads
  - PUT /api/v1/auth/clinic/settings/letterheads/{owner}
  - DELETE /api/v1/auth/clinic/settings/letterheads/{owner}
  - GET /api/v1/auth/clinic/settings/letterheads/{owner}/logo
  - PUT /api/v1/auth/clinic/settings/letterheads/{owner}/logo
  - DELETE /api/v1/auth/clinic/settings/letterheads/{owner}/logo
related_permissions:
  - record.read
  - record.configure
  - admin.clinic.read
  - admin.clinic.write
related_paths:
  - backend/app/modules/record/frontend/pages/settings/apps/clinical-record.vue
last_verified_commit: 5421a03
---

# Clinical record settings

**Settings → Apps → Clinical record → Configure.** How the clinical record
is put together in this clinic. What is chosen here applies to the whole
clinic, on every patient's *Record* tab and on the document that is printed
or handed over.

## Permissions

- `record.read` — see the format.
- `record.configure` — change it (admin only).

## Letterheads

What heads **everything the clinic prints**: the record, the consent
letters and the blank health questionnaire.

- **Clinic**: the default letterhead.
- **One per professional**: under *Own letterhead for* choose the
  professional and press *Add*; the card appears with their name and
  licence already offered as the extra line.

Each card has:

- **Logo**: a PNG or JPG of up to 512 KB. Saved the moment it is chosen.
- **Heading**: left empty, it is the clinic's name.
- **Extra line**: free text — the professional and their licence, a
  speciality.
- **Show address** and **Show phone and email**: the clinic's own details;
  here you only decide whether they appear.
- Its own **Save** button, and *Remove letterhead*.

### Which letterhead each document carries

It is not chosen when printing; the system decides:

- **Consent letter**: that of the professional who explained it.
- **Record** and **blank questionnaire**: that of the professional who
  prints or hands it over.
- If that professional has no letterhead of their own, or whoever prints
  is not one of the clinic's professionals, the clinic's is used.
- **Another doctor's letterhead is never used.**

From this page they are managed by whoever may change the clinic's
details. In addition, **each professional can set up their own** under
*Settings → Account → My letterhead*, without being able to touch the
clinic's or a colleague's. Their account has to be linked to their
professional profile for that.

## Sections and order

Each section of the record has a switch and arrows to move it up or down.

- **Turning a section off** removes it from the *Record* tab and from what
  can be printed or handed over. **It deletes nothing**: the data stays
  where it is written, and turning it back on brings it back.
- **The order** is the one the record follows on screen and on paper.
- A section added by an App enabled later appears at the end.

## What the record should hold

The points the *Record* tab reviews for each patient. Turn off the ones
that do not apply to your clinic; they stop showing as pending.

## Consent templates

A shortcut to the texts of the consent letters.

## Saving and restoring

Nothing changes until **Save** is pressed. **Reset** returns to the default
format — every section, in the order of a paper record, every point
reviewed — and has to be saved too.
