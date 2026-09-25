---
module: cashbox
screen: cashbox
route: /finanzas?tab=cashbox
related_endpoints:
  - GET /api/v1/cashbox/movements
  - GET /api/v1/cashbox/position
  - GET /api/v1/cashbox/periods
  - GET /api/v1/cashbox/late-entries
  - POST /api/v1/cashbox/late-entries/acknowledge
  - GET /api/v1/cashbox/closings
  - GET /api/v1/cashbox/closings/{closing_id}
  - POST /api/v1/cashbox/closings
  - POST /api/v1/cashbox/closings/{closing_id}/reopen
  - GET /api/v1/cashbox/movements/totals
  - GET /api/v1/cashbox/movements/{movement_id}
  - POST /api/v1/cashbox/movements
  - PUT /api/v1/cashbox/movements/{movement_id}
  - DELETE /api/v1/cashbox/movements/{movement_id}
related_permissions:
  - cashbox.movement.read
  - cashbox.movement.write
  - cashbox.closing.read
  - cashbox.closing.write
  - cashbox.closing.reopen
related_paths:
  - backend/app/modules/cashbox/frontend/components/finance/CashboxTab.vue
  - backend/app/modules/cashbox/frontend/components/CashMovementModal.vue
  - backend/app/modules/cashbox/frontend/components/CashClosingCard.vue
  - backend/app/modules/cashbox/frontend/components/CashPeriodCard.vue
  - backend/app/modules/cashbox/frontend/components/CashLateEntriesCard.vue
  - backend/app/modules/cashbox/router.py
last_verified_commit: 75cd119
---

# Till

> **Where it is.** The **Caja** tab of **Finanzas**, between Payments and
> Budgets.

This is where the cash entering or leaving the drawer is recorded **when it
is not a patient payment**: what is handed to the lab courier, supplies
bought with drawer money, an advance to someone on the team, what is taken
to the bank, change added to or removed from the float.

## At a glance

- **You work one day at a time.** The picker at the top chooses the day and
  everything else on screen belongs to it. A drawer is counted per day, so
  there is no date range.
- **In and out are shown apart, never added together.** A day of 5,000 in
  and 5,000 out is not a quiet day, and one net figure would tell both as
  zero. That is why the net also carries the movement count.
- **Patient payments are not recorded here.** They go under Payments, and
  the arqueo will read them from there when it arrives.

## Recording a movement

> Requires `cashbox.movement.write`.

1. **Record movement**.
2. **Direction**: *Money out* (the usual case) or *Money in*.
3. **Amount**, always positive. The direction carries the sign, not the
   number.
4. **Date**: the day it belongs to. Prefilled with the day you are viewing.
5. **Category**: Lab, Supplies, Advance, Professional payout, Bank deposit,
   Float adjustment or Other. *Professional payout* is written by the
   Settlements tab when an associate is paid in cash, and those rows are
   not editable here. The list is short on purpose so nobody has to think at the
   counter; the detail goes in the concept.
6. **Concept**, required. It is what makes the row readable three months
   from now: "nitrile gloves, pharmacy on the corner" says something
   "Supplies" alone does not.
7. **Reference**, optional: ticket or invoice number.

### Method: not everything leaves the drawer

**Method** comes set to *Cash*, which is how most of a day's money leaves.
But a clinic pays its lab by transfer, its rent by direct debit and its
supplier on thirty days, and none of that passes through a drawer. **There
was nowhere to write it down**, so no figure in the system was ever an
outflow — every one of them was an inflow.

Now it goes here, under the method it really used. What the choice changes:

| | Cash | Transfer, card, direct debit, other |
|---|---|---|
| Counts in the day's total | yes | yes |
| **Counts in the arqueo** | **yes** | **no** |
| Frozen when the day closes | yes | no, still correctable |

The form says so as soon as you pick a non-cash method, and in the list the
row carries the method's name — cash rows do not, because writing "cash" on
every row of a till would be noise.

Under the day's totals, and **only when they differ**, a line reads
*"4,200.00 MXN never passed through the drawer, so the count does not see
it"*. That sentence is what saves half an hour hunting a discrepancy that
is not there.

## Correcting or removing

The pencil corrects the row and the bin removes it, **while the day is
still open**. Anything can be changed, the date included: filing a movement
on the wrong day is the commonest correction there is, and it should not
force a delete and a retype.

Once the arqueo lands and someone closes the day, **the cash rows** become
part of a count a person made and signed off: the row is marked **Day
closed** and loses its controls. Changing it will mean reopening the day,
which will be administration's call.

Non-cash rows **stay correctable**. The closing states what was in the
drawer, and freezing the rent because somebody counted Tuesday's notes
would block a typo's correction for a reason that has nothing to do with
it.

