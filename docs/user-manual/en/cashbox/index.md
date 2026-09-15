---
module: cashbox
last_verified_commit: f2ce026
---

# Till (cashbox)

The cashbox module keeps **the drawer**: the cash that enters and leaves
the clinic without being a patient payment.

It does not overlap with Payments. Payments answers "how much were we
paid"; the Till answers "what is in the drawer right now, and why". A
patient's cash payment adds to both, but the lab courier you hand 450 pesos
to never appears in Payments and empties the drawer all the same.

## What is here today

The module is complete: the movements, the daily count, the weekly,
fortnightly and monthly cuts, and the entries that arrive against a day
already counted.

What it deliberately does **not** cover: associate-dentist liquidation and
terminal commission. Both are worth having and both drag decisions of their
own.

## Screens

- [Till](./screens/cashbox.md) — a tab of Finance.
