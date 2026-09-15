"""cashbox module — initial schema (till movements).

Hangs off the core chain rather than another module's: the only foreign
keys are ``clinics.id`` and ``users.id``, both core tables, so threading
through a sibling's revisions would buy nothing and cost uninstall safety
(issue #56, ADR 0002).

Revision ID: cash_0001
Revises: 0001
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "cash_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("cashbox",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cash_movements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("direction", sa.String(length=3), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("concept", sa.String(length=160), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # No FK: `cash_closings` arrives in phase 2 and a constraint
        # against a table that does not exist will not create.
        sa.Column("closing_id", sa.UUID(), nullable=True),
        sa.Column("recorded_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_cash_movement_amount_positive"),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cash_movements_clinic_id"), "cash_movements", ["clinic_id"], unique=False
    )
    op.create_index(
        "idx_cash_movement_clinic_date", "cash_movements", ["clinic_id", "business_date"]
    )
    op.create_index("idx_cash_movement_closing", "cash_movements", ["closing_id"])


def downgrade() -> None:
    op.drop_index("idx_cash_movement_closing", table_name="cash_movements")
    op.drop_index("idx_cash_movement_clinic_date", table_name="cash_movements")
    op.drop_index(op.f("ix_cash_movements_clinic_id"), table_name="cash_movements")
    op.drop_table("cash_movements")
