"""An account that belongs to no clinic cannot sign in, and an admin can
cut off one that does not belong to theirs.

Two halves of the same hole. `/auth/login` only ever asked for a password
and an active flag, so an account with no membership anywhere signed in
happily and got a token with `clinic_id = None` — able to do nothing, and
invisible to the one screen that could stop it.

Accounts reach that state on their own: `DELETE /auth/users/{id}` removes
the membership and keeps the account, so "remove from clinic" left a
working login behind. Seeding over an installation that already had a
clinic does the same to every user of the original one.

The first half closes it for good: no membership, no sign-in — which also
makes removing someone from the clinic mean what it says. The second half
covers what that cannot reach, an account stranded in *another* clinic
row, where only an operator can decide it should stop working.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password

PASSWORD = "TestPass1234"


async def _user(db: AsyncSession, email: str) -> User:
    user = User(
        email=email,
        password_hash=hash_password(PASSWORD),
        first_name="Left",
        last_name="Behind",
    )
    db.add(user)
    await db.commit()
    return user


async def _other_clinic(db: AsyncSession) -> Clinic:
    clinic = Clinic(
        id=uuid4(),
        name="Clinic From Before The Seed",
        tax_id=f"B{uuid4().int % 100000000:08d}",
        address={"street": "Elsewhere", "city": "Bilbao"},
        settings={},
        account_tier="clinic",
    )
    db.add(clinic)
    await db.commit()
    return clinic


async def _login(client: AsyncClient, email: str):
    return await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


# --- no membership, no sign-in ----------------------------------------


@pytest.mark.asyncio
async def test_an_account_with_no_membership_cannot_sign_in(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    orphan = await _user(db_session, f"orphan-{uuid4().hex[:8]}@example.com")

    response = await _login(client, orphan.email)

    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_removing_someone_from_the_clinic_ends_their_sign_in(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    """The reason the first rule matters.

    `DELETE /auth/users/{id}` drops the membership and keeps the account,
    so before this an admin who removed somebody left them a working login
    and no way to see it.
    """
    member = await _user(db_session, f"member-{uuid4().hex[:8]}@example.com")
    db_session.add(
        ClinicMembership(user_id=member.id, clinic_id=test_clinic.id, role="receptionist")
    )
    await db_session.commit()
    # Read off the instance before it is expired below: afterwards every
    # attribute is a lazy load, and a lazy load here is a `MissingGreenlet`.
    email, member_id = member.email, member.id
    assert (await _login(client, email)).status_code == 200

    removed = await client.delete(f"/api/v1/auth/users/{member_id}", headers=auth_headers)
    assert removed.status_code == 204, removed.text

    # The suite hands the app its own session, with `expire_on_commit=False`,
    # so the `User` it already loaded keeps the membership collection it was
    # loaded with. A real request opens a fresh session and sees the delete;
    # this is how the test gets the same view.
    db_session.expire_all()

    assert (await _login(client, email)).status_code == 403


@pytest.mark.asyncio
async def test_a_membership_in_another_clinic_still_signs_in(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The rule is "no clinic at all", not "not my clinic"."""
    other = await _other_clinic(db_session)
    stranded = await _user(db_session, f"stranded-{uuid4().hex[:8]}@example.com")
    db_session.add(ClinicMembership(user_id=stranded.id, clinic_id=other.id, role="admin"))
    await db_session.commit()

    assert (await _login(client, stranded.email)).status_code == 200


# --- cutting off an account that is not this clinic's ------------------


@pytest.mark.asyncio
async def test_an_admin_can_stop_an_account_that_has_no_access_here(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    """What login-gating cannot reach: a live account in another clinic row."""
    other = await _other_clinic(db_session)
    stranded = await _user(db_session, f"stranded-{uuid4().hex[:8]}@example.com")
    db_session.add(ClinicMembership(user_id=stranded.id, clinic_id=other.id, role="admin"))
    await db_session.commit()
    assert (await _login(client, stranded.email)).status_code == 200

    response = await client.patch(
        f"/api/v1/auth/users/{stranded.id}/active",
        json={"is_active": False},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["is_active"] is False

    assert (await _login(client, stranded.email)).status_code == 403


@pytest.mark.asyncio
async def test_stopping_an_account_invalidates_the_tokens_it_holds(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    """A password that no longer works is no use if the open session does."""
    other = await _other_clinic(db_session)
    stranded = await _user(db_session, f"stranded-{uuid4().hex[:8]}@example.com")
    db_session.add(ClinicMembership(user_id=stranded.id, clinic_id=other.id, role="admin"))
    await db_session.commit()
    tokens = (await _login(client, stranded.email)).json()

    await client.patch(
        f"/api/v1/auth/users/{stranded.id}/active",
        json={"is_active": False},
        headers=auth_headers,
    )

    refreshed = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 401, refreshed.text


@pytest.mark.asyncio
async def test_an_account_can_be_let_back_in(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    """Reversible: an operator who stops the wrong account can undo it."""
    other = await _other_clinic(db_session)
    stranded = await _user(db_session, f"stranded-{uuid4().hex[:8]}@example.com")
    db_session.add(ClinicMembership(user_id=stranded.id, clinic_id=other.id, role="admin"))
    await db_session.commit()

    for active in (False, True):
        response = await client.patch(
            f"/api/v1/auth/users/{stranded.id}/active",
            json={"is_active": active},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["is_active"] is active

    assert (await _login(client, stranded.email)).status_code == 200


@pytest.mark.asyncio
async def test_a_member_of_this_clinic_is_not_managed_here(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    """One way to do a thing: members go through `PUT /users/{id}`, which
    also carries their role and profile."""
    member = await _user(db_session, f"member-{uuid4().hex[:8]}@example.com")
    db_session.add(ClinicMembership(user_id=member.id, clinic_id=test_clinic.id, role="dentist"))
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/auth/users/{member.id}/active",
        json={"is_active": False},
        headers=auth_headers,
    )
    assert response.status_code == 409, response.text


@pytest.mark.asyncio
async def test_an_admin_cannot_stop_themselves(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    me = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()["data"]["user"]

    response = await client.patch(
        f"/api/v1/auth/users/{me['id']}/active",
        json={"is_active": False},
        headers=auth_headers,
    )
    assert response.status_code in (400, 409), response.text
    still = await db_session.execute(select(User).where(User.id == me["id"]))
    assert still.scalar_one().is_active is True


@pytest.mark.asyncio
async def test_an_unknown_account_is_not_found(
    client: AsyncClient, auth_headers: dict[str, str], test_clinic: Clinic
) -> None:
    response = await client.patch(
        f"/api/v1/auth/users/{uuid4()}/active",
        json={"is_active": False},
        headers=auth_headers,
    )
    assert response.status_code == 404, response.text
