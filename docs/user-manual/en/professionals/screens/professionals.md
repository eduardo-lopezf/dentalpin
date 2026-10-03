---
module: professionals
screen: list
route: /professionals
related_endpoints:
  - GET /api/v1/professionals
  - GET /api/v1/professionals/{professional_id}
  - POST /api/v1/professionals
  - PUT /api/v1/professionals/{professional_id}
related_permissions:
  - professionals.read
  - professionals.write
related_paths:
  - backend/app/modules/professionals/frontend/pages/professionals/index.vue
  - backend/app/modules/professionals/router.py
last_verified_commit: 0d60d45
---

# Directory

The directory lists active dentists and collaborators by default. Search by
name, specialty or professional-license number; select a profile type or show
inactive profiles when needed.

> **On a tablet.** The list keeps its row layout in both landscape and
> portrait. Only phones stack it into cards, so rotating the tablet does
> not reorganise the information.

## View a profile

Select any row to open the **professional's card**: the portrait at size, the
profile type, the status and the disciplines they practise, and below them a
mosaic of tiles with the licence number, email, phone and whether they have
system access. Email and phone are links — selecting one opens the mail client
or the dialler.

The card answers the usual question, who is this person, without entering edit
mode. To change anything, use **Edit profile** from inside the card.

## Add or edit a profile

> Creating and editing requires `professionals.write`.

1. Select **Add professional**, or open an existing professional's card
   and choose **Edit profile**.
2. Enter name and profile type. Add specialty, professional license, photo URL
   and contact fields as needed.
3. Use **Active** to retain a former collaborator in the directory without
   including them in the default list.
4. If the profile's email matches a user with access to this clinic, a
   read-only **"User with access"** note with a green check appears next to
   **Active**.
5. Select **Save**.

Profiles are directory records only. They do not grant a login or
permissions. The "User with access" indicator only reports whether a
matching account already exists — it does not create or link one.

## Linked account

The **Linked account** dropdown on the form says which account this person
signs in with. It is what lets a clinical entry name **who is responsible for
it**: when someone records an allergy or writes a note, the record keeps the
account that operated the software and, through this link, the professional and
their licence number.

Leave it on **No account** when the person does not use the system — an
external collaborator, someone not given access yet. The directory does not
require an account, which is why the field can stay empty.

**It is not inferred from the email.** The "User with access" indicator
compares emails and is a hint, nothing more: two people can share a family
address, someone changes their email, a clinic reuses one. The authorship of a
clinical document cannot rest on a coincidence, so you state the link yourself.

The list only offers accounts **with access to this clinic**, and never one
already linked to another professional: an account is a person, and two
profiles sharing it would leave unanswered who signs each entry.

## Specialty

A professional can hold **one or more** specialties, picked from the **clinic's catalog**
(Settings → Treatment catalog → By Specialty), not from a fixed list. It is
the same catalog that classifies treatments, so "Ortodoncia" means the same
thing in both places and the question "which disciplines does my staff cover"
becomes answerable.

An empty catalog means an empty dropdown: create the specialties in Settings
first. Searching by specialty still works.
