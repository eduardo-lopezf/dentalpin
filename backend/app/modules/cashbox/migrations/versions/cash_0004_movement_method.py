"""cashbox — how a movement was paid.

The table was the till and nothing else: every row was cash by definition,
which is why this column arrives with a server default of `cash` and needs
no backfill. Every historical row is already correct under the new meaning.

What it unlocks is the half of the money the system could not see. A clinic
pays its lab by transfer, its rent by direct debit, its supplier on thirty
days — none of that ever passes through a drawer, so none of it could be
recorded, so no figure in the product was ever an outflow.

The arqueo is unaffected by construction: it counts `method = 'cash'` only,
and before this revision that was every row.

Revision ID: cash_0004
Revises: cash_0003
Create Date: 2026-09-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "cash_0004"
down_revision: str | None = "cash_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NOT NULL with a server default in one statement: Postgres fills the
    # existing rows itself, so there is no window in which the column is
    # nullable and no separate UPDATE over a table that may be large.
    op.add_column(
        "cash_movements",
        sa.Column(
            "method",
            sa.String(length=20),
            nullable=False,
            server_default="cash",
        ),
    )


def downgrade() -> None:
    op.drop_column("cash_movements", "method")
