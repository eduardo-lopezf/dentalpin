"""A write is committed before the client is told it succeeded.

``get_db`` commits when its ``yield`` returns, and FastAPI runs that exit
**after the response has been sent**: a generator dependency defaults to
scope ``"request"``, whose exit stack closes once ``await response(...)``
is done. A client could hear ``201`` for a patient and ask for it before
the row existed — the quick-create e2e did exactly that on CI's slower
disk — and a commit that failed there would have reported ``201`` for
data that was then rolled back.

``httpx``'s ``ASGITransport`` waits for the whole app before handing back
the response, and ``BaseHTTPMiddleware`` runs the app in a task of its
own, so neither shows the ordering. This drives ``app.router`` directly:
``send`` then runs inline, in the order the app calls it, and the row is
looked for from a separate connection at the moment the response starts.
"""

import asyncio
import json
from contextlib import AsyncExitStack
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.auth.models import Clinic
from app.database import async_session_maker
from app.main import app
from app.modules.patients.models import Patient


async def _post(path: str, payload: dict, headers: dict[str, str], on_start) -> int:
    body = json.dumps(payload).encode()
    status: list[int] = []
    delivered = False

    async def receive() -> dict:
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}
        # The client stays connected; nothing else ever arrives.
        await asyncio.Event().wait()
        return {}

    async def send(message: dict) -> None:
        if message["type"] == "http.response.start":
            status.append(message["status"])
            await on_start()

    # What FastAPI's own outermost middleware would have put in the scope.
    async with AsyncExitStack() as middleware_stack:
        scope: dict[str, Any] = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": [
                (b"host", b"test"),
                (b"content-type", b"application/json"),
                *((k.lower().encode(), v.encode()) for k, v in headers.items()),
            ],
            "client": ("test", 1),
            "server": ("test", 80),
            "app": app,
            "state": {},
            "fastapi_middleware_astack": middleware_stack,
        }
        await app.router(scope, receive, send)
    return status[0]


@pytest.mark.asyncio
async def test_a_created_patient_exists_when_the_response_starts(
    client: AsyncClient,  # installs the test database override
    auth_headers: dict[str, str],
    test_clinic: Clinic,  # the user needs a clinic to create a patient in
) -> None:
    seen: list[bool] = []

    async def look_from_another_connection() -> None:
        async with async_session_maker() as other:
            row = await other.execute(select(Patient.id).where(Patient.last_name == "Antes"))
            seen.append(row.scalar_one_or_none() is not None)

    status = await _post(
        "/api/v1/patients",
        {"first_name": "Commit", "last_name": "Antes"},
        auth_headers,
        look_from_another_connection,
    )

    assert status == 201
    assert seen == [True], "the client was told 201 before the patient was committed"
