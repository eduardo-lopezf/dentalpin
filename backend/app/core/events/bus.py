"""Event bus for cross-module communication."""

import asyncio
import inspect
import json
import logging
import traceback
from collections.abc import Callable
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], None]

PENDING_EVENTS_KEY = "_pending_events"
"""Key under which queued events live in ``Session.info``."""


def _jsonable(data: dict[str, Any]) -> dict[str, Any]:
    """Coerce a payload into something JSONB will accept.

    Payloads are meant to be plain JSON already; this is the guard for
    the one that is not, so a bad value costs the record its fidelity
    rather than costing us the record.
    """
    safe: dict[str, Any] = {}
    for key, value in data.items():
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            safe[str(key)] = str(value)
        else:
            safe[str(key)] = value
    return safe


class EventBus:
    """Event bus with async handler support.

    Modules can subscribe to events and publish events.
    Supports both sync and async handlers. Handlers run inline — a
    publisher that ``await``s ``publish()`` is guaranteed every
    subscriber has finished before the call returns. Handler
    exceptions are caught and logged so one broken subscriber cannot
    fail another, but the publisher sees a clean return.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}

    def subscribe(self, event_type: str, handler: Handler) -> None:
        """Subscribe a handler to an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"Handler subscribed to event: {event_type}")

    def unsubscribe(self, event_type: str, handler: Handler) -> None:
        """Unsubscribe a handler from an event type."""
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass

    async def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish an event and await every subscriber to completion.

        Sync handlers run inline; async handlers are awaited in order.
        Handler exceptions are caught and logged — one failing
        subscriber does not abort the rest, and the publisher sees a
        clean return. The contract is: "after ``await``, every handler
        has finished (or failed)."

        Handlers that need fire-and-forget (e.g. an SMTP call that
        should not block the request) are responsible for scheduling
        their own background task internally.
        """
        logger.info(f"Event published: {event_type}", extra={"event_data": data})

        for handler in self._handlers.get(event_type, []):
            try:
                result = handler(data)
                if inspect.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.exception(
                    "Event handler %s failed for %s",
                    getattr(handler, "__qualname__", handler.__name__),
                    event_type,
                    extra={
                        "event_type": event_type,
                        "clinic_id": data.get("clinic_id"),
                    },
                )
                try:
                    await self._record_failure(event_type, handler, data, exc)
                except Exception:
                    # Recording is a diagnostic; it must never become a
                    # second way to fail. Guarding here rather than inside
                    # the recorder keeps the invariant true no matter how
                    # the recorder changes.
                    logger.exception(
                        "Could not record the failure of %s for %s — that failure now "
                        "exists only in this log",
                        getattr(handler, "__qualname__", getattr(handler, "__name__", handler)),
                        event_type,
                    )

    # --- Deferred publication ------------------------------------------

    def publish_after_commit(
        self,
        session: Any,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Queue an event to fire once ``session``'s transaction commits.

        Handlers run in their **own** sessions, so anything published
        from inside an open transaction is announced against a database
        where the change does not exist yet: the publisher had only
        ``flush()``ed. That is audit finding S2 — a refund whose invoice
        stays ``paid``, a handler that sets an FK to a row nobody else
        can see, a handler that commits work a later rollback then
        contradicts.

        Queuing on ``session.info`` ties the event to the transaction
        that makes it true. :class:`~app.database.UnitOfWorkSession`
        drains the queue after ``commit()`` and drops it on
        ``rollback()``, so an event is announced exactly when — and only
        if — the fact it describes became real.

        Deliberately not a coroutine: ``await``ing it is a mistake worth
        failing loudly on, since nothing is dispatched here.
        """
        session.info.setdefault(PENDING_EVENTS_KEY, []).append((event_type, data))
        logger.debug("Event queued until commit: %s", event_type)

    async def dispatch_pending(self, session: Any) -> None:
        """Publish everything ``session`` queued, in publish order."""
        pending = session.info.pop(PENDING_EVENTS_KEY, None)
        if not pending:
            return

        # Popped before dispatching: a handler that commits this same
        # session (or a publisher re-entering) must not replay the queue.
        for event_type, data in pending:
            await self.publish(event_type, data)

    def discard_pending(self, session: Any) -> None:
        """Drop the queue — the transaction did not happen."""
        dropped = session.info.pop(PENDING_EVENTS_KEY, None)
        if dropped:
            logger.info(
                "Discarded %d queued event(s) after rollback: %s",
                len(dropped),
                [event_type for event_type, _ in dropped],
            )

    # --- Failure visibility --------------------------------------------

    async def _record_failure(
        self,
        event_type: str,
        handler: Handler,
        data: dict[str, Any],
        exc: BaseException,
    ) -> None:
        """Persist one failed handler call to ``core_event_failure``.

        A swallowed handler exception used to leave nothing but a log
        line. Handlers run after the publisher's commit (ADR 0019), so
        the fact survives and its reaction does not — this row is what
        makes that owed reaction findable.

        Raises on failure; :meth:`publish` decides what that means, and
        it means "log it and keep dispatching".
        """
        from app.core.events.models import ERROR_MAX, TRACEBACK_MAX, EventHandlerFailure
        from app.database import async_session_maker

        clinic_id: UUID | None = None
        raw_clinic = data.get("clinic_id")
        if raw_clinic:
            try:
                clinic_id = UUID(str(raw_clinic))
            except (ValueError, TypeError):
                # An unattributable failure is still worth recording.
                clinic_id = None

        module = getattr(handler, "__module__", "") or ""
        module_name = module.split(".")[2] if module.startswith("app.modules.") else None
        qualname = getattr(handler, "__qualname__", getattr(handler, "__name__", "?"))

        async with async_session_maker() as session:
            session.add(
                EventHandlerFailure(
                    event_type=str(event_type),
                    handler=f"{module}.{qualname}"[:255],
                    module=module_name,
                    clinic_id=clinic_id,
                    payload=_jsonable(data),
                    error=f"{type(exc).__name__}: {exc}"[:ERROR_MAX],
                    traceback="".join(
                        traceback.format_exception(type(exc), exc, exc.__traceback__)
                    )[-TRACEBACK_MAX:],
                )
            )
            await session.commit()

    def publish_sync(self, event_type: str, data: dict[str, Any]) -> None:
        """Sync entry point for non-async callers (scripts, REPL).

        Avoid in production code — it spins up a fresh loop with
        ``asyncio.run`` and will fail inside an already-running loop.
        Always prefer ``await event_bus.publish(...)`` from async
        contexts.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.publish(event_type, data))
            return
        raise RuntimeError(
            "publish_sync called from a running event loop — use "
            "'await event_bus.publish(...)' instead."
        )

    def clear(self) -> None:
        """Remove all handlers. Useful for testing."""
        self._handlers.clear()


# Global singleton instance
event_bus = EventBus()