## The count

> Requires `cashbox.closing.write`.

The **Till count** card, below the movements, is where the day is closed.
Before you count it shows **the workings** — opening float, cash collected,
cash refunded, movements in and out — but **not the total they add up to**.
That is deliberate: if the screen says "you should have 4,350" and then asks
you to count, 4,350 is what gets typed, the difference is zero every day,
and a year of counts has nothing in it worth looking at.

1. **Count the drawer**.
2. **Opening float**: what was in the drawer at opening. Carried from the
   last count; change it if that is not what was there.
3. **Counted**: count the drawer and type what is there. The moment you
   type a number the **expected** figure and the **difference** appear.
4. **What happened**: required if the count does not match. Money over is
   as much a sign as money short.
5. **Left for tomorrow**: the float you leave. The rest comes out of the
   drawer, and that float becomes the next count's opening.
6. **Close the day**.

Only **cash** is counted. What came in by card or transfer is shown
separately, as information: a card batch reconciles against the terminal
itself and a transfer reaches the bank on its own. Putting all three in one
count is the quickest way to make the whole thing useless.

A refund handed back in cash empties the drawer even when the original
payment was by card, so it counts; a cash payment refunded by transfer does
not.

## Reopening a day

> Requires `cashbox.closing.reopen`, which by default only administration
> has.

Reopening sets the count aside and makes the day's movements editable
again. It asks for a reason, and **the previous count is not deleted**: it
stays in the history beside the new one. That is deliberate — 20 pesos
short on a Tuesday is noise, 500 short every Friday is a signal, and
deleting the old count would erase exactly that evidence.

## The period cut

> Requires `cashbox.closing.read`.

The **Period cut** card at the bottom of the tab summarises the **week**,
**fortnight** or **month** containing the day you are viewing. The fortnight
is a calendar one: the 1st to the 15th and the 16th to the end of the month,
which is how payroll is paid.

What matters on this card is not the totals but the amber line: **"N day(s)
still to count"**, with the days listed. Those are days where money moved in
the drawer and nobody counted it, and **their amounts are not in the totals**
above. A cut built by adding up payments would look complete even if nobody
had counted anything all fortnight; this one is built from the counts
precisely so it can say otherwise.

A day only joins that list if cash actually moved: cash collected, cash
refunded, or a till movement. A card-only day never touches the drawer, and
a closed Sunday does not appear.

**The period difference is signed and summed.** If one day was 50 short and
the next 50 over, the fortnight genuinely balances — which is why "N day(s)
did not match" sits underneath, and that is the number worth watching. The
list below gives the day-by-day detail with its explanation: a single
difference is noise, the pattern is the information.

## Entries after the count

> Requires `cashbox.closing.read` to see them and `cashbox.closing.write` to
> note them.

Reception writes down Friday's cash on Monday, and Friday had already been
counted. **This is allowed** — forbidding it would only get the money filed
under today — and Friday's count **does not move**: that is what signing it
means. What happens instead is that this card appears.

It shows in amber, with what the entries come to and one line each: the day
they belong to, what they are (cash collection, refund or till movement) and
the amount, signed by its effect on the drawer. **When there is nothing, the
card is not there**; a card that is almost always empty teaches people to
skip the place the warning will appear.

Each entry ends one of two ways:

- **Reopen the day and count it again**, from the arqueo card. Counted
  afresh with the entry in it, there is nothing pending.
- **Note what is being done with it.** It asks for text, and that text is
  required — "seen" is not a decision anybody can act on three months from
  now — and the entry leaves the list. It is not deleted: who noted it and
  when stay with it.

A card payment never appears here: it never entered the drawer, so the count
it missed was not about it.

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| See the tab and its movements | `cashbox.movement.read` |
| Record, correct and remove movements | `cashbox.movement.write` |
| See the count, the history and the period cut | `cashbox.closing.read` |
| Count the drawer and close the day | `cashbox.closing.write` |
| Reopen an already closed day | `cashbox.closing.reopen` |

Reception counts and closes — they are who opens the drawer. **Reopening is
not theirs**, because it throws away a count somebody signed. Hygienists
have none of them.

## Troubleshooting

- **I cannot see the Caja tab.** Your role lacks `cashbox.movement.read`.
- **The amount will not take a negative number.** Deliberate: switch the
  direction to *Money out* instead. A negative number in a till listing
  reads as a correction, not as money going out.
- **It will not let me save.** The concept is missing or the amount is
  zero. The button lights up when both are there.
- **A movement is on the wrong day.** Open it with the pencil and change
  the date; there is no need to delete it.
