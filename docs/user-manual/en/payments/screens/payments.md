---
module: payments
screen: list
route: /payments
related_endpoints:
  - GET /api/v1/payments
  - GET /api/v1/payments/budgets/{budget_id}/allocations
  - GET /api/v1/payments/filters/budgets-by-status
  - GET /api/v1/payments/filters/patients-with-debt
  - GET /api/v1/payments/patients/{patient_id}/ledger
  - GET /api/v1/payments/receivables
  - GET /api/v1/payments/receivables/{patient_id}/contacts
  - POST /api/v1/payments/receivables/{patient_id}/contacts
  - GET /api/v1/cashbox/periods
  - GET /api/v1/payments/reports/aging-receivables
  - GET /api/v1/payments/reports/by-method
  - GET /api/v1/payments/reports/by-professional
  - GET /api/v1/payments/reports/refunds
  - GET /api/v1/payments/reports/summary
  - GET /api/v1/payments/reports/trends
  - GET /api/v1/payments/{payment_id}
  - GET /api/v1/payments/{payment_id}/refunds
  - POST /api/v1/payments
  - POST /api/v1/payments/summary/by-budgets
  - POST /api/v1/payments/summary/by-patients
  - POST /api/v1/payments/{payment_id}/reallocate
  - POST /api/v1/payments/{payment_id}/refunds
related_permissions:
  - payments.record.read
  - payments.record.write
  - payments.record.refund
  - payments.reports.read
related_paths:
  - backend/app/modules/payments/frontend/pages/payments/index.vue
  - backend/app/modules/payments/router.py
last_verified_commit: 75cd119
---

# Payment list


> **Where it lives.** This screen is the **Payments** tab of
> **Finance**, in the sidebar right after Professionals. The old
> `/payments` address still works and redirects here.

The clinic's operational cash log. Each row is a payment received
from a patient, with its gross amount, the allocations to budgets or
*on-account*, and the refunded total if any. Record a new payment,
reallocate it, or issue a refund from the same screen.

> **On a tablet.** The list keeps its row layout in both landscape and
> portrait. Only phones stack it into cards, so rotating the tablet does
> not reorganise the information.


> **Selecting a row** opens that payment's card: gross, refunded and net,
> the allocations to a budget or *on account*, the method, date,
> reference and who recorded it. Refunding is available from there too.

## At a glance

- **Patient-centric, not invoice-centric.** Every payment belongs to
  a patient and splits into *allocations* (budget or `on_account`).
  Invoicing lives in the `billing` module and links back to these
  payments — never the reverse.
- **Filters live in the URL** — method, patient, date range, *With
  refunds*, *With on-account balance*. Sharing the link shares the
  filters.
- **Sort:** payment date descending by default. Amount sort is also
  available.
- **Off-books.** The list never crosses *paid* against *invoiced* —
  this is a deliberate product decision (see ADR 0010).
- **Refund state:** if a payment has refunds, the refunded amount
  shows in red under the gross amount. The ↺ button only appears
  when net balance remains and your role can refund.

## The Finanzas summary

> Finanzas → **Resumen**, the first tab and the one that opens by default.

Finanzas was six registers — Cobros, Por cobrar, Caja, Presupuestos,
Facturas, Liquidaciones. Every one is a good list and **none of them
answers the question people arrive with**: *how am I doing?* That answer
existed, in **Informes**, which is a different sidebar entry; somebody who
wants to see "the money" opens Finanzas and finds lists.

Now the answer comes first and the registers are one click behind:

| Tile | Says | Owned by |
|---|---|---|
| **Cobrado** | what came in today, net of refunds, and the month to date | `payments` |
| **Por cobrar** | work done and unpaid, how many patients, how much is over 90 days, and a way into the queue | `payments` |
| **Caja** | days of the fortnight not counted, with a way to the arqueo | `cashbox` |

Each tile is contributed by **its own module**. A clinic without `cashbox`
has no till tile and the row closes up; a role that can work the lists but
not read the money reports gets an empty summary that says why, rather than
a blank rectangle.

The till tile tells apart three things that are not the same: **days not
counted** (something to do), **up to date** (counted and square) and **no
movement** (the fortnight has seen no money). The third matters: reading
zero counted days as "up to date" would tell a clinic that has never done
an arqueo that it is doing fine.

## The "To collect" queue

