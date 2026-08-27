"""S2 — events must not be announced from inside an open transaction.

Handlers run in their own sessions. A publisher that has only
``flush()``ed is telling them about a row no other connection can see:
``billing.on_payment_refunded`` recomputes an invoice from a database
without the refund and leaves it ``paid``; the recalls auto-link handler
points an FK at an appointment nobody else has. The fix is
``event_bus.publish_after_commit(db, ...)``, which queues on the session
and lets :class:`~app.database.UnitOfWorkSession` dispatch once the
commit lands.

Direct ``event_bus.publish(...)`` is still legitimate where the caller
has *already* committed — that is what the allowlist below records. Each
entry is a promise that the call sits after a commit; adding a file to
it should be a deliberate act, not a reflex.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus
from app.core.events.bus import PENDING_EVENTS_KEY
from app.core.plugins.db_models import ModuleRecord

APP_ROOT = Path(__file__).resolve().parents[1] / "app"

COMMIT_BEFORE_PUBLISH = {
    # /auth/setup commits the clinic, then publishes so `catalog` can
    # seed against it — and awaits the handlers before returning tokens.
    "core/auth/router.py",
    # Both commit the conversation row on the line above the publish.
    "modules/copilot/router.py",
    "modules/copilot/tasks.py",
    # Background workers that own their session and commit per item.
    "modules/verifactu/services/submission_queue.py",
    "modules/notifications/gateway.py",
    # Session-less helpers called after `db.commit()` per import batch.
    "modules/migration_import/events.py",
}


def test_publishers_defer_to_the_commit() -> None:
    offenders = {
        str(path.relative_to(APP_ROOT))
        for path in APP_ROOT.rglob("*.py")
        if "core/events/" not in str(path.relative_to(APP_ROOT))
        and "event_bus.publish(" in path.read_text()
    }

    assert offenders <= COMMIT_BEFORE_PUBLISH, (
        "these publish inside the caller's transaction — use "
        f"event_bus.publish_after_commit(db, ...): {sorted(offenders - COMMIT_BEFORE_PUBLISH)}"
    )


# --- The mechanism --------------------------------------------------------


async def test_queued_event_fires_only_after_the_commit(db_session: AsyncSession) -> None:
    fired: list[dict] = []
    event_bus.subscribe("test.deferred", fired.append)
    try:
        db_session.add(
            ModuleRecord(
                name="s2_probe",
                version="0.1.0",
                state="installed",
                category="official",
                removable=True,
                auto_install=False,
                manifest_snapshot={},
            )
        )
        event_bus.publish_after_commit(db_session, "test.deferred", {"ok": True})

        await db_session.flush()
        assert fired == [], "a flush is not a commit"
        assert db_session.info[PENDING_EVENTS_KEY]

        await db_session.commit()

        assert fired == [{"ok": True}]
        assert PENDING_EVENTS_KEY not in db_session.info
    finally:
        event_bus.unsubscribe("test.deferred", fired.append)


async def test_handlers_see_the_committed_row(db_session: AsyncSession) -> None:
    """The property that was actually broken: visibility from another session."""
    seen: list[bool] = []

    async def handler(data: dict) -> None:
        from app.database import async_session_maker

        async with async_session_maker() as other:
            row = await other.execute(select(ModuleRecord).where(ModuleRecord.name == data["name"]))
            seen.append(row.scalar_one_or_none() is not None)

    event_bus.subscribe("test.visibility", handler)
    try:
        db_session.add(
            ModuleRecord(
                name="s2_visible",
                version="0.1.0",
                state="installed",
                category="official",
                removable=True,
                auto_install=False,
                manifest_snapshot={},
            )
        )
        event_bus.publish_after_commit(db_session, "test.visibility", {"name": "s2_visible"})
        await db_session.commit()

        assert seen == [True], "the handler could not see the row it was told about"
    finally:
        event_bus.unsubscribe("test.visibility", handler)


async def test_rollback_drops_the_queue(db_session: AsyncSession) -> None:
    fired: list[dict] = []
    event_bus.subscribe("test.rolled_back", fired.append)
    try:
        db_session.add(
            ModuleRecord(
                name="s2_rollback",
                version="0.1.0",
                state="installed",
                category="official",
                removable=True,
                auto_install=False,
                manifest_snapshot={},
            )
        )
        event_bus.publish_after_commit(db_session, "test.rolled_back", {"ok": True})

        await db_session.rollback()
        await db_session.commit()

        assert fired == [], "announced a fact the transaction threw away"
    finally:
        event_bus.unsubscribe("test.rolled_back", fired.append)


def test_publish_after_commit_is_not_a_coroutine() -> None:
    """Nothing is dispatched at the call site.

    Keeping it sync means a leftover ``await`` from the old call shape
    fails loudly instead of silently queueing nothing.
    """
    assert not inspect.iscoroutinefunction(event_bus.publish_after_commit)
    assert inspect.iscoroutinefunction(event_bus.publish)
