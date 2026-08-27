"""Module discovery and loading.

Discovery happens in two stages:

1. **Entry points** — the primary mechanism. Modules (internal or
   third-party) declare an entry point in the ``dentalpin.modules``
   group. This is how published PyPI packages plug in without any
   filesystem layout assumptions.

2. **Filesystem scan** — a dev-mode fallback that walks
   ``backend/app/modules/`` and imports any package containing a
   ``BaseModule`` subclass. Controlled by
   ``settings.DENTALPIN_DEV_MODULE_SCAN``. The fallback skips modules
   that an entry point already provided, so entry points win when both
   are present.

Loading is two separate steps, and keeping them separate is the
fix for audit finding S1: :func:`discover_and_register` records what
exists on disk, and :func:`mount_active` gives a runtime surface only
to the modules the database says are installed. :func:`load_modules`
still does both unconditionally for tests and tooling.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from collections.abc import Iterable
from importlib import metadata
from pathlib import Path

from fastapi import FastAPI

from app.config import settings

from .base import BaseModule
from .registry import module_registry
from .topology import topological_sort

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "dentalpin.modules"


def _resolve_load_order(modules: list[BaseModule]) -> list[BaseModule]:
    return topological_sort(
        modules,
        key=lambda m: m.name,
        deps_of=lambda m: m.dependencies,
    )


def _instantiate_module_class(cls: type) -> BaseModule | None:
    """Instantiate a BaseModule subclass, return None on failure."""
    if not (isinstance(cls, type) and issubclass(cls, BaseModule) and cls is not BaseModule):
        return None
    try:
        return cls()
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to instantiate module class %s: %s", cls.__name__, exc)
        return None


def _discover_entry_points() -> list[BaseModule]:
    """Discover modules registered as ``dentalpin.modules`` entry points."""
    modules: list[BaseModule] = []

    try:
        eps = metadata.entry_points(group=ENTRY_POINT_GROUP)
    except TypeError:
        # Python <3.10 fallback (not expected here but cheap).
        eps = metadata.entry_points().get(ENTRY_POINT_GROUP, [])  # type: ignore[union-attr]

    for ep in eps:
        try:
            cls = ep.load()
        except Exception as exc:
            logger.error("Failed to load entry point %s: %s", ep.name, exc)
            continue

        instance = _instantiate_module_class(cls)
        if instance is None:
            logger.warning("Entry point %s did not resolve to a BaseModule subclass", ep.name)
            continue

        modules.append(instance)
        logger.info("Discovered module via entry point: %s", instance.name)

    return modules


def _discover_filesystem(seen: set[str]) -> list[BaseModule]:
    """Filesystem scan fallback for dev mode.

    Skips modules already present in ``seen`` (names discovered via
    entry points).
    """
    modules: list[BaseModule] = []
    modules_path = Path(__file__).parent.parent.parent / "modules"

    if not modules_path.exists():
        logger.warning("Modules directory not found: %s", modules_path)
        return modules

    for module_info in pkgutil.iter_modules([str(modules_path)]):
        if not module_info.ispkg:
            continue

        try:
            pkg = importlib.import_module(f"app.modules.{module_info.name}")
        except Exception as exc:
            logger.error("Failed to import module %s: %s", module_info.name, exc)
            continue

        for attr_name in dir(pkg):
            cls = getattr(pkg, attr_name)
            instance = _instantiate_module_class(cls)
            if instance is None:
                continue
            if instance.name in seen:
                # Entry point already provided this module.
                break
            modules.append(instance)
            seen.add(instance.name)
            logger.info("Discovered module via filesystem scan: %s", instance.name)
            break

    return modules


def discover_modules() -> list[BaseModule]:
    """Run both discovery stages and return all unique modules."""
    modules = _discover_entry_points()
    seen = {m.name for m in modules}

    if settings.DENTALPIN_DEV_MODULE_SCAN:
        modules.extend(_discover_filesystem(seen))
    else:
        logger.info("DENTALPIN_DEV_MODULE_SCAN disabled; skipping filesystem discovery")

    return modules


def _mount_one(app: FastAPI, module: BaseModule) -> None:
    """Give one module its runtime surface: routes, handlers, tools."""
    from app.core.agents.tools.registry import tool_registry
    from app.core.events import event_bus

    app.include_router(
        module.get_router(),
        prefix=f"/api/v1/{module.name}",
        tags=[module.name],
    )
    logger.info("Mounted router for module: %s", module.name)

    for event_type, handler in module.get_event_handlers().items():
        event_bus.subscribe(event_type, handler)
        logger.info("Subscribed %s to event: %s", module.name, event_type)

    tool_registry.register_from(module)
    module_registry.activate(module.name)


def unmount_module(module: BaseModule) -> None:
    """Undo :func:`_mount_one` — the symmetry uninstall never had.

    Routes cannot be un-included from a running FastAPI app, and they
    do not need to be: the module stops answering because
    :data:`~app.core.plugins.gate.module_gate` blocks it now and the
    next boot does not mount it. Everything else can and must be undone
    in-process — a handler left on the bus keeps firing against dropped
    tables (its exception swallowed by the bus), and a copilot tool
    stays callable long after its data is gone.
    """
    from app.core.agents.tools.registry import tool_registry
    from app.core.events import event_bus

    for event_type, handler in module.get_event_handlers().items():
        event_bus.unsubscribe(event_type, handler)
        logger.info("Unsubscribed %s from event: %s", module.name, event_type)

    tool_registry.unregister_module(module.name)
    module_registry.deactivate(module.name)
    logger.info("Unmounted module: %s", module.name)


def discover_and_register() -> list[BaseModule]:
    """Discover modules and put them in the registry — nothing more.

    Deliberately side-effect free beyond the registry: no routes, no
    event subscriptions, no tools, no permission grants. The lifecycle
    processor needs every module *discovered* (it may have to install or
    uninstall any of them), while only the installed ones may run. See
    :func:`mount_active`.

    Returns the modules in dependency order. Re-registration is a no-op
    so a second call (tests, CLI) is harmless.
    """
    modules = discover_modules()
    if not modules:
        logger.warning("No modules discovered")
        return []

    try:
        ordered = _resolve_load_order(modules)
    except ValueError as exc:
        logger.error("Failed to resolve module dependencies: %s", exc)
        raise

    for module in ordered:
        if module_registry.is_discovered(module.name):
            continue
        module_registry.register(module)

    return [module_registry.get(m.name) or m for m in ordered]


def mount_active(app: FastAPI, installed: Iterable[str]) -> list[str]:
    """Mount exactly the modules named in ``installed``.

    ``installed`` comes from ``core_module.state`` — the database is the
    authority on what runs, never the filesystem (audit S1). Names that
    are not discovered are skipped with a warning: the row outlives the
    code when a module is deleted from disk, and the admin recovers with
    ``modules orphan``.

    Dependency consistency is not enforced here — ``ModuleService``
    refuses to uninstall a module others depend on. The loader mounts
    what it is told, in dependency order.
    """
    wanted = set(installed)
    mounted: list[str] = []

    # Mounting is authoritative, not additive: whatever is live now gets
    # taken down first, so afterwards the runtime surface is exactly
    # ``wanted``. In a fresh process this is a no-op — it matters when a
    # boot sequence runs twice in one process, where re-registering a
    # module's tools would otherwise raise ``ToolRegistryError``.
    for live in module_registry.list_modules():
        unmount_module(live)

    for module in _resolve_load_order(module_registry.list_discovered()):
        if module.name not in wanted:
            continue
        _mount_one(app, module)
        mounted.append(module.name)

    missing = wanted - set(mounted)
    if missing:
        logger.warning(
            "Install state names modules that are not on disk: %s",
            sorted(missing),
        )

    logger.info("Mounted %d modules: %s", len(mounted), mounted)
    return mounted


def load_modules(app: FastAPI) -> None:
    """Discover and mount every module, ignoring install state.

    The unconditional path, kept for the test suite and any caller that
    wants the whole inventory live. Production boots through
    :func:`discover_and_register` + :func:`mount_active` so that
    ``core_module.state`` decides — see :func:`app.main.lifespan`.
    """
    modules = discover_and_register()
    if modules:
        mount_active(app, [m.name for m in modules])