> Finanzas → **Por cobrar**. Requires `payments.record.read`.

*Cobros* counts what came in. This tab counts **what did not**, and it is
a list of people rather than a figure.

The data existed but the list did not: the report said "seven patients owe
12,400 in the 90-day bucket" and clicking any of the four buckets went to
*patients with debt* — the same place for all four, with the age thrown
away. So the number was looked at and nothing followed. Budgets have
something that chases them; money already earned had nothing.

- **Oldest debt first**, which is the money most at risk and the order a
  person would work in.
- Each row carries what a call needs without opening the record: the
  **name**, **how much**, **how many days**, and **when they last paid
  anything** — somebody who paid last week is a different conversation from
  somebody silent since March.
- **Call**, **WhatsApp** and **Charge** buttons. The charge opens with the
  patient set and the amount suggested.
- The **four buckets** (0-30, 31-60, 61-90, 90+) filter, and the filter
  travels in the URL: clicking a bucket in the collections report lands
  here already filtered by it.

**Age is measured from the treatment the money did not reach**, not from
the patient's oldest one. That difference is what makes the list usable:
somebody three years in and up to date except for last week's filling has
a first treatment from 2023, and counting from there would file them under
90+ next to genuine bad debt. A queue that is wrong about the clinic's best
patients does not get opened twice.

### Logging a contact

The notebook button records **that somebody tried**: how — call, WhatsApp,
email, in person or other — and a line if it helps. Nothing more: the moment
it becomes a form with required fields, reception stops filling it in after
a call that went nowhere, which is exactly the call worth recording.

The row shows it. Chased today appears as a badge with the channel
(*contactado hoy (WhatsApp)*); an older contact just carries its date. That
is what stops two people ringing the same patient before lunch.

**A contact does not move money.** It is a note about an attempt; if the
attempt worked there is a payment to show for it. Keeping them apart is what
lets the row say "contacted yesterday, still owes 300".

The patient **does not drop off** the list once contacted: they still owe,
and hiding them would make the list disagree with the total above it.

## Record a payment

> Requires `payments.record.write`.

1. Click **New payment** in the header (or from the budget sidebar
   card on the patient record).
2. Pick the patient. Choose the method (cash, card, bank transfer,
   direct debit, insurance, or *other*) and the payment date.
3. Split the amount across the patient's open budgets, or leave it
   *on account* for later assignment. The sum of allocations must
   equal the gross amount — the form validates this invariant before
   submitting.
4. **Save**. `payment.recorded` and one `payment.allocated` per
   allocation are published. The budget's *Paid / Outstanding*
   sidebar card refreshes immediately.

## Reallocate a payment

> Requires `payments.record.write`.

1. Open the payment by clicking on its row, or from the patient
   record.
2. Use **Reallocate** to move amounts between budgets or between a
   budget and *on-account*. Each change publishes
   `payment.allocated` with the previous and new targets.

## Refund

> Requires `payments.record.refund`. Default is admin and dentist
> only. Admins may grant this to the front desk under *Settings →
> Users → Roles*.

1. Click ↺ on the payment row (only visible while net balance
   remains).
2. Enter the amount (partial or full) and the reason. The refund
   never deletes the original payment: it lands as a `Refund` row
   and is subtracted from the *net* total.
3. **Confirm**. `payment.refunded` is published and the row shows
   `− 50.00 €` under the gross amount.

In the patient's payments panel, each row's **⋮** menu offers only
*Refund*: there is no payment detail page, and the entry that linked
to one has been removed — it led to a 404.

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| View list, allocations, patient ledger | `payments.record.read` |
| Record a payment and reallocate it | `payments.record.write` |
| Issue a refund | `payments.record.refund` |
| Access the payment reports | `payments.reports.read` |

## Troubleshooting

- **The list is empty with active filters.** Click **Clear filters**
  in the toolbar (the chip with the counter). If nothing still
  shows, check the date range — none is set by default.
- **Save rejects with "allocation sum mismatch".** The total of the
  allocations must match the gross amount. Adjust a value or add an
  *on-account* allocation for the remainder.
- **No ↺ button even though my role should refund.** The payment is
  already 100% refunded (net is zero). Refunds only run while net
  balance remains.
- **An invoice is not reflected as paid on its budget.** The invoice
  links to the payment from the `billing` module. Make sure the
  payment is allocated to the right budget.
