"""core — refresh-token sessions, so a login can be ended.

``User.token_version`` was the only revocation the system had: a global
switch that logs a user out of every device at once, incremented in
exactly one place — when an account is deactivated. A clinic that lost a
laptop could not end *that* session without ending every other one, and a
stolen refresh token stayed valid for its full seven days.

``auth_sessions`` holds one row per refresh token, keyed by the token's
``jti``, with every row descending from one login sharing a
``family_id``. Rotation stamps ``rotated_at`` and issues a successor;
presenting a spent token means two holders and revokes the family
(ADR 0029, invariant 3).

Holds no IP and no user agent — both are personal data needing
classification and retention (ADR 0025), and neither is needed to end a
session, only to label one in a UI that does not exist yet.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        # The refresh token's ``jti``, not a surrogate key.
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(20), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    # Revoking a family is the hot path of reuse detection and of logout.
    op.create_index("ix_auth_sessions_family_id", "auth_sessions", ["family_id"])


def downgrade() -> None:
    op.drop_index("ix_auth_sessions_family_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
