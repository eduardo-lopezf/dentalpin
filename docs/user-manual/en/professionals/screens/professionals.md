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
last_verified_commit: e2b7328
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

## Specialty

A professional can hold **one or more** specialties, picked from the **clinic's catalog**
(Settings → Treatment catalog → By Specialty), not from a fixed list. It is
the same catalog that classifies treatments, so "Ortodoncia" means the same
thing in both places and the question "which disciplines does my staff cover"
becomes answerable.

An empty catalog means an empty dropdown: create the specialties in Settings
first. Searching by specialty still works.
