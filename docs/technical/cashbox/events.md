# Cashbox — events

## Published

None.

`cashbox.closed` is the obvious candidate once the arqueo lands in phase 2,
and it is deliberately not declared yet: there is no subscriber, and the
codebase already carries one event declared ahead of its consumers
(`treatment_plan.status_changed`). It will be added when notifications or
reporting actually needs it.

## Consumed

None.

The module **reads** `payments` rows directly — allowed, because `payments`
is in `manifest.depends` — rather than mirroring them through the bus. The
arqueo needs a consistent point-in-time total of the day's cash, not a
stream of individual events, and a denormalized copy would be one more
thing that can drift from the ledger it is supposed to count.
