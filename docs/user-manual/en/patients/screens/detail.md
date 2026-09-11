---
module: patients
screen: detail
route: /patients/[id]
related_endpoints:
  - GET /api/v1/patients/{patient_id}
  - PUT /api/v1/patients/{patient_id}
  - DELETE /api/v1/patients/{patient_id}
  - GET /api/v1/patients/{patient_id}/extended
  - PUT /api/v1/patients/{patient_id}/extended
related_permissions:
  - patients.read
  - patients.write
related_paths:
  - backend/app/modules/patients/router.py
  - backend/app/modules/patients/frontend/pages/patients/[id].vue
last_verified_commit: 3568519
---

# Patient detail

Dashboard-style patient view. A persistent header carries identity,
critical allergy chips and quick actions; below it sits a tab strip.
The default **Summary** tab is a modular dashboard where each block
is contributed by a different module (plans, agenda, payments,
dental chart, medical history). Every block is also a deep link —
one click reaches the detail.

## Layout

- **Sticky header** — avatar, name, age, ID, contact, critical
  allergy chips (allergy, pregnancy, anticoagulant…) and *Edit* +
  *Actions ▾* buttons (Appointment, Collect, Note, Archive). Stays
  visible while scrolling and across tabs.
- **The tab strip scrolls rather than squeezing.** Six tabs with icons
  do not fit across a tablet held upright: Nuxt UI shared the width out
  and every label collapsed to an ellipsis ("Sum…", "Admin…", "G…").
  They now keep their natural width and the strip slides sideways. Only
  the strip scrolls — the panels below keep `overflow-visible`, which
  sticky children rely on.
- **Summary (dashboard)** — smart-cards contributed by each owning
  module via the `patient.summary.cards` slot:
  - **Active plan** *(treatment_plan)* — title, progress bar, n/m
    treatments. Click → plan detail.
  - **Next appointment** *(agenda)* — day/time/professional.
    Click → appointment.
  - **Balance** *(payments)* — debt / on-account / paid. Click →
    Administration → Payments.
  - **Diagnoses** *(odontogram)* — untreated findings count.
    Click → dental chart in diagnosis mode.
  - **Medical history** *(patients_clinical)* — allergies, systemic
    diseases, medication. Click → edit history.
  - **Quick actions** *(patients)* — Appointment, Budget, Document
    and the `patient.summary.actions` slot for sibling modules
    (recalls *Set recall*, notifications, etc.).
- **Tabs** — Info, Clinical, Administration, Gallery, History. In
  Clinical and Administration the sub-nav is a pill-bar exposing all
  modes upfront (Diagnosis · Plans · Appointments · History /
  Budgets · Billing · Payments · Documents).
- **Mobile** — header condenses, cards stack to a single column and
  a sticky bottom bar surfaces the three core actions
  (Appointment · Collect · Note).

## What happens when something fails

This screen gathers surfaces from several modules, and they share the
same safety rules:

- **A clinical note is never lost.** If the save fails, the composer
  stays open with your text and an error notice. It used to clear the
  field even though nothing had been saved.
- **Deleting a note asks for confirmation** on all five surfaces that
  offer it (appointment, diagnosis, plan, treatment, recent notes).
  The endpoint has no undo.
- **Editing an odontogram treatment** keeps your changes on screen
  when the save fails, and deleting one asks first: it may already be
  invoiced.
- **Replying over WhatsApp** ignores a second Enter while a message is
  in flight. Every send is billed and read by the patient.
- **No list hides data silently.** The odontogram change history says
  *Showing N of M* and offers to load earlier ones; the document
  gallery and the activity feed paginate for real.

## Editing identity

> Requires `patients.write`.

The identity card on **Info** is laid out as a profile: a tinted band,
the portrait (or initials) sitting on its edge, the name as the heading,
and the facts as a mosaic of tiles — the same visual language as the
professional profile card. Only tiles with content are drawn, except the
date of birth, which always shows because its absence is itself
clinically relevant.

1. Click the pencil icon in the summary hero, or the **Edit general
   details** button on the identity card.
2. Update name, contact, ID document, demographics. Extended demographics
   live behind the *Identity → Extended* tab and are persisted via the
   `/extended` endpoint.
3. **Save** publishes a `patient.updated` event with the changed fields,
   so dependents (recalls, notifications, …) can react.

## Archiving a patient

> Requires `patients.write`. Patients are **never** hard-deleted.

1. Open the **⋮ More** menu in the summary hero.
2. Click **Archive patient**.
3. Confirm. The patient's `status` flips to `archived`, the row is
   hidden from default lists, and a `patient.archived` event is
   published.
4. To restore, run an SQL update on the `status` column — there is no
   in-app un-archive flow yet.

## Payments tab — "Pending to charge"

The **Administration → Payments** tab shows the patient ledger
(total paid, debt, on-account balance) and, when there is real debt,
a **Pending to charge** card at the top.

- The card lists the recently completed sessions that net payments
  haven't covered yet (FIFO).
- Each session's date and time are the **clinic's**, not those of the
  reader's browser: reception is matching them against an appointment, and
  that appointment happened at the practice. Opening the record from another
  country does not change the time shown here.
- Total equals `clinic_receivable = earned − net_paid`.
- The **Collect** button opens the payment modal with the amount pre-filled
  in the clinic's currency; reception just picks the method and confirms.
- After the payment is recorded, the card disappears (or shrinks)
  depending on how much was collected.

## "Do not contact"

The `do_not_contact` flag is the operational opt-out. When enabled:

- Recalls module excludes the patient from any recall queue.
- Future outreach modules (email, SMS) MUST honour the flag.
- The patient still appears in the list and can be opened normally —
  they just won't be pestered automatically.

## Permissions

| You see / can do | Permission |
|------------------|-----------|
| View the detail | `patients.read` |
| Edit identity / extended | `patients.write` |
| Archive | `patients.write` |
| Sibling-module actions (recalls, notifications, …) | The sibling module's permissions. |

## Troubleshooting

- **Edit and Archive buttons are hidden.** Your role lacks
  `patients.write`. An admin can grant it via *Settings → Users → Roles*.
- **A tab I expected isn't there.** That tab is contributed by a
  sibling module (e.g. *Treatment plans*). Make sure that module is
  installed and you have its read permission.
