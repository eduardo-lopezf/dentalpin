"""core — bounded refresh families and idle activity policy.

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "auth_sessions",
        sa.Column("family_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "auth_sessions",
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            """
            WITH family_starts AS (
                SELECT family_id, MIN(created_at) AS created_at
                FROM auth_sessions
                GROUP BY family_id
            )
            UPDATE auth_sessions AS session
            SET family_expires_at = family_starts.created_at + INTERVAL '30 days',
                last_activity_at = now()
            FROM family_starts
            WHERE session.family_id = family_starts.family_id
            """
        )
    )
    op.alter_column("auth_sessions", "family_expires_at", nullable=False)
    op.alter_column("auth_sessions", "last_activity_at", nullable=False)


def downgrade() -> None:
    op.drop_column("auth_sessions", "last_activity_at")
    op.drop_column("auth_sessions", "family_expires_at")
