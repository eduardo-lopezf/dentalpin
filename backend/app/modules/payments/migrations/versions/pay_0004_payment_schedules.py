"""Agreed payment schedules.

The earned ledger answers "what is owed for work already done" — the right
question for a filling, the wrong one for a 19.000 € orthognathic case, where
the money is agreed up front and collected long before most of the work
exists. A schedule records that agreement.

Whether an instalment is paid is derived at read time from the same payments
the earned ledger settles against, so there is no status column here to drift
out of sync with the money.

``depends_on`` pins bud_0001: ``budget_id`` is a cross-module FK and ``budget``
is in this module's ``manifest.depends``.

Revision ID: pay_0004
Revises: pay_0003
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "pay_0004"
down_revision: str | None = "pay_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = "bud_0001"


def upgrade() -> None:
    op.create_table(
        "payment_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("budget_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["budget_id"], ["budgets.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_schedules_clinic_id", "payment_schedules", ["clinic_id"])
    op.create_index("ix_payment_schedules_patient_id", "payment_schedules", ["patient_id"])
    op.create_index("ix_payment_schedules_budget_id", "payment_schedules", ["budget_id"])
    op.create_index(
        "idx_payment_schedules_clinic_patient", "payment_schedules", ["clinic_id", "patient_id"]
    )
    op.create_index("idx_payment_schedules_budget", "payment_schedules", ["budget_id"])

    op.create_table(
        "payment_schedule_instalments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["schedule_id"], ["payment_schedules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("schedule_id", "sequence", name="uq_schedule_instalment_sequence"),
    )
    op.create_index(
        "ix_payment_schedule_instalments_clinic_id", "payment_schedule_instalments", ["clinic_id"]
    )
    op.create_index(
        "ix_payment_schedule_instalments_schedule_id",
        "payment_schedule_instalments",
        ["schedule_id"],
    )
    op.create_index(
        "idx_schedule_instalments_schedule", "payment_schedule_instalments", ["schedule_id"]
    )


def downgrade() -> None:
    op.drop_table("payment_schedule_instalments")
    op.drop_table("payment_schedules")
