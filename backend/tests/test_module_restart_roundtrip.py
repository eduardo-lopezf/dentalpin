"""S1 end to end: an uninstall must survive the restart that applies it.

The audit's headline symptom, in one test. Uninstall ``recalls`` and the
old code would: drop its tables, then re-create them on the next boot
(``alembic upgrade heads``), keep its routes mounted, keep its handlers
firing against those tables, keep its copilot tools callable and keep
granting ``recalls.*`` — all while ``core_module`` said ``uninstalled``.

Each "boot" here is what the container actually does: the entrypoint's
migration step (core chain only, because this database has a module
registry) followed by ``app.main.lifespan`` on a fresh app object.

Marked ``alembic_roundtrip`` — it drives real migrations and a real
``pg_dump``, so it is excluded from the default run like its neighbours.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import asyncpg
import pytest
from fastapi import FastAPI

from app.config import settings
from app.core.agents.tools.registry import tool_registry
from app.core.auth.permissions import get_role_permissions
from app.core.events import event_bus
from app.core.plugins.alembic_paths import resolve_core_head
from app.core.plugins.db_models import ModuleRecord
from app.core.plugins.registry import module_registry
from app.core.plugins.service import ModuleService
from app.core.plugins.state import ModuleState
from app.database import async_session_maker
from app.main import lifespan

pytestmark = [
    pytest.mark.alembic_roundtrip,
    pytest.mark.usefixtures("isolated_runtime"),
]

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

SPECIMEN = "recalls"
SPECIMEN_TABLES = {"recalls", "recall_contact_attempts", "recall_settings"}


def _alembic(*args: str) -> None:
    subprocess.run(["alembic", "-c", str(ALEMBIC_INI), *args], cwd=BACKEND_ROOT, check=True)


def _dsn() -> str:
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def _tables() -> set[str]:
    conn = await asyncpg.connect(_dsn())
    try:
        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
    finally:
        await conn.close()
    return {r["table_name"] for r in rows}


async def _boot(app: FastAPI) -> list[str]:
    """One container restart: entrypoint migration + lifespan startup."""
    core_head = resolve_core_head()
    assert core_head is not None
    _alembic("upgrade", core_head)

    async with lifespan(app):
        return list(app.openapi()["paths"])


def _serves(paths: list[str], module: str) -> bool:
    return any(p.startswith(f"/api/v1/{module}") for p in paths)


async def _state(name: str) -> str | None:
    async with async_session_maker() as session:
        record = await session.get(ModuleRecord, name)
        return record.state if record else None


async def test_uninstalled_module_stays_uninstalled_across_restarts() -> None:
    _alembic("upgrade", "heads")
    try:
        # --- boot 1: a healthy install -------------------------------
        paths = await _boot(FastAPI())
        assert _serves(paths, SPECIMEN)
        assert SPECIMEN_TABLES <= await _tables()
        assert await _state(SPECIMEN) == ModuleState.INSTALLED.value

        # --- the admin uninstalls ------------------------------------
        async with async_session_maker() as session:
            await ModuleService(session).uninstall(SPECIMEN)
        assert await _state(SPECIMEN) == ModuleState.TO_REMOVE.value

        # --- boot 2: the processor applies it ------------------------
        others = await _tables() - SPECIMEN_TABLES
        paths = await _boot(FastAPI())

        after = await _tables()
        assert SPECIMEN_TABLES.isdisjoint(after), (
            f"tables survived the uninstall: {SPECIMEN_TABLES & after}"
        )
        assert others <= after, f"the downgrade leaked: {others - after}"

        assert await _state(SPECIMEN) == ModuleState.UNINSTALLED.value
        assert not _serves(paths, SPECIMEN), "routes still mounted after uninstall"
        assert not module_registry.is_installed(SPECIMEN)
        assert not [t for t in tool_registry.list() if t.startswith(f"{SPECIMEN}.")]

        module = module_registry.get(SPECIMEN)
        assert module is not None
        subscribed = {h for handlers in event_bus._handlers.values() for h in handlers}
        assert not set(module.get_event_handlers().values()) & subscribed
        assert not [p for p in get_role_permissions("dentist") if p.startswith(f"{SPECIMEN}.")]

        # --- boot 3: the resurrection check --------------------------
        # This is the one that used to fail: `alembic upgrade heads` on
        # every boot re-created the tables of a module nobody installed.
        paths = await _boot(FastAPI())
        assert SPECIMEN_TABLES.isdisjoint(await _tables()), "schema came back on restart"
        assert not _serves(paths, SPECIMEN)
        assert await _state(SPECIMEN) == ModuleState.UNINSTALLED.value

        # --- and back: reinstall is a single restart -----------------
        async with async_session_maker() as session:
            await ModuleService(session).install(SPECIMEN)

        paths = await _boot(FastAPI())
        assert SPECIMEN_TABLES <= await _tables()
        assert _serves(paths, SPECIMEN)
        assert await _state(SPECIMEN) == ModuleState.INSTALLED.value
        assert [t for t in tool_registry.list() if t.startswith(f"{SPECIMEN}.")]
    finally:
        # Leave the database complete for whatever runs next.
        _alembic("upgrade", "heads")
