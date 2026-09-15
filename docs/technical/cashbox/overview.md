# Cashbox — overview

The clinic's till. Shipped in phases; phase 1 is the movements surface.

## Why it is a module and not a report

`payments` already answers *how much came in this week, by method, by
professional* — `/reports/trends` even buckets by day, week and month. A
**corte de caja** is a different kind of object: an act in which a person
counts the drawer, declares what was in it, and freezes the difference
between that and what the system expected. The number that matters is the
one no query can produce.

## The two layers

| Layer | What it is | Status |
|---|---|---|
| **Movements** | Money in or out of the drawer that is not a patient payment | Phase 1 — shipped |
| **Arqueo diario** | The count: opening float, expected, counted, difference, frozen | Phase 2 — shipped |
| **Cortes de periodo** | Weekly / fortnightly / monthly roll-ups **of the daily closings** | Phase 3 — shipped |
| **Late entries** | Money landing in an already counted day, surfaced rather than absorbed | Phase 4 — shipped |

Period cuts are built from the daily closings, never recalculated from
`payments`. A fortnight recalculated from payments looks perfectly clean
with three unreconciled days inside it; one built from closings says
*three days still open*, which is the thing the clinic needs to know.

## Why movements shipped first

A till is emptied all day by things `payments` will never know about — the
lab courier is paid, gloves are bought, an assistant takes an advance,
change comes from the safe. Without somewhere to record them the counted
cash can never match the expected cash, the difference is non-zero every
single day, and the arqueo is abandoned within the fortnight as "it always
says there's an error".

They are also useful alone: *where did today's cash go* is a question the
clinic could not ask at all before.

## The three channels do not cut the same way

Planned for phase 2, recorded here because it shapes the model:

- **Cash** is counted physically. Only this channel has a difference.
- **Card** is reconciled against the terminal's own batch, and what reaches
  the bank is not what the patient paid — the commission takes 3-4 %.
- **Transfer / direct debit / insurance** is not till money at all. It
  reaches the bank on its own schedule and appears for information only.

Putting all three in one "corte" is the commonest way this feature is made
useless.

## What the count is made of

```
expected = opening float
         + cash collected      (Payment.method = 'cash', payment_date = the day)
         - cash refunded       (Refund.method = 'cash',  refunded_at in the clinic's day)
         + movements in
         - movements out
```

The two halves of the day boundary are not symmetric, and that asymmetry is
the whole reason `app.core.utils.clinic_time` exists: `payment_date` is
already a DATE in the clinic's calendar and needs no conversion, while
`refunded_at` is a true instant and must be resolved through the clinic's
zone before it can be compared to a day.

Every figure is **stored** on the closing, never recomputed on read. A
signed count that moves because somebody back-dated a payment into the day
is not a signed count.

## What happens when money arrives late

Reception records Friday's cash on Monday, and Friday was signed on Friday.
Three answers were possible and only one of them survives contact with a
clinic:

| Answer | Why not |
|---|---|
| Refuse the back-date | They file it under today and lie about the date. Worse than the problem. |
| Let it change the count | A signed number that moves is not a signed number, and the whole feature is the signature. |
| **Allow it, keep the count, surface the entry** | The one that is both honest and usable. |

The entry then ends one of two ways: the day is reopened and recounted, or
somebody writes down what is being done with it and it leaves the list. It
cannot simply sit there — a warning that is always on is a warning nobody
reads, which is the same failure that kills an arqueo whose difference is
never zero.

## Dependencies

`depends = ["payments"]`. The arqueo reads cash `Payment` and `Refund`
rows to compute the expected cash; it never writes there, and `payments`
knows nothing about this module. Clinic-day boundaries come from
`app.core.utils.clinic_time`, promoted out of `payments/service.py` when
this module needed the same rules.

## Scope boundary

A corte lives on the **collection axis** (gross cash in, out, counted) and
must never become a back door to the invoiced-minus-collected difference
that ADR 0010 keeps off the reports.

Two things are explicitly **out of scope**, both worth having:

- **Associate-dentist liquidation.** The highest-value thing a period cut
  could carry, and it drags its own decision — whether an associate is paid
  on work performed or on money collected — which the earned ledger alone
  cannot answer. `by_professional` splits the *earned* axis; most Mexican
  clinics pay on the collected one, and that number does not exist yet.
- **Terminal commission.** A clinic collects 10.000 by card and 9.650
  reaches the bank. Nothing here models that, so the card figures are gross
  throughout.
