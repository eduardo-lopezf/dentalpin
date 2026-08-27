# 0020 — Handler failures are recorded, not just logged

- **Status:** accepted
- **Date:** 2026-08-26
- **Deciders:** Eduardo (maintainer)
- **Tags:** events, observability, correctness

## Context

The bus catches every handler exception so one broken subscriber cannot
abort a dispatch ([ADR 0003](0003-event-bus-over-direct-imports.md) makes
handlers the only way modules react to each other, so one of them failing
must not take the others down). Until now that was the whole story: a
`logger.exception` and nothing else.

[ADR 0019](0019-events-publish-after-commit.md) made that silence
expensive. Handlers now run strictly *after* the publisher's commit, so a
swallowed failure means the fact is durable and its reaction is gone: the
invoice is issued and its VeriFactu record never written, the payment is
recorded and the recall never linked, the patient is archived and their
documents never archived. Nothing queryable says a reaction was ever
owed — which is the "looks fine, did nothing" posture the
[audit](../technical/audit-2026-07-03.md) called out as finding S5, at
the one place where it costs the most.

## Decision

**Every failed handler call becomes a row in `core_event_failure`** —
event type, handler qualified name, owning module, `clinic_id` lifted
from the payload, the payload itself, the exception and its traceback.
Admins read them at `GET /api/v1/events/failures`, gated by the new core
permission `admin.events.read` and scoped to the caller's clinic.

Recording is a diagnostic and is treated as one: `publish()` wraps the
call and logs if it fails, so a broken recorder can never become a
second way for a dispatch to die. The invariant lives at the call site,
not inside the recorder, so it holds however the recorder changes.

## Consequences

### Good

- "Did anything fail to react?" becomes a query instead of a log grep.
- The payload is kept, so a failure carries everything needed to
  reproduce or replay it by hand.
- It is the first half of a durable outbox: once failures are recorded
  and addressable, making delivery durable is a smaller step than it
  was.

### Bad / accepted trade-offs

- **No automatic retry.** Handlers are not uniformly idempotent —
  replaying `payment.recorded` into a handler that appends rows would
  double them. Retry needs a per-handler idempotency marker, and that is
  a separate decision.
- **Failures whose payload has no `clinic_id` are recorded but not
  listed.** They cannot be attributed to a tenant, and guessing would
  leak one clinic's operational detail into another's. They stay in the
  table and in the logs.
- **The table grows unbounded.** A recurring bug in a hot handler writes
  a row per event. No purge job yet; a retention policy belongs with the
  retry decision.
- The payload is coerced to JSON-safe scalars, so a non-serialisable
  value is stored as its `str()`. The record loses fidelity rather than
  being lost.

## Alternatives considered

- **Keep logging only, and lean on log aggregation.** Free, and what we
  had. Rejected: there is no aggregator in a self-hosted clinic, and the
  data an operator needs (which clinic, which payload) is exactly what a
  log line loses.
- **Re-raise from the handler and fail the request.** Impossible after
  ADR 0019 — the request has already committed and usually already
  returned — and it would let one module's bug break another module's
  endpoint, which is what the bus exists to prevent.
- **A severity flag per handler (`critical` / `best_effort`).** Without
  a retry mechanism it changes nothing but the log level, so it would be
  decoration. It arrives with retry or not at all.

## How to verify the rule still holds

- `backend/tests/test_event_failure_visibility.py` — a failing handler
  is recorded with its payload and clinic, a successful one records
  nothing, one broken subscriber does not stop the next, a broken
  recorder does not break the dispatch, and an admin can read the list.

## References

- `backend/app/core/events/bus.py` — `publish`, `_record_failure`
- `backend/app/core/events/models.py` — `EventHandlerFailure`
- `backend/app/core/events/router.py` — `GET /api/v1/events/failures`
- `backend/alembic/versions/0008_event_handler_failures.py`
- [ADR 0019](0019-events-publish-after-commit.md) — why the silence got
  expensive
- [`docs/technical/audit-2026-07-03.md`](../technical/audit-2026-07-03.md) — finding S5
