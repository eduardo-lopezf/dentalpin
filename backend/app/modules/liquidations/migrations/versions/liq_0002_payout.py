"""liquidations — recording that the settlement was handed over.

The payout state lives on the `liquidations` row rather than a table of its
own: a settlement is paid once, and "issued but not yet paid" is a state of
the document, not an event with a life of its own.

`cash_movement_id` is a cross-module foreign key, allowed because `cashbox`
is in `manifest.depends`. Ordered with `depends_on` rather than by hanging
`down_revision` off the cashbox head — threading one module's revisions
through another's merges the branches (issue #56, ADR 0002).

RESTRICT, not CASCADE: a till movement inside a counted day is part of a
number somebody signed, and deleting it out from under the settlement that
points at it would leave the payout claiming money that no longer moved.

Revision ID: liq_0002
Revises: liq_0001
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "liq_0002"
down_revision: str | None = "liq_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = ("cashbox",)


def upgrade() -> None:
    op.add_column("liquidations", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("liquidations", sa.Column("paid_by", sa.UUID(), nullable=True))
    op.add_column("liquidations", sa.Column("payment_method", sa.String(length=10), nullable=True))
    op.add_column("liquidations", sa.Column("cash_movement_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_liquidation_paid_by", "liquidations", "users", ["paid_by"], ["id"])
    op.create_foreign_key(
        "fk_liquidation_cash_movement",
        "liquidations",
        "cash_movements",
        ["cash_movement_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_liquidation_cash_movement", "liquidations", type_="foreignkey")
    op.drop_constraint("fk_liquidation_paid_by", "liquidations", type_="foreignkey")
    op.drop_column("liquidations", "cash_movement_id")
    op.drop_column("liquidations", "payment_method")
    op.drop_column("liquidations", "paid_by")
    op.drop_column("liquidations", "paid_at")
