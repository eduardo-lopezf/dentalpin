"""S5 on the bus — a handler that fails must leave a trace.

The bus catches every handler exception and logs it. That was already
the weakest link; [ADR 0019](../../docs/adr/0019-events-publish-after-commit.md)
made it load-bearing. Handlers now run strictly *after* the publisher's
commit, so when one fails the fact is durable and the reaction is gone:
the invoice is issued and its VeriFactu record never written, the
payment is recorded and the recall never linked. Nothing in the database
says so, and the only evidence is a log line nobody greps.

The contract: every handler failure becomes a row in
``core_event_failure`` — event, handler, payload, error — readable by an
admin. Recording is best-effort about itself: it must never turn one
broken subscriber into a broken dispatch.
"""

from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.events import event_bus
from app.core.events.models import EventHandlerFailure

EVENT = "test.failure_visibility"


async def _failures(db: AsyncSession) -> list[EventHandlerFailure]:
    rows = await db.execute(select(EventHandlerFailure).order_by(EventHandlerFailure.id))
    return list(rows.scalars())


async def test_failing_handler_is_recorded(db_session: AsyncSession) -> None:
    clinic_id = uuid4()

    async def broken(data: dict) -> None:
        raise ValueError("no such treatment category")

    event_bus.subscribe(EVENT, broken)
    try:
        await event_bus.publish(EVENT, {"clinic_id": str(clinic_id), "payment_id": "abc"})
    finally:
        event_bus.unsubscribe(EVENT, broken)

    rows = await _failures(db_session)
    assert len(rows) == 1
    row = rows[0]
    assert row.event_type == EVENT
    assert "broken" in row.handler
    assert row.clinic_id == clinic_id
    assert row.payload["payment_id"] == "abc"
    assert "no such treatment category" in row.error
    assert "ValueError" in (row.traceback or "")


async def test_successful_handler_records_nothing(db_session: AsyncSession) -> None:
    async def fine(data: dict) -> None:
        return None

    event_bus.subscribe(EVENT, fine)
    try:
        await event_bus.publish(EVENT, {"clinic_id": str(uuid4())})
    finally:
        event_bus.unsubscribe(EVENT, fine)

    assert await _failures(db_session) == []


async def test_one_broken_subscriber_does_not_stop_the_others(
    db_session: AsyncSession,
) -> None:
    ran: list[str] = []

    async def broken(data: dict) -> None:
        raise RuntimeError("boom")

    async def after(data: dict) -> None:
        ran.append("after")

    event_bus.subscribe(EVENT, broken)
    event_bus.subscribe(EVENT, after)
    try:
        await event_bus.publish(EVENT, {})
    finally:
        event_bus.unsubscribe(EVENT, broken)
        event_bus.unsubscribe(EVENT, after)

    assert ran == ["after"]
    assert len(await _failures(db_session)) == 1


async def test_a_broken_recorder_does_not_break_the_dispatch(
    db_session: AsyncSession, monkeypatch
) -> None:
    """Recording is a diagnostic, never a new way to fail."""
    ran: list[str] = []

    async def explode(*args, **kwargs) -> None:
        raise OSError("database is gone")

    monkeypatch.setattr(event_bus, "_record_failure", explode)

    async def broken(data: dict) -> None:
        raise RuntimeError("boom")

    async def after(data: dict) -> None:
        ran.append("after")

    event_bus.subscribe(EVENT, broken)
    event_bus.subscribe(EVENT, after)
    try:
        await event_bus.publish(EVENT, {})
    finally:
        event_bus.unsubscribe(EVENT, broken)
        event_bus.unsubscribe(EVENT, after)

    assert ran == ["after"]


async def test_admin_can_read_the_failures(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    async def broken(data: dict) -> None:
        raise ValueError("visible to the admin")

    event_bus.subscribe(EVENT, broken)
    try:
        await event_bus.publish(EVENT, {"clinic_id": str(test_clinic.id)})
        # A failure from another clinic must not leak into the listing.
        await event_bus.publish(EVENT, {"clinic_id": str(uuid4())})
    finally:
        event_bus.unsubscribe(EVENT, broken)

    response = await client.get("/api/v1/events/failures", headers=auth_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    entry = body["data"][0]
    assert entry["event_type"] == EVENT
    assert "visible to the admin" in entry["error"]
    assert "broken" in entry["handler"]
