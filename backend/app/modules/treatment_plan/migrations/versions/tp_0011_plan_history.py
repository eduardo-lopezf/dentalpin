"""Who changed a plan, what they changed, and when.

A plan is a contract with the patient and its price moves with it, so
"the budget says something different from what I remember agreeing to"
has to be answerable. The budget side already keeps ``budget_history``;
the plan side kept nothing, so a reopen that cancelled a budget and a
re-confirmation that minted a new one left no trace anybody could read.

Append-only by convention. ``ON DELETE CASCADE`` on the plan because the
history of a hard-deleted plan has nothing left to describe — plans are
soft-deleted in normal operation, so this only fires on a real removal.

Revision ID: tp_0011
Revises: tp_0010
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "tp_0011"
down_revision: str | None = "tp_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "treatment_plan_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("treatment_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["treatment_plan_id"], ["treatment_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_treatment_plan_history_clinic_id",
        "treatment_plan_history",
        ["clinic_id"],
    )
    op.create_index(
        "ix_treatment_plan_history_treatment_plan_id",
        "treatment_plan_history",
        ["treatment_plan_id"],
    )
    # The panel reads one plan's entries newest first; this is that query.
    op.create_index(
        "idx_tp_history_plan_created",
        "treatment_plan_history",
        ["treatment_plan_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_tp_history_plan_created", table_name="treatment_plan_history")
    op.drop_index(
        "ix_treatment_plan_history_treatment_plan_id", table_name="treatment_plan_history"
    )
    op.drop_index("ix_treatment_plan_history_clinic_id", table_name="treatment_plan_history")
    op.drop_table("treatment_plan_history")
