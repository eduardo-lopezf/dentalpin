# 0019 — Events are published after the transaction commits

- **Status:** accepted
- **Date:** 2026-08-26
- **Deciders:** Eduardo (maintainer)
- **Tags:** events, transactions, money, correctness

## Context

Handlers on the event bus run inline but in **their own sessions**
(`async_session_maker`), because [ADR 0003](0003-event-bus-over-direct-imports.md)
forbids reaching across module boundaries any other way. Publishers, on
the other hand, ran inside the request's transaction: the dominant shape
was `db.flush()` → `await event_bus.publish(...)`, with `get_db`
committing only at request teardown.

So handlers were told about rows no other connection could see. The
[2026-07-03 audit](../technical/audit-2026-07-03.md) (finding S2) traced
three shapes of damage:

- **Wrong state, silently.** `payments.refund_payment` flushed the
  `Refund` and published; `billing.on_payment_refunded` recomputed the
  invoice in a fresh session where that refund did not exist, concluded
  nothing had changed, and left the invoice **`paid` after a full
  refund**. Reproduced deterministically in
  `tests/modules/billing/test_refund_invoice_status.py`.
- **Failed or blocked writes.** A handler setting an FK to a
  flushed-but-uncommitted appointment either violates the constraint or
  waits on the publisher's row lock.
- **Phantom rows.** A handler commits its own work in its own session;
  the publisher's transaction later rolls back. The consequence outlives
  the cause.

`verifactu`, `copilot`, `notifications` and `migration_import` already
committed before publishing, with comments explaining why — the correct
pattern was known, but nothing made it the default.

## Decision

**An event is announced only once the fact it describes has committed.**

Publishers inside a transaction call
`event_bus.publish_after_commit(db, event_type, payload)`, which queues
the event on `Session.info`. `UnitOfWorkSession` — the session class
behind `async_session_maker` — drains that queue after `commit()`
succeeds and discards it on `rollback()`. Dispatch preserves publish
order, and the queue is popped before dispatching so a handler that
commits the same session cannot replay it.

`publish_after_commit` is deliberately **not** a coroutine: nothing is
dispatched at the call site, and a leftover `await` should fail loudly.

Direct `await event_bus.publish(...)` remains correct for callers that
have already committed — background workers that own their session, and
`/auth/setup`, which must await its handlers before returning tokens.
`tests/test_event_transaction_boundary.py` holds the allowlist of files
allowed to do it; every other publish must defer.

## Consequences

### Good

- Handlers see the data they are told about. The refund case is fixed,
  and the FK/lock cases stop being possible.
- The rule is enforced by the session, not by discipline at 80 call
  sites, and the allowlist test catches new violations.
- A rolled-back request announces nothing — the bus stops being a
  channel through which failed work leaks.

### Bad / accepted trade-offs

- **In-process and non-durable.** A crash between the commit and the
  dispatch loses those events. A durable outbox table with a dispatcher
  is the next step up; it needs at-least-once semantics and idempotent
  handlers, so it is a separate decision. This closes the correctness
  hole without a new table.
- **Handlers no longer run before the response is built** for
  request-scoped publishes: they run at `get_db`'s commit, during
  teardown. A publisher can no longer read what a handler wrote in the
  same request — nothing did, and relying on it was the bug.
- Handler failures now happen strictly after the commit, so they can no
  longer fail the request. They never could — the bus swallows handler
  exceptions — but that makes handler-failure visibility (audit S5) more
  load-bearing, not less.
- The test suite's `get_db` override now commits, like production. That
  makes tests exercise the real boundary; it also means a request's
  writes are durable mid-test.

## Alternatives considered

- **`db.commit()` before each publish, at every call site.** What the
  four correct modules already did. Rejected as the general rule: it
  splits a request into several transactions, so a later failure leaves
  half the work committed — trading a visibility bug for an atomicity
  bug.
- **A durable outbox table drained by a poller.** The right end state
  for crash-safety and multi-process deployments, and a much larger
  change (table, migration, dispatcher, ordering, retries, idempotency).
  Deferred deliberately; this ADR is the step that stops the bleeding.
- **SQLAlchemy's `after_commit` event.** It is synchronous; our handlers
  are coroutines. Scheduling them as tasks from there would make
  dispatch concurrent with the rest of the request and untestable
  without sleeps.
- **A ContextVar holding "the current request's session"** so
  `publish()` could stay unchanged at all 80 sites. Rejected: implicit,
  and wrong for handlers and background tasks that own their session.

## How to verify the rule still holds

- `backend/tests/test_event_transaction_boundary.py` — the allowlist,
  the queue-drains-on-commit / drops-on-rollback behaviour, and a
  handler asserting visibility from a second session.
- `backend/tests/modules/billing/test_refund_invoice_status.py` — the
  audit's money case, end to end over HTTP.

## References

- `backend/app/database.py` — `UnitOfWorkSession`
- `backend/app/core/events/bus.py` — `publish_after_commit`,
  `dispatch_pending`, `discard_pending`
- `backend/app/modules/payments/workflow.py` — the refund publisher
- `backend/app/modules/billing/events.py` — `on_payment_refunded`
- [`docs/technical/audit-2026-07-03.md`](../technical/audit-2026-07-03.md) — finding S2
- [ADR 0003](0003-event-bus-over-direct-imports.md) — why handlers have
  their own sessions in the first place
