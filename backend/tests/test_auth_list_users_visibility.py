"""Every account that can sign in must be visible to an admin.

`GET /auth/users` built its list by joining `ClinicMembership` for the
caller's clinic, so an account without a membership *there* did not appear
— while `POST /auth/login` never asked for one, and let it in. That is the
worst pairing available: an account nobody can see and nobody can
deactivate, still holding a password that works.

It is not hypothetical. A deployment holds exactly one clinic (nothing
creates a second except `/auth/setup` and the demo seed), so running
`seed_demo.py` over an installation that already had its own clinic leaves
the original users behind a clinic the admin is no longer looking at. That
is how a live server ended up with a user it could not see and could not
stop.

The listing is deliberately **not** scoped to the clinic, which is an
exception to the rule that every query filters by `clinic_id`
(`CLAUDE.md`). It is bounded: the rows say who can sign in and whether
they have access here, and nothing about any other clinic.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password


async def _make_user(db: AsyncSession, email: str) -> User:
    user = User(
        email=email,
        password_hash=hash_password("TestPass1234"),
        first_name="Left",
        last_name="Behind",
    )
    db.add(user)
    await db.commit()
    return user


def _row(body: dict, email: str) -> dict | None:
    return next((u for u in body["data"] if u["email"] == email), None)


@pytest.mark.asyncio
async def test_a_user_with_no_membership_anywhere_is_listed(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    """The account the seed strands: it can log in and belonged to nobody."""
    orphan = await _make_user(db_session, f"orphan-{uuid4().hex[:8]}@example.com")

    response = await client.get("/api/v1/auth/users", headers=auth_headers)
    assert response.status_code == 200, response.text

    listed = _row(response.json(), orphan.email)
    assert listed is not None, "an account that can sign in was hidden from the admin"
    # No role, because it has no access here — that is the thing to show.
    assert listed["role"] is None
    assert listed["has_clinic_access"] is False


@pytest.mark.asyncio
async def test_a_user_left_in_another_clinic_is_listed(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    """The other shape of the same problem, and the likelier one.

    `seed_demo.py` adds its own clinic rather than adopting the one that is
    there, so the users of the original clinic keep working logins while
    the admin now administers a different clinic.
    """
    other = Clinic(
        id=uuid4(),
        name="Clinic From Before The Seed",
        tax_id="B99999999",
        address={"street": "Elsewhere", "city": "Bilbao"},
        settings={},
        account_tier="clinic",
    )
    db_session.add(other)
    stranded = await _make_user(db_session, f"stranded-{uuid4().hex[:8]}@example.com")
    db_session.add(ClinicMembership(user_id=stranded.id, clinic_id=other.id, role="admin"))
    await db_session.commit()

    response = await client.get("/api/v1/auth/users", headers=auth_headers)
    assert response.status_code == 200, response.text

    listed = _row(response.json(), stranded.email)
    assert listed is not None, "an account that can sign in was hidden from the admin"
    assert listed["has_clinic_access"] is False
    # Their role elsewhere is not this clinic's business, and saying "admin"
    # here would read as administrator *of this clinic*.
    assert listed["role"] is None


@pytest.mark.asyncio
async def test_members_of_this_clinic_keep_their_role(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    """The listing that already worked must not change shape."""
    member = await _make_user(db_session, f"member-{uuid4().hex[:8]}@example.com")
    db_session.add(
        ClinicMembership(user_id=member.id, clinic_id=test_clinic.id, role="receptionist")
    )
    await db_session.commit()

    response = await client.get("/api/v1/auth/users", headers=auth_headers)
    listed = _row(response.json(), member.email)

    assert listed is not None
    assert listed["role"] == "receptionist"
    assert listed["has_clinic_access"] is True


@pytest.mark.asyncio
async def test_each_account_is_listed_once(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    """A user with a membership here *and* elsewhere is one row, not two."""
    other = Clinic(
        id=uuid4(),
        name="Second Clinic",
        tax_id="B88888888",
        address={"street": "Elsewhere", "city": "Vigo"},
        settings={},
        account_tier="clinic",
    )
    db_session.add(other)
    both = await _make_user(db_session, f"both-{uuid4().hex[:8]}@example.com")
    db_session.add(ClinicMembership(user_id=both.id, clinic_id=test_clinic.id, role="dentist"))
    db_session.add(ClinicMembership(user_id=both.id, clinic_id=other.id, role="admin"))
    await db_session.commit()

    body = (await client.get("/api/v1/auth/users", headers=auth_headers)).json()
    rows = [u for u in body["data"] if u["email"] == both.email]

    assert len(rows) == 1
    assert rows[0]["role"] == "dentist", "the role shown must be the one for this clinic"
    assert rows[0]["has_clinic_access"] is True
    assert body["total"] == len(body["data"])
