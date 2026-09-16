---
module: liquidations
screen: liquidations
route: /finanzas?tab=liquidations
related_endpoints:
  - GET /api/v1/liquidations
  - GET /api/v1/liquidations/preview
  - GET /api/v1/liquidations/commissions
  - GET /api/v1/liquidations/{liquidation_id}
  - POST /api/v1/liquidations
  - POST /api/v1/liquidations/{liquidation_id}/pay
  - POST /api/v1/liquidations/{liquidation_id}/unpay
  - PUT /api/v1/liquidations/commissions/{professional_id}
related_permissions:
  - liquidations.settlement.read
  - liquidations.settlement.issue
  - liquidations.commission.write
related_paths:
  - backend/app/modules/liquidations/frontend/components/finance/LiquidationsTab.vue
  - backend/app/modules/liquidations/router.py
  - backend/app/modules/liquidations/service.py
last_verified_commit: 934bc23
---

# Settlements

> **Where it is.** The **Liquidaciones** tab of **Finanzas**, the last one.
> It only appears when the module is installed.

This is where an associate dentist is settled with for a period. The period
defaults to the **calendar quincena** — the 1st to the 15th, or the 16th to
the end of the month — because that is when payroll is paid, and it can be
changed.

## The two figures

- **Earned**: the work they did in the period, priced. Paid for or not.
- **Collected**: what the patient has already paid **for that work**.

The blue outline marks which of the two the percentage is taken on. Below,
line by line, each treatment with what it earned and what has been collected
for it; **amber marks what is not yet fully collected**.

> **How the app knows which payments belong to which work.** A payment does
> not point at a treatment: a patient's money covers their oldest charges
> first. So if a patient owed for earlier work, what they pay today goes to
> that work before it reaches the period you are settling — even when
> somebody else did it.

## The arrangement

> Requires `liquidations.commission.write`.

**Change the arrangement** opens the percentage and the basis: *on
collected* or *on earned*. It can be changed whenever needed; **settlements
already issued keep the percentage they were made with**, so renegotiating
in March does not touch January.

While no arrangement is recorded the screen says so in amber and will not
issue. The work figures are real regardless: what is missing is the share,
not the data.

## Issuing

> Requires `liquidations.settlement.issue`.

**Issue the settlement** freezes the figures. From then on, what the patient
pays afterwards does not change what was settled — which is the point: it is
the number somebody was paid on.

A period is settled once per professional. If it is already done, the header
says so and the button disappears.

## Paying the settlement

> Requires `liquidations.settlement.issue`, the same permission as issuing.

Issuing says what is owed; **Pay** hands it over. They are two acts because
they happen at different moments: the quincena closes on the 15th and the
associate is paid when they come in.

**Pay in cash and the till movement writes itself.** There is no going to the
Caja tab to type the figure: it appears there as *Professional payout*, with
the name and the period in the concept, and the day's arqueo already counts
it. Somebody copying 699 by hand is exactly how a till stops balancing.

**A transfer never touches the drawer.** The money reaches the associate's
bank without the till opening, and recording a movement for it would leave
the arqueo short by the whole payout.

A paid settlement is marked in green with how it was paid, with the **undo**
arrow beside it.

## Undoing a payment

If the payment was recorded by mistake, the arrow undoes it and **takes the
till movement with it**.

It stops being possible once the day has been counted: that movement is
inside a number somebody counted and signed. The way then is to reopen the
day from the Caja tab, undo, and count again.

> A payout movement **cannot be edited or deleted from Caja**. Trying tells
> you to undo it from the settlement — the only way the two cannot end up
> contradicting each other.

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| See the tab and the settlements | `liquidations.settlement.read` |
| Issue a settlement, pay it and undo the payment | `liquidations.settlement.issue` |
| Change the agreed percentage | `liquidations.commission.write` |

A dentist can see what they are owed. **What the clinic pays its associates,
and issuing the figure, belong to administration.**

## Troubleshooting

- **I cannot see the tab.** The module is optional: install it from
  Settings → Modules. If it is installed, your role lacks `settlement.read`.
- **Everything reads zero.** Check the period, and that the work is marked
  as performed: a settlement reads the earned ledger, which only exists once
  a treatment is carried out.
- **Collected is far below earned.** That is information, not an error: the
  work has not been paid for yet. The amber lines say which.
- **It will not let me issue.** Either the arrangement with that
  professional is not recorded, or the period is already settled.
