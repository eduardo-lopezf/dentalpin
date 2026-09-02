"""A session can be ended, and a stolen refresh token gets caught.

ADR 0029, invariant 3. Before ``auth_sessions`` the only revocation was
``User.token_version`` — a global switch, incremented in one place, that
logs a user out of every device at once. These are the three behaviours
that replace it: rotation, reuse detection, and a logout that reaches
the server.

The tests drive the HTTP endpoints rather than the service, because the
defect being fixed was in the endpoints: the service could have been
perfect and `/auth/logout` still would not have existed.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import sessions
from app.core.auth.models import Clinic, User
from app.core.auth.service import create_refresh_token, hash_password

PASSWORD = "TestPass1234"


async def _make_user(db: AsyncSession, email: str) -> User:
    user = User(
        email=email,
        password_hash=hash_password(PASSWORD),
        first_name="Session",
        last_name="Probe",
    )
    db.add(user)
    await db.commit()
    return user


async def _login(client: AsyncClient, email: str) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return body["access_token"], body["refresh_token"]


async def _refresh(client: AsyncClient, token: str):
    return await client.post("/api/v1/auth/refresh", json={"refresh_token": token})


@pytest.mark.asyncio
async def test_refresh_rotates_and_spends_the_old_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _make_user(db_session, "rotate@example.com")
    _, first = await _login(client, user.email)

    response = await _refresh(client, first)

    assert response.status_code == 200, response.text
    second = response.json()["refresh_token"]
    assert second != first, "the refresh token was reissued unchanged"

    # And the successor works, so rotation is not a one-way trip.
    assert (await _refresh(client, second)).status_code == 200


@pytest.mark.asyncio
async def test_reusing_a_spent_token_kills_the_whole_family(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The case the design exists for.

    A refresh token is a bearer credential: a stolen one is
    indistinguishable from the real one *until it is used twice*. At that
    point there are two holders and no way to tell which is the thief, so
    both lose — refusing only the second presentation would leave the
    attacker holding a working chain.
    """
    user = await _make_user(db_session, "reuse@example.com")
    _, stolen = await _login(client, user.email)

    # The legitimate holder refreshes; `stolen` is now spent.
    live = (await _refresh(client, stolen)).json()["refresh_token"]

    replay = await _refresh(client, stolen)

    assert replay.status_code == 401

    # The thief is out — and so is the victim, which is the trade.
    assert (await _refresh(client, live)).status_code == 401
    assert await sessions.usable_sessions(db_session, user.id) == []


@pytest.mark.asyncio
async def test_logout_ends_the_session_server_side(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """What `useAuth.logout()` could not do: reach the server.

    Clearing the cookie left the refresh token valid for its full seven
    days.
    """
    user = await _make_user(db_session, "logout@example.com")
    _, refresh = await _login(client, user.email)

    response = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh})

    assert response.status_code == 204
    assert (await _refresh(client, refresh)).status_code == 401
    assert await sessions.usable_sessions(db_session, user.id) == []


@pytest.mark.asyncio
async def test_logout_is_silent_about_tokens_it_does_not_know(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """An endpoint that reports which tokens exist is an oracle."""
    user = await _make_user(db_session, "quiet@example.com")

    garbage = await client.post("/api/v1/auth/logout", json={"refresh_token": "not-a-jwt"})
    orphan = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": create_refresh_token(user.id, jti=user.id)},
    )

    assert garbage.status_code == 204
    assert orphan.status_code == 204


@pytest.mark.asyncio
async def test_a_refresh_token_naming_no_session_is_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Tokens minted before this table named no row, so nothing could revoke them.

    Rejecting them logs those holders out once, which is the point.
    """
    user = await _make_user(db_session, "legacy@example.com")
    legacy = create_refresh_token(user.id, token_version=user.token_version)

    assert (await _refresh(client, legacy)).status_code == 401


@pytest.mark.asyncio
async def test_logging_out_one_device_leaves_the_other_alone(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic
) -> None:
    """The whole reason this is not `token_version`.

    Two logins are two families. Ending one must not end the other —
    that is exactly what the global switch could not do.
    """
    user = await _make_user(db_session, "twodevices@example.com")
    _, laptop = await _login(client, user.email)
    _, phone = await _login(client, user.email)

    await client.post("/api/v1/auth/logout", json={"refresh_token": laptop})

    assert (await _refresh(client, laptop)).status_code == 401
    assert (await _refresh(client, phone)).status_code == 200
