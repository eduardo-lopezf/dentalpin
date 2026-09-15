# Cashbox — permissions

| Permission | Gates |
|---|---|
| `cashbox.movement.read` | `GET /api/v1/cashbox/movements`, `GET /api/v1/cashbox/movements/totals`, `GET /api/v1/cashbox/movements/{id}`, the **Caja** tab in Finanzas, and both agent tools (`cash_movements`, `cash_movements_day_totals`) |
| `cashbox.movement.write` | `POST /api/v1/cashbox/movements`, `PUT /api/v1/cashbox/movements/{id}`, `DELETE /api/v1/cashbox/movements/{id}` |
| `cashbox.closing.read` | `GET /api/v1/cashbox/position`, `/closings`, `/closings/{id}`, `/periods`, `/late-entries`, the arqueo, period and late-entry cards, and the `cash_closings` / `cash_period_summary` agent tools |
| `cashbox.closing.write` | `POST /api/v1/cashbox/closings` — counting the drawer and closing the day — and `POST /api/v1/cashbox/late-entries/acknowledge` |
| `cashbox.closing.reopen` | `POST /api/v1/cashbox/closings/{id}/reopen` |

## Roles

| Role | Grants |
|---|---|
| `admin` | `*` — the only role with `closing.reopen` |
| `receptionist` | movement read+write, closing read+write — they are who opens the drawer and counts it |
| `assistant` | movement read+write, closing read |
| `dentist` | movement read+write, closing read+write |
| `hygienist` | none — no business at the till |

**Acknowledging a late entry is `closing.write`, not `closing.reopen`.**
Deciding that money written against a counted day rolls into the next count
is reception's call and changes nothing that was signed. Reopening the day
is the other answer to the same situation, and that one is not theirs.

**`closing.reopen` is deliberately admin-only.** Reopening throws away a
count somebody made and signed off, the same way reopening a plan throws
away a budget the patient may have seen — and `treatment_plan` narrows that
one for the same reason. A clinic that wants reception to be able to
recount can grant it from the roles UI; no code change needed.

## Notes

`movement.write` does **not** imply the ability to change a movement whose
day is closed. That refusal lives in `MovementService`, not in RBAC: it is
a property of the row's state, not of who is asking, and putting it in the
service is what makes the agent tools inherit it.
