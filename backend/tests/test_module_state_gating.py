"""S1 — install state must gate what the process mounts.

``docs/technical/audit-2026-07-03.md`` S1: ``core_module.state`` is
written by the plugin service and read by nobody. ``loader`` mounts
every module found on disk, so an uninstalled module keeps its routes,
its event subscriptions, its copilot tools and its role grants — and
``app.main.lifespan`` makes it structural by mounting *before* it
reconciles state.

This file is the executable contract for the fix:

* discovery (import + register) has no observable side effect;
* mounting takes an explicit set of installed names and honours it;
* the registry tells "discovered" from "installed", and every consumer
  that means *installed* reads the installed set;
* the boot sequence resolves state before it mounts.

``recalls`` is the specimen the audit uses: router, five event handlers,
copilot tools and role grants — one module covering every surface.

Note ``mount_active`` mounts exactly what it is told. Dependency
consistency (never uninstalling a module someone depends on) is
``ModuleService``'s job, not the loader's.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.tools.registry import tool_registry
from app.core.auth.permissions import (
    get_role_permissions,
    invalidate_role_permissions_cache,
)
from app.core.events import event_bus
from app.core.plugins.db_models import ModuleRecord
from app.core.plugins.loader import mount_active
from app.core.plugins.registry import module_registry
from app.core.plugins.service import installed_module_names
from app.core.plugins.state import ModuleState
from app.core.tenancy.single import SingleTenantResolver

SPECIMEN = "recalls"
KEEPER = "patients"


@pytest.fixture(autouse=True)
def isolated_runtime():
    """Give each test an empty runtime to mount into.

    ``conftest`` mounts every discovered module into the process-wide
    singletons at import time. These tests mount a different subset, so
    snapshot the three globals, hand the test a blank slate, and put the
    originals back — the rest of the suite depends on them.
    """
    saved_active = set(module_registry._active)
    saved_handlers = {k: list(v) for k, v in event_bus._handlers.items()}
    saved_tools = dict(tool_registry._tools)
    saved_owners = dict(tool_registry._owners)

    module_registry._active = set()
    event_bus._handlers = {}
    tool_registry.clear()
    invalidate_role_permissions_cache()

    yield

    module_registry._active = saved_active
    event_bus._handlers = saved_handlers
    tool_registry._tools = saved_tools
    tool_registry._owners = saved_owners
    invalidate_role_permissions_cache()


def _mount(*names: str) -> FastAPI:
    app = FastAPI()
    mount_active(app, set(names))
    return app


def _paths(app: FastAPI) -> list[str]:
    """URL paths the app actually serves.

    Since FastAPI 0.141 ``app.routes`` holds lazy ``_IncludedRouter``
    wrappers instead of flat routes, so the generated OpenAPI schema is
    the supported way to ask what is mounted.
    """
    return list(app.openapi()["paths"])


# --- Mounting -------------------------------------------------------------


def test_uninstalled_module_gets_no_routes() -> None:
    paths = _paths(_mount(KEEPER))

    assert any(p.startswith(f"/api/v1/{KEEPER}") for p in paths)
    assert not any(p.startswith(f"/api/v1/{SPECIMEN}") for p in paths)


def test_uninstalled_module_gets_no_event_subscriptions() -> None:
    _mount(KEEPER)

    subscribed = {h for handlers in event_bus._handlers.values() for h in handlers}
    specimen = module_registry.get(SPECIMEN)
    assert specimen is not None
    assert not set(specimen.get_event_handlers().values()) & subscribed


def test_uninstalled_module_gets_no_copilot_tools() -> None:
    _mount(KEEPER)

    assert [q for q in tool_registry.list() if q.startswith(f"{KEEPER}.")]
    assert not [q for q in tool_registry.list() if q.startswith(f"{SPECIMEN}.")]


# --- Registry semantics ---------------------------------------------------


def test_registry_tells_discovered_from_installed() -> None:
    _mount(KEEPER)

    assert module_registry.is_discovered(SPECIMEN)
    assert not module_registry.is_installed(SPECIMEN)
    assert module_registry.is_installed(KEEPER)

    assert {m.name for m in module_registry.list_modules()} == {KEEPER}
    assert SPECIMEN in {m.name for m in module_registry.list_discovered()}


def test_uninstalled_module_grants_no_permissions() -> None:
    _mount(KEEPER)

    assert not [p for p in get_role_permissions("dentist") if p.startswith(f"{SPECIMEN}.")]
    assert not [p for p in module_registry.get_all_permissions() if p.startswith(f"{SPECIMEN}.")]


async def test_tenant_modules_enabled_follows_install_state() -> None:
    _mount(KEEPER)

    ctx = await SingleTenantResolver().resolve_by_slug("default")

    assert KEEPER in ctx.modules_enabled
    assert SPECIMEN not in ctx.modules_enabled


# --- The DB is the source of truth ---------------------------------------


async def test_installed_module_names_reads_state_from_db(db_session: AsyncSession) -> None:
    """Only ``installed`` mounts.

    ``to_remove`` is deliberately excluded: by mount time the processor
    has either completed the removal (state ``uninstalled``) or failed
    half-way, and a module with partially dropped tables must not serve.
    """
    now = datetime.now(UTC)
    for name, state in (
        (KEEPER, ModuleState.INSTALLED),
        (SPECIMEN, ModuleState.UNINSTALLED),
        ("verifactu", ModuleState.TO_REMOVE),
    ):
        db_session.add(
            ModuleRecord(
                name=name,
                version="0.1.0",
                state=state.value,
                category="official",
                removable=True,
                auto_install=False,
                last_state_change=now,
                manifest_snapshot={},
            )
        )
    await db_session.commit()

    assert await installed_module_names(db_session) == {KEEPER}


# --- Boot order -----------------------------------------------------------


async def test_lifespan_resolves_state_before_mounting(db_session: AsyncSession) -> None:
    """The end-to-end shape of S1.

    A module with ``auto_install=False`` has never been installed, so a
    fresh boot must leave it unmounted. Today the lifespan mounts every
    module on disk first and only then looks at ``core_module`` — which
    is why this fails before the fix.
    """
    from app.main import lifespan

    app = FastAPI()
    async with lifespan(app):
        paths = _paths(app)

    # auto_install=True → reconciled as installed → mounted.
    assert any(p.startswith("/api/v1/agenda") for p in paths)
    # auto_install=False → stays uninstalled → not mounted.
    assert not any(p.startswith("/api/v1/verifactu") for p in paths)
    assert not module_registry.is_installed("verifactu")
