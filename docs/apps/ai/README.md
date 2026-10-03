# IA (`ai`)

- **Tier:** optional  ·  **Version:** 0.1
- **Declared in:** `backend/apps.json`  ·  **Composition and requirements:** [Apps catalog](../../apps-catalog.md)

## What it is for

The clinic's AI assistant, limited to what the person asking is allowed to see.

## Modules

- [`copilot`](../../technical/copilot/overview.md) — code in `backend/app/modules/copilot/` ([notes](../../../backend/app/modules/copilot/CLAUDE.md))

## With this App off

Verified on 2026-10-03: the IA menu entry and the assistant launcher go, `/copilot` sends the visit home with the notice "La app IA no está habilitada", and the home page makes no failed call.

## Notes

- Requires no other App: it works with the tools the running modules expose.
