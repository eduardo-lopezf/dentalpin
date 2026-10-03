# Presupuestos y cobros (`budgets_payments`)

- **Tier:** optional  ·  **Version:** 0.1
- **Declared in:** `backend/apps.json`  ·  **Composition and requirements:** [Apps catalog](../../apps-catalog.md)

## What it is for

Budgets (quotes) and their acceptance, collections and the patient ledger, invoices, and — in Spain — Veri*Factu and the export for the accountant.

## Modules

- [`budget`](../../technical/budget/overview.md) — code in `backend/app/modules/budget/` ([notes](../../../backend/app/modules/budget/CLAUDE.md))
- [`payments`](../../technical/payments/overview.md) — code in `backend/app/modules/payments/` ([notes](../../../backend/app/modules/payments/CLAUDE.md))
- [`billing`](../../technical/billing/overview.md) — code in `backend/app/modules/billing/` ([notes](../../../backend/app/modules/billing/CLAUDE.md))
- [`verifactu`](../../technical/verifactu/overview.md) — code in `backend/app/modules/verifactu/` ([notes](../../../backend/app/modules/verifactu/CLAUDE.md))
- [`accounting_export`](../../technical/accounting_export/overview.md) — code in `backend/app/modules/accounting_export/` ([notes](../../../backend/app/modules/accounting_export/CLAUDE.md))

## With this App off

Not verified as a whole. What is verified: its pages redirect home with a notice, and a confirmed treatment plan goes straight to *in treatment* (checked with `budget` and `payments` off).

## Notes

- Requires Patients, Treatments and Professionals.
- `verifactu` and `accounting_export` are not installed by default. `verifactu` is to be replaced by invoicing for Mexico's SAT.
- It mints, cancels and deletes a plan's budget by reacting to the plan's events (`plan_quotes.py`).

## Decisions

- [0042](../../adr/0042-core-apps-must-stay-separable.md)
