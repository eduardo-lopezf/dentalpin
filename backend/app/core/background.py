"""Fire-and-forget work the process still keeps track of.

A handler that must not hold up the request — sending an email, calling a
vendor — schedules its own task (see the event bus contract). Two things
go wrong when that is a bare ``asyncio.create_task``:

- **Nothing holds the task.** The loop keeps only a weak reference, so a
  task can be garbage-collected mid-flight and the work simply never
  happens, with no error anywhere.
- **Nothing can wait for it.** The test suite drops every table between
  tests, and a straggler still writing through its own session deadlocks
  against that ``DROP TABLE`` — which is how four odontogram tests died
  on CI, two of them only because the failed teardown left the previous
  test's rows behind.

``spawn`` keeps the reference until the task finishes; ``drain`` is for
the suite, which waits for the stragglers before pulling the schema out
from under them.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)

_tasks: set[asyncio.Task[Any]] = set()


def spawn(coro: Coroutine[Any, Any, Any], *, name: str | None = None) -> asyncio.Task[Any]:
    """Run ``coro`` detached from the caller, holding a reference to it."""
    task = asyncio.create_task(coro, name=name)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return task


def pending() -> frozenset[asyncio.Task[Any]]:
    """The spawned tasks that have not finished."""
    return frozenset(task for task in _tasks if not task.done())


async def drain(timeout: float = 30.0) -> None:
    """Wait for the spawned tasks, for callers that own the database.

    Returns when they are done or when ``timeout`` runs out; a task that
    overruns is reported, not cancelled — cancelling it mid-write would
    trade a slow teardown for a torn one.
    """
    outstanding = pending()
    if not outstanding:
        return
    _, still_running = await asyncio.wait(outstanding, timeout=timeout)
    if still_running:
        logger.warning(
            "background tasks still running after %.0fs: %s",
            timeout,
            [task.get_name() for task in still_running],
        )
