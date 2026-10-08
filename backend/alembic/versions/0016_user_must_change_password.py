"""core — a password the user has to replace at the next sign-in.

Set on an account somebody else created with a password its owner did not
choose — today the holder of a clinic the control plane creates. While it
is set the account can sign in and change its password, and nothing else.

Every existing account gets ``false``: their passwords are their own.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
