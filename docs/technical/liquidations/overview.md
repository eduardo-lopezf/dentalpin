# Liquidations — overview

Settling with associate dentists. The highest-value thing left over from the
cashbox work, and the one that dragged a decision of its own.

## The decision, and why it was not answered with one axis

An associate on a percentage is paid from one of two figures:

| | What it is | Who carries the collection risk |
|---|---|---|
| **earned** | The work performed, priced | The clinic |
| **collected** | What the patient actually paid for that work | Shared with the associate |

They are the same number only in a clinic where everybody pays on the day.
On a 19.000 MXN orthognathic case they are months apart.

The module computes **both** and records, per professional, which one the
percentage is taken on. `collected` is the default because it is the norm in
Mexico and because a clinic paying on `earned` is distributing money it has
not received — but both are shown on every surface, because a clinic that
cannot see the gap cannot judge either figure.

## Attribution

There is no foreign key from a `Payment` to the work it pays for. `payments`
settles the two FIFO: a patient's money covers their oldest charges first,
and the order is the only thing that assigns it. `PatientEarnedEntry`
carries `professional_id`, so projecting that walk onto the entries is what
attributes collected money to the person who earned it.

`LedgerService.coverage_by_earned_entry` is that projection, and it lives in
`payments` beside its two siblings for the reason that module's own notes
give: **the walk has one home**. It runs over every entry of each patient,
not only the ones belonging to the professional being settled with —
otherwise money already consumed by older work would be credited twice.

## Preview and document

A preview recalculates on every read, which is right while nobody has been
paid. Issuing copies the lines, the percentage and the basis onto a
`Liquidation` row and the figures stop moving: a patient paying tomorrow for
work done last fortnight must not change what somebody was already paid.

The arrangement itself stays mutable for exactly that reason. Same shape as
the arqueo in `cashbox` — the document is the record, the setting is only
where the next one starts.

## Paying it

`POST /{id}/pay` records the payout and, for a cash one, writes the till
movement in `cashbox` **in the same transaction**.

That is a direct call and the event bus was the wrong answer. ADR 0003 makes
events the default for cross-module *reactions*, but the payout and the till
movement are not two events — they are one fact seen twice. A handler running
after the commit can fail, the bus records it and never retries, and what
that leaves is a settlement reading *paid* with no money out of the drawer:
the exact silent divergence the cashbox work exists to prevent. The precedent
is `treatment_plan.confirm()` calling into `budget` synchronously, documented
there as the carve-out.

Only cash touches the drawer. A transfer reaches the associate's bank without
the till opening, and inventing a movement for it would make the next arqueo
short by the whole payout.

Undoing exists — an irreversible mistaken payout is what makes people stop
trusting a screen — and stops where the till stops it: once the day has been
counted, the way back is to reopen it.

## Not covered

- **Per-discipline percentages.** 40 % on orthodontics and 50 % on surgery
  is a real arrangement. The extension point is a child table keyed on the
  catalog category; nothing in the current model has to change for it.
- **Terminal commission.** Card figures are gross throughout the project.
