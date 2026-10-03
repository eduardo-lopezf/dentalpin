# Caja (`cash`)

- **Tier:** optional  ·  **Version:** 0.1
- **Declared in:** `backend/apps.json`  ·  **Composition and requirements:** [Apps catalog](../../apps-catalog.md)

## What it is for

The cash desk: cash movements, the daily count, period cuts, and payouts to associate professionals.

## Modules

- [`cashbox`](../../technical/cashbox/overview.md) — code in `backend/app/modules/cashbox/` ([notes](../../../backend/app/modules/cashbox/CLAUDE.md))
- [`liquidations`](../../technical/liquidations/overview.md) — code in `backend/app/modules/liquidations/` ([notes](../../../backend/app/modules/liquidations/CLAUDE.md))

## With this App off

Not verified.

## Notes

- Requires Budgets & payments (it counts what `payments` collected) and Professionals (payouts).
