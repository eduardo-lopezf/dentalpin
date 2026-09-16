# Liquidations — events

## Published

None.

`liquidation.issued` is the obvious candidate — notifications could tell an
associate their settlement is ready — but there is no subscriber today, and
the project already carries one event declared ahead of its consumers. It
goes in when something needs it.

## Consumed

None.

The module **reads** `payments` and `professionals` directly, which their
presence in `manifest.depends` allows. A settlement needs a consistent
point-in-time view of a patient's whole ledger, not a stream of individual
events, and a denormalized mirror would be one more thing that can drift
from the ledger it is supposed to settle against.
