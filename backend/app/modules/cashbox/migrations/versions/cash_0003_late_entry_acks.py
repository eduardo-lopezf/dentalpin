"""cashbox — acknowledgements for entries that landed after a count.

A late entry is surfaced until somebody says what is being done about it.
Without a place to record that decision the list only grows, and a warning
that is always on is a warning nobody reads.

The entry is addressed by `(entry_kind, entry_id)` rather than a foreign
key: two of the three kinds live in `payments`, and an FK from here would be
a dependency the manifest does not declare.

Revision ID: cash_0003
Revises: cash_0002
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "cash_0003"
down_revision: str | None = "cash_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cash_late_entry_acks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("entry_kind", sa.String(length=10), nullable=False),
        sa.Column("entry_id", sa.UUID(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("resolution", sa.String(length=300), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["acknowledged_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "entry_kind", "entry_id", name="uq_cash_late_entry_ack"),
    )
    op.create_index(
        op.f("ix_cash_late_entry_acks_clinic_id"),
        "cash_late_entry_acks",
        ["clinic_id"],
    )
    op.create_index(
        "idx_cash_late_ack_clinic_date",
        "cash_late_entry_acks",
        ["clinic_id", "business_date"],
    )


def downgrade() -> None:
    op.drop_index("idx_cash_late_ack_clinic_date", table_name="cash_late_entry_acks")
    op.drop_index(op.f("ix_cash_late_entry_acks_clinic_id"), table_name="cash_late_entry_acks")
    op.drop_table("cash_late_entry_acks")
