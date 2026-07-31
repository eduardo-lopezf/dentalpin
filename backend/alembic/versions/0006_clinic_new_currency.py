"""core — change clinics.currency default from EUR to MXN.

Only the server_default changes. Existing rows keep whatever value
they already have (typically ``EUR``, inherited from 0005) — this
migration does not backfill or rewrite existing clinic data. Clinics
created from this point on (including the SystemSetup / first-run
flow, when no currency is explicitly chosen) default to MXN instead.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "clinics",
        "currency",
        server_default="MXN",
    )


def downgrade() -> None:
    op.alter_column(
        "clinics",
        "currency",
        server_default="EUR",
    )
