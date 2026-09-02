"""Refresh-token sessions: rotation, reuse detection, revocation.

ADR 0029, invariant 3. The rules this file implements, in one place
because they only make sense together:

1. **A refresh token is spent when it is used.** Every exchange stamps
   ``rotated_at`` on the presented row and issues a new one. A refresh
   token therefore has exactly one legitimate use.

2. **Reuse means theft, and we cannot tell whose.** A bearer credential
   presented twice has two holders. Which one is the attacker is not
   knowable from the request, so the whole family is revoked and both
   have to authenticate again. Refusing only the second presentation
   would leave the thief holding a working chain.

3. **Logout ends the family, not the row.** Ending only the presented
   token would leave its already-issued successors alive, which is not
   what anyone means by logging out.

``User.token_version`` is untouched and still works: it stays the
per-user emergency switch that invalidates *access* tokens too, which
this table cannot do — an access token is stateless by design and lives
15 minutes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

from .models import AuthSession


class RefreshReuseError(Exception):
    """A spent or revoked refresh token was presented again.

    Separate from "unknown token" on purpose: the caller answers both
    with 401, but only this one means a live session family was just
    destroyed, and only this one is worth a log line an operator can act
    on.
    """


async def start_session(db: AsyncSession, user_id: UUID) -> AuthSession:
    """Open a new family. Called on login and on first-run setup."""
    family_id = uuid4()
    session = AuthSession(
        id=uuid4(),
        user_id=user_id,
        family_id=family_id,
        expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(session)
    return session


async def revoke_family(db: AsyncSession, family_id: UUID, reason: str) -> int:
    """Kill every row in a family. Returns how many were still usable."""
    result = await db.execute(
        update(AuthSession)
        .where(
            AuthSession.family_id == family_id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC), revoked_reason=reason)
    )
    return result.rowcount or 0


async def rotate(db: AsyncSession, jti: UUID) -> AuthSession:
    """Spend the token named by ``jti`` and open its successor.

    Raises :class:`RefreshReuseError` when the token was already spent or
    revoked — and revokes the family before raising, because the caller
    must not be able to forget to.

    Raises :class:`LookupError` when no such row exists: an unknown
    ``jti`` is a forged or long-purged token, and there is no family to
    punish for it.
    """
    session = await db.get(AuthSession, jti)

    if session is None:
        raise LookupError(f"no session for jti {jti}")

    if not session.is_usable:
        await revoke_family(db, session.family_id, "reuse")
        raise RefreshReuseError(f"refresh token {jti} was already spent")

    now = datetime.now(UTC)
    if session.expires_at <= now:
        raise LookupError(f"session {jti} expired")

    session.rotated_at = now
    successor = AuthSession(
        id=uuid4(),
        user_id=session.user_id,
        family_id=session.family_id,
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(successor)
    return successor


async def end_session(db: AsyncSession, jti: UUID) -> bool:
    """Log out: revoke the family the token belongs to.

    Returns False for an unknown ``jti`` so the caller can stay quiet
    about it — a logout that reports whether a token was real is an
    oracle, and logging out is not an operation worth failing.
    """
    session = await db.get(AuthSession, jti)
    if session is None:
        return False

    await revoke_family(db, session.family_id, "logout")
    return True


async def usable_sessions(db: AsyncSession, user_id: UUID) -> list[AuthSession]:
    """Sessions a user could still refresh with. For tests and, later, a UI."""
    result = await db.execute(
        select(AuthSession).where(
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.rotated_at.is_(None),
            AuthSession.expires_at > datetime.now(UTC),
        )
    )
    return list(result.scalars().all())
