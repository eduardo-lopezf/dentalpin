"""Module registry for tracking discovered and installed modules.

Two distinct facts live here, and conflating them is audit finding S1:

* **discovered** — the module's code is importable and its manifest is
  readable. Says nothing about whether it should run.
* **installed** — ``core_module.state`` says the module is live, so the
  loader mounted its router, subscribed its event handlers and
  registered its copilot tools.

Discovery is a filesystem/entry-point fact; install state is a database
fact. Everything user-facing (permissions, navigation, scheduled jobs,
``modules_enabled``) must read the *installed* set — hence
:meth:`list_modules` returns active modules only, and callers that
genuinely need the full inventory (the admin UI, the CLI, the lifecycle
processor) ask for :meth:`list_discovered`.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseModule

logger = logging.getLogger(__name__)


class ModuleRegistry:
    """Registry that tracks discovered modules and which ones are active."""

    def __init__(self) -> None:
        self._modules: dict[str, BaseModule] = {}
        self._active: set[str] = set()

    # --- Discovery ------------------------------------------------------

    def register(self, module: "BaseModule") -> None:
        """Record a discovered module instance.

        Registration alone grants nothing: the module contributes no
        permissions, no jobs and no routes until :meth:`activate` marks
        it installed.
        """
        if module.name in self._modules:
            raise ValueError(f"Module '{module.name}' is already registered")
        self._modules[module.name] = module
        logger.info(f"Registered module: {module.name} v{module.version}")

    def get(self, name: str) -> "BaseModule | None":
        """Get a discovered module by name, or None if not found."""
        return self._modules.get(name)

    def is_discovered(self, name: str) -> bool:
        """True when the module's code is present and importable."""
        return name in self._modules

    def list_discovered(self) -> list["BaseModule"]:
        """Every module found on disk, whatever its install state."""
        return list(self._modules.values())

    # --- Activation -----------------------------------------------------

    def activate(self, name: str) -> None:
        """Mark a discovered module as installed and live."""
        if name not in self._modules:
            raise ValueError(f"Cannot activate unknown module '{name}'")
        self._active.add(name)
        self._invalidate_permission_cache()

    def deactivate(self, name: str) -> None:
        """Mark a module as no longer live (uninstall / disable)."""
        self._active.discard(name)
        self._invalidate_permission_cache()

    def is_installed(self, name: str) -> bool:
        """True when the module is installed *and* mounted in this process."""
        return name in self._active

    def is_loaded(self, name: str) -> bool:
        """Deprecated alias for :meth:`is_installed`.

        The old name meant "discovered" but every caller used it to mean
        "installed" — the S1 ambiguity. Kept as the safe reading.
        """
        return self.is_installed(name)

    # --- Active view ----------------------------------------------------

    def list_modules(self) -> list["BaseModule"]:
        """Installed modules only — the set the app should behave as if it has."""
        return [self._modules[name] for name in self._modules if name in self._active]

    def get_all_permissions(self) -> list[str]:
        """All permissions from *installed* modules, fully namespaced.

        Each permission is prefixed with the module name:
        'patients.read' from 'clinical' module becomes 'clinical.patients.read'
        """
        permissions: list[str] = []
        for module in self.list_modules():
            for perm in module.get_permissions():
                permissions.append(f"{module.name}.{perm}")
        return permissions

    # --- Internals ------------------------------------------------------

    def _invalidate_permission_cache(self) -> None:
        # Local import: the auth package imports plugin models transitively.
        from app.core.auth.permissions import invalidate_role_permissions_cache

        invalidate_role_permissions_cache()


# Global singleton instance
module_registry = ModuleRegistry()
