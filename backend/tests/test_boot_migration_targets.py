"""S1, schema half — boot must not migrate what is not installed.

``docker-entrypoint.sh`` used to run ``alembic upgrade heads`` on every
boot. ``heads`` walks every branch directory on disk, so the tables of a
module the admin had uninstalled came back on the next restart while its
state stayed ``uninstalled`` (audit S1, issue #56 one layer up).

The contract now:

* the entrypoint applies the **core linear chain** only, unless the
  database has no module registry at all (a bootstrap, where nothing can
  have been uninstalled yet);
* module branches are applied by :class:`PendingProcessor`, which reads
  ``core_module.state``;
* a module whose branch cannot reach head is kept out of the mount set —
  its code moved and its tables did not.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plugins import processor as processor_mod
from app.core.plugins.alembic_paths import (
    core_versions_dir,
    resolve_core_head,
    resolve_module_branch_head,
)
from app.core.plugins.db_models import ModuleRecord
from app.core.plugins.processor import PendingProcessor
from app.core.plugins.registry import module_registry
from app.core.plugins.state import ModuleState
from app.database import async_session_maker

ENTRYPOINT = Path(__file__).resolve().parents[1] / "docker-entrypoint.sh"

# ``patients`` ships a branch but declares no ``branch_labels`` — half the
# modules don't — so it is the specimen that proves targets are revision
# ids and not ``<label>@head``.
UNLABELLED = "patients"


def _record(name: str, state: ModuleState, applied: str | None) -> ModuleRecord:
    return ModuleRecord(
        name=name,
        version="0.1.0",
        state=state.value,
        category="official",
        removable=True,
        auto_install=True,
        last_state_change=datetime.now(UTC),
        manifest_snapshot={},
        base_revision=applied,
        applied_revision=applied,
    )


# --- The core head --------------------------------------------------------


def test_core_head_comes_from_the_linear_chain() -> None:
    head = resolve_core_head()

    assert head is not None
    module_heads = {resolve_module_branch_head(m) for m in module_registry.list_discovered()} - {
        None
    }
    assert head not in module_heads

    filenames = [p.name for p in core_versions_dir().glob("*.py")]
    assert any(name.startswith(f"{head}_") or name == f"{head}.py" for name in filenames)


def test_entrypoint_does_not_upgrade_heads_unconditionally() -> None:
    """The one line that resurrects a dropped schema."""
    script = ENTRYPOINT.read_text()

    assert "resolve_core_head" in script
    assert "to_regclass('public.core_module')" in script

    commands = [
        line.strip() for line in script.splitlines() if line.strip().startswith("alembic upgrade")
    ]
    # ``heads`` survives only as the bootstrap arm of the registry check.
    assert commands.count("alembic upgrade heads") == 1
    assert any('"$CORE_HEAD"' in command for command in commands)


# --- Branch targets -------------------------------------------------------


async def test_run_migrate_targets_the_revision_id_not_a_branch_label(monkeypatch) -> None:
    """``<name>@head`` only resolves for modules that declare a label.

    ``alembic upgrade patients@head`` fails with "Can't locate revision
    identified by 'patients'", which would have made every catch-up
    migration for an unlabelled branch a boot-time error.
    """
    calls: list[list[str]] = []
    monkeypatch.setattr(processor_mod, "_alembic_cmd", lambda args: calls.append(args))

    module = module_registry.get(UNLABELLED)
    assert module is not None
    head = resolve_module_branch_head(module)

    await PendingProcessor(async_session_maker)._run_migrate(module)

    assert calls == [["upgrade", head]]
    assert f"{UNLABELLED}@head" not in calls[0]


# --- Catch-up migrations --------------------------------------------------


async def test_migrate_installed_only_touches_installed_stale_branches(
    db_session: AsyncSession, monkeypatch
) -> None:
    migrated: list[str] = []
    monkeypatch.setattr(
        processor_mod,
        "_alembic_cmd",
        lambda args: migrated.append(args[-1]) or args[-1],
    )

    stale = resolve_module_branch_head(module_registry.get(UNLABELLED))
    db_session.add_all(
        [
            # installed + behind head → migrates
            _record(UNLABELLED, ModuleState.INSTALLED, "pat_0001"),
            # uninstalled + behind head → must NOT be resurrected
            _record("verifactu", ModuleState.UNINSTALLED, "ver_0001"),
            # installed + already at head → no Alembic at all
            _record(
                "recalls",
                ModuleState.INSTALLED,
                resolve_module_branch_head(module_registry.get("recalls")),
            ),
        ]
    )
    await db_session.commit()

    failed = await PendingProcessor(async_session_maker)._migrate_installed()

    assert failed == set()
    assert migrated == [stale]

    await db_session.refresh(await db_session.get(ModuleRecord, UNLABELLED))
    row = (
        await db_session.execute(select(ModuleRecord).where(ModuleRecord.name == UNLABELLED))
    ).scalar_one()
    assert row.applied_revision == stale


async def test_failed_branch_migration_keeps_the_module_unmounted(
    db_session: AsyncSession, monkeypatch
) -> None:
    def boom(args: list[str]) -> str:
        raise RuntimeError("relation already exists")

    monkeypatch.setattr(processor_mod, "_alembic_cmd", boom)

    db_session.add(_record(UNLABELLED, ModuleState.INSTALLED, "pat_0001"))
    await db_session.commit()

    processor = PendingProcessor(async_session_maker)
    failed = await processor._migrate_installed()

    assert failed == {UNLABELLED}

    row = (
        await db_session.execute(select(ModuleRecord).where(ModuleRecord.name == UNLABELLED))
    ).scalar_one()
    await db_session.refresh(row)
    # Still installed — nothing was removed, and the admin needs it
    # visible to retry — but the error is on the record.
    assert row.state == ModuleState.INSTALLED.value
    assert "relation already exists" in (row.error_message or "")


@pytest.mark.parametrize("state", [ModuleState.UNINSTALLED, ModuleState.TO_REMOVE])
async def test_uninstalled_branches_are_never_migrated(
    db_session: AsyncSession, monkeypatch, state: ModuleState
) -> None:
    migrated: list[str] = []
    monkeypatch.setattr(
        processor_mod, "_alembic_cmd", lambda args: migrated.append(args[-1]) or args[-1]
    )

    db_session.add(_record("verifactu", state, "ver_0001"))
    await db_session.commit()

    assert await PendingProcessor(async_session_maker)._migrate_installed() == set()
    assert migrated == []
