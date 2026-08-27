"""S1, the uninstall window — a module on its way out must stop serving.

Lifecycle transitions are restart-based: ``uninstall`` marks the record
``to_remove`` and the lifespan processor does the work at the next boot.
Between those two moments the module is still mounted, so it keeps
accepting writes into tables that are about to be dropped — and the only
copy of them will be a ``pg_dump`` file nobody reads.

Two mechanisms, tested here:

* :data:`module_gate` — an in-memory set consulted by one middleware,
  closed by ``ModuleService.uninstall`` and re-opened when the removal is
  cancelled or completed;
* :func:`unmount_module` — the symmetry ``_remove`` never had: handlers
  off the bus, tools out of the registry, module out of the active set.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.tools.registry import tool_registry
from app.core.events import event_bus
from app.core.plugins.db_models import ModuleRecord
from app.core.plugins.gate import module_gate
from app.core.plugins.loader import mount_active, unmount_module
from app.core.plugins.registry import module_registry
from app.core.plugins.service import ModuleService
from app.core.plugins.state import ModuleState

pytestmark = pytest.mark.usefixtures("isolated_runtime")

SPECIMEN = "recalls"
NEIGHBOUR = "patients"


def _record(name: str, state: ModuleState) -> ModuleRecord:
    return ModuleRecord(
        name=name,
        version="0.1.0",
        state=state.value,
        category="official",
        removable=True,
        auto_install=False,
        installed_at=datetime.now(UTC),
        last_state_change=datetime.now(UTC),
        manifest_snapshot={"name": name, "version": "0.1.0", "depends": []},
        base_revision="rec_0001",
        applied_revision="rec_0001",
    )


# --- Path matching --------------------------------------------------------


def test_gate_matches_only_the_blocked_module_segment() -> None:
    module_gate.block(NEIGHBOUR)

    assert module_gate.match(f"/api/v1/{NEIGHBOUR}") == NEIGHBOUR
    assert module_gate.match(f"/api/v1/{NEIGHBOUR}/123/notes") == NEIGHBOUR

    # A module whose name merely starts with a blocked one is untouched —
    # ``patients`` blocked must not take down ``patients_clinical``.
    assert module_gate.match("/api/v1/patients_clinical/1") is None
    assert module_gate.match(f"/api/v1/{SPECIMEN}/stats") is None
    assert module_gate.match("/health") is None


def test_open_gate_matches_nothing() -> None:
    assert module_gate.match(f"/api/v1/{SPECIMEN}") is None


# --- The middleware -------------------------------------------------------


async def test_blocked_module_answers_409(client: AsyncClient, auth_headers: dict) -> None:
    module_gate.block(SPECIMEN)

    response = await client.get(f"/api/v1/{SPECIMEN}/stats/dashboard", headers=auth_headers)

    assert response.status_code == 409
    body = response.json()
    assert SPECIMEN in body["message"]
    assert body["errors"]


async def test_gate_does_not_touch_other_modules(client: AsyncClient, auth_headers: dict) -> None:
    module_gate.block(SPECIMEN)

    response = await client.get(f"/api/v1/{NEIGHBOUR}", headers=auth_headers)

    assert response.status_code != 409


async def test_preflight_passes_through_the_gate(client: AsyncClient) -> None:
    """A 409 on OPTIONS reads as a CORS failure and hides the real status."""
    module_gate.block(SPECIMEN)

    response = await client.options(
        f"/api/v1/{SPECIMEN}/stats/dashboard",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code != 409


# --- State transitions drive the gate -------------------------------------


async def test_uninstall_closes_the_gate_and_install_reopens_it(
    db_session: AsyncSession,
) -> None:
    db_session.add(_record(SPECIMEN, ModuleState.INSTALLED))
    await db_session.commit()
    service = ModuleService(db_session)

    await service.uninstall(SPECIMEN)
    assert module_gate.is_blocked(SPECIMEN)

    # Changing your mind before the restart must bring the module back.
    await service.install(SPECIMEN)
    assert not module_gate.is_blocked(SPECIMEN)


async def test_orphan_reopens_the_gate(db_session: AsyncSession) -> None:
    db_session.add(_record(SPECIMEN, ModuleState.TO_REMOVE))
    await db_session.commit()
    module_gate.block(SPECIMEN)

    assert await ModuleService(db_session).orphan(SPECIMEN) is True
    assert not module_gate.is_blocked(SPECIMEN)


# --- Unmounting -----------------------------------------------------------


def test_unmount_takes_handlers_tools_and_activation_away() -> None:
    from fastapi import FastAPI

    mount_active(FastAPI(), {SPECIMEN, NEIGHBOUR})
    module = module_registry.get(SPECIMEN)
    assert module is not None
    assert [q for q in tool_registry.list() if q.startswith(f"{SPECIMEN}.")]

    unmount_module(module)

    subscribed = {h for handlers in event_bus._handlers.values() for h in handlers}
    assert not set(module.get_event_handlers().values()) & subscribed
    assert not [q for q in tool_registry.list() if q.startswith(f"{SPECIMEN}.")]
    assert not module_registry.is_installed(SPECIMEN)

    # The neighbour keeps everything.
    assert module_registry.is_installed(NEIGHBOUR)
    assert [q for q in tool_registry.list() if q.startswith(f"{NEIGHBOUR}.")]


async def test_remove_unmounts_before_dropping_the_data(
    db_session: AsyncSession, monkeypatch
) -> None:
    """``_remove`` used to drop tables with the handlers still subscribed."""
    from fastapi import FastAPI

    from app.core.plugins import processor as processor_mod
    from app.core.plugins.processor import PendingProcessor
    from app.database import async_session_maker

    mount_active(FastAPI(), {SPECIMEN})
    module = module_registry.get(SPECIMEN)
    assert module is not None

    subscribed_when_dropping: set = set()

    async def fake_downgrade(self, revision: str) -> None:
        subscribed_when_dropping.update(
            h for handlers in event_bus._handlers.values() for h in handlers
        )

    async def fake_dump(self, module_name: str, tables: list[str]) -> None:
        return None

    monkeypatch.setattr(PendingProcessor, "_run_downgrade", fake_downgrade)
    monkeypatch.setattr(PendingProcessor, "_dump_tables", fake_dump)
    monkeypatch.setattr(processor_mod, "_alembic_cmd", lambda args: None)

    record = _record(SPECIMEN, ModuleState.TO_REMOVE)
    db_session.add(record)
    await db_session.commit()
    module_gate.block(SPECIMEN)

    await PendingProcessor(async_session_maker)._remove(record)

    assert not set(module.get_event_handlers().values()) & subscribed_when_dropping
    assert not [q for q in tool_registry.list() if q.startswith(f"{SPECIMEN}.")]
    assert not module_registry.is_installed(SPECIMEN)
    # Nothing left to guard once the module is gone.
    assert not module_gate.is_blocked(SPECIMEN)
