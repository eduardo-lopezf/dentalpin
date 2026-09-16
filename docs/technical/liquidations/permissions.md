# Liquidations — permissions

| Permission | Gates |
|---|---|
| `liquidations.settlement.read` | `GET /commissions`, `/preview`, the list, `/{id}`, the Liquidaciones tab, and the `liquidation_preview` agent tool |
| `liquidations.settlement.issue` | `POST /api/v1/liquidations` — issuing the document somebody is paid on — and `POST /{id}/pay` / `POST /{id}/unpay` |
| `liquidations.commission.write` | `PUT /commissions/{professional_id}` — the agreed percentage and basis |

## Roles

| Role | Grants |
|---|---|
| `admin` | `*` |
| `dentist` | `settlement.read` — they can see what they are owed |
| everyone else | none |

## Notes

The three are split rather than collapsed into read/write because they
answer to different people. Seeing what you are owed is reasonable for the
associate themselves; **what the clinic pays its associates, and the act of
issuing the figure, are the owner's business**. A clinic that wants its
practice manager to issue settlements grants `settlement.issue` from the
roles UI without touching `commission.write`, and no code changes.

**Paying reuses `settlement.issue` rather than adding a fourth grant.** Both
are the owner deciding money moves, and a permission every holder of another
also holds is flexibility nobody asked for. If a clinic ever wants a manager
who can produce the document but not hand over cash, that is the moment to
split it — not before.
