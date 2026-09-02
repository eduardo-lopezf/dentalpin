"""Authentication service for JWT and password handling."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import bcrypt
from jose import jwt

from app.config import settings


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validate password meets minimum requirements.

    Returns (is_valid, error_message).
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters"

    has_letter = any(c.isalpha() for c in password)
    has_number = any(c.isdigit() for c in password)

    if not has_letter or not has_number:
        return False, "Password must contain at least one letter and one number"

    return True, ""


def create_access_token(
    user_id: UUID,
    clinic_id: UUID | None = None,
    token_version: int = 0,
) -> str:
    """Create a JWT access token."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "access",
        "token_version": token_version,
    }
    if clinic_id:
        payload["clinic_id"] = str(clinic_id)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: UUID, token_version: int = 0, jti: UUID | None = None) -> str:
    """Create a JWT refresh token.

    ``jti`` names the ``auth_sessions`` row that decides whether this
    token is still usable (ADR 0029, invariant 3). It is optional only so
    that callers which have no session to point at — none in production —
    still get a token; a refresh presented without one is rejected,
    because a token nothing can revoke is the thing this replaced.
    """
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
        "token_version": token_version,
    }
    if jti is not None:
        payload["jti"] = str(jti)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Raises JWTError if token is invalid or expired.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
