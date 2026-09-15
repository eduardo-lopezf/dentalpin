"""cashbox — the daily arqueo.

Adds `cash_closings` and the FK from `cash_movements.closing_id`, which
phase 1 left nullable and unconstrained because the target table did not
exist yet.

Revision ID: cash_0002
Revises: cash_0001
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "cash_0002"
down_revision: str | None = "cash_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cash_closings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("opening_float", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("expected_cash", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("counted_cash", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("difference", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("closing_float", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "snapshot",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_by", sa.UUID(), nullable=False),
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reopened_by", sa.UUID(), nullable=True),
        sa.Column("reopen_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("opening_float >= 0", name="ck_cash_closing_opening_float"),
        sa.CheckConstraint("counted_cash >= 0", name="ck_cash_closing_counted_cash"),
        sa.CheckConstraint("closing_float >= 0", name="ck_cash_closing_closing_float"),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["closed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["reopened_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cash_closings_clinic_id"), "cash_closings", ["clinic_id"], unique=False
    )
    op.create_index("idx_cash_closing_clinic_date", "cash_closings", ["clinic_id", "business_date"])
    # Partial: at most one *standing* count per day. The superseded rows a
    # reopen leaves behind must not collide with the count that replaces
    # them, and the database is a better place for that rule than the
    # service remembering to check.
    op.create_index(
        "uq_cash_closing_standing_day",
        "cash_closings",
        ["clinic_id", "business_date"],
        unique=True,
        postgresql_where=sa.text("status = 'closed'"),
    )

    # The constraint phase 1 could not create: the target table now exists.
    # RESTRICT, not CASCADE — a closing is never deleted, and if one ever
    # were, taking the movements with it would erase the day it counted.
    op.create_foreign_key(
        "fk_cash_movement_closing",
        "cash_movements",
        "cash_closings",
        ["closing_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_cash_movement_closing", "cash_movements", type_="foreignkey")
    op.drop_index("uq_cash_closing_standing_day", table_name="cash_closings")
    op.drop_index("idx_cash_closing_clinic_date", table_name="cash_closings")
    op.drop_index(op.f("ix_cash_closings_clinic_id"), table_name="cash_closings")
    op.drop_table("cash_closings")
