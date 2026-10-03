"""Work a handler sends off on its own is still held, and can be waited for.

A notification handler returns immediately and does its writing in a task
of its own. With a bare ``asyncio.create_task`` nobody held that task —
the loop keeps only a weak reference, so it could be collected mid-write —
and nothing could wait for it either: the suite drops every table between
tests, and a straggler still writing deadlocked against that ``DROP``.
Four odontogram tests died that way on CI.
"""

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import background
from app.core.auth.models import Clinic
from app.modules.notifications.models import CommunicationMessage


@pytest.mark.asyncio
async def test_a_spawned_task_is_held_until_it_finishes() -> None:
    gate = asyncio.Event()

    async def work() -> None:
        await gate.wait()

    task = background.spawn(work(), name="probe")

    assert task in background.pending()

    gate.set()
    await background.drain(timeout=5)

    assert background.pending() == frozenset()
    assert task.done()


@pytest.mark.asyncio
async def test_the_welcome_message_is_written_after_the_response(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
) -> None:
    """The case that bit CI: creating a patient leaves work behind.

    The request is answered before the welcome message is written, so
    whatever owns the database — the suite here, a shutdown in
    production — has to wait for that task instead of pulling the tables
    out from under it.
    """
    response = await client.post(
        "/api/v1/patients",
        json={"first_name": "Nueva", "last_name": "Paciente", "email": "nueva@example.com"},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text

    await background.drain(timeout=10)
    assert background.pending() == frozenset()

    written = await db_session.execute(
        select(func.count(CommunicationMessage.id)).where(
            CommunicationMessage.triggered_by_event == "patient.created"
        )
    )
    assert written.scalar_one() == 1, "the welcome message never reached the database"
