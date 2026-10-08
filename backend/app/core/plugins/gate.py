"""Runtime gate for modules on their way out.

Module lifecycle transitions are restart-based: ``uninstall`` marks the
record ``to_remove`` and the lifespan processor does the work on the
next boot. That leaves a window — from the admin's command to the
restart — in which the module is still fully mounted and happily
accepting writes into tables that are about to be dropped and replaced
by a ``pg_dump`` file.

The gate closes that window. It is deliberately tiny: a set of module
names whose HTTP surface must stop answering, consulted by one
middleware. It carries no state across a restart because it does not
need to — after the restart the module is uninstalled, and the boot
sequence simply does not mount it.

It is closed from two sides, and a name on either is refused:

- **By this process**, the moment it changes a module's state
  (:meth:`ModuleGate.block`).
- **By the database**, a few seconds later at most
  (:meth:`ModuleGate.claim_sync` / :meth:`ModuleGate.apply_sync`).
  The process that changes the state is rarely the one that serves:
  ``dienteazul modules disable`` runs ``python -m app.cli`` beside the
  server, and with several backends it is whichever one the request
  reached. A gate that only its own process can close is, to every
  other process, never closed — and ``core_module.state`` is what
  decides what runs (ADR 0018), so that is what they ask.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from typing import Final

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1/"

# How stale another process's change can be here. It is the price of not
# asking the database on every request: for this long after a module is
# turned off elsewhere, this process still answers for it.
SYNC_SECONDS: Final = 5.0


class ModuleGate:
    """Names whose ``/api/v1/<name>/...`` routes must refuse traffic."""

    def __init__(self) -> None:
        self._local: set[str] = set()
        self._remote: set[str] = set()
        self._local_changes = 0
        self._next_sync = 0.0

    def block(self, name: str) -> None:
        """Stop serving ``name`` until the pending removal is resolved."""
        self._local.add(name)
        self._local_changes += 1
        logger.info("Module gate closed for %s (pending removal)", name)

    def unblock(self, name: str) -> None:
        """Serve ``name`` again — the removal was cancelled or completed."""
        if self.is_blocked(name):
            logger.info("Module gate opened for %s", name)
        self._local.discard(name)
        self._remote.discard(name)
        self._local_changes += 1

    def is_blocked(self, name: str) -> bool:
        return name in self._local or name in self._remote

    def blocked(self) -> frozenset[str]:
        return frozenset(self._local | self._remote)

    def clear(self) -> None:
        """Drop every entry. Boot and tests."""
        self._local.clear()
        self._remote.clear()
        self._local_changes += 1
        self._next_sync = 0.0

    def match(self, path: str) -> str | None:
        """Return the blocked module owning ``path``, if any.

        Module routers are always mounted at ``/api/v1/<name>``, so the
        third path segment is the module name.
        """
        if not (self._local or self._remote) or not path.startswith(API_PREFIX):
            return None
        name = path[len(API_PREFIX) :].split("/", 1)[0]
        return name if self.is_blocked(name) else None

    # --- What the database says ------------------------------------------

    def claim_sync(self) -> int | None:
        """A ticket to read the database, or ``None`` if it is not time.

        Claiming postpones the next one, so of the requests that arrive
        while a read is in flight only the first pays for it.
        """
        now = time.monotonic()
        if now < self._next_sync:
            return None
        self._next_sync = now + SYNC_SECONDS
        return self._local_changes

    def apply_sync(self, names: Iterable[str], ticket: int) -> None:
        """Take ``names`` as what the database has closed.

        Dropped if this process changed the gate since ``ticket`` was
        claimed: the read may predate that change, and applying it would
        undo for a few seconds what was just decided here. The next
        round reads again.
        """
        if ticket != self._local_changes:
            return
        closed = set(names)
        for name in sorted(closed - self._remote):
            logger.warning(
                "Module gate closed for %s: the database says it is off and this "
                "process still has it mounted. It stops at the next restart.",
                name,
            )
        for name in sorted(self._remote - closed):
            logger.info("Module gate opened for %s: the database no longer says it is off", name)
        self._remote = closed


module_gate = ModuleGate()
