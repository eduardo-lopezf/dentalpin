"""Runtime gate for modules on their way out.

Module lifecycle transitions are restart-based: ``uninstall`` marks the
record ``to_remove`` and the lifespan processor does the work on the
next boot. That leaves a window — from the admin's click to the
restart — in which the module is still fully mounted and happily
accepting writes into tables that are about to be dropped and replaced
by a ``pg_dump`` file.

The gate closes that window. It is deliberately tiny: an in-memory set
of module names whose HTTP surface must stop answering, consulted by
one middleware. It carries no state across a restart because it does
not need to — after the restart the module is uninstalled, and the boot
sequence simply does not mount it.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1/"


class ModuleGate:
    """Names whose ``/api/v1/<name>/...`` routes must refuse traffic."""

    def __init__(self) -> None:
        self._blocked: set[str] = set()

    def block(self, name: str) -> None:
        """Stop serving ``name`` until the pending removal is resolved."""
        self._blocked.add(name)
        logger.info("Module gate closed for %s (pending removal)", name)

    def unblock(self, name: str) -> None:
        """Serve ``name`` again — the removal was cancelled or completed."""
        if name in self._blocked:
            logger.info("Module gate opened for %s", name)
        self._blocked.discard(name)

    def is_blocked(self, name: str) -> bool:
        return name in self._blocked

    def blocked(self) -> frozenset[str]:
        return frozenset(self._blocked)

    def clear(self) -> None:
        """Drop every entry. Boot and tests."""
        self._blocked.clear()

    def match(self, path: str) -> str | None:
        """Return the blocked module owning ``path``, if any.

        Module routers are always mounted at ``/api/v1/<name>``, so the
        third path segment is the module name.
        """
        if not self._blocked or not path.startswith(API_PREFIX):
            return None
        name = path[len(API_PREFIX) :].split("/", 1)[0]
        return name if name in self._blocked else None


module_gate = ModuleGate()
