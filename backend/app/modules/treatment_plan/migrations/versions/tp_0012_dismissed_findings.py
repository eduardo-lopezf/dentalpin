"""Findings the dentist decided this plan does not answer.

The builder seeds its draft from the patient's charted findings, so deleting
one of those lines is a clinical decision — "I saw the caries on 27 and this
plan is not for it" — and until now it left no trace. The plan was created,
the finding still had no planned work, and the plan's own proposals list
offered it straight back. The dentist dismissed it once and the app asked
again.

Scoped to the plan on purpose, which is what makes it safe: a dismissal says
nothing about the finding itself, only that *this* plan is not where it gets
treated. The chart keeps showing the caries, and the next plan offers it
again — a decision about one treatment plan must not quietly become a
decision to leave a tooth alone forever.

``ON DELETE CASCADE`` on both sides: a dismissal describes a pairing, and
with either half hard-deleted there is nothing left to describe. Plans are
soft-deleted in normal operation, so the plan side only fires on a real
removal.

Revision ID: tp_0012
Revises: tp_0011
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "tp_0012"
down_revision: str | None = "tp_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plan_dismissed_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("treatment_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dismissed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["treatment_plan_id"], ["treatment_plans.id"], ondelete="CASCADE"),
        # `odontogram` is in this module's `depends`, so the FK is allowed.
        sa.ForeignKeyConstraint(["finding_id"], ["treatments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dismissed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        # Dismissing twice is the same fact, and the write path is idempotent
        # because of it.
        sa.UniqueConstraint("treatment_plan_id", "finding_id", name="uq_plan_dismissed_finding"),
    )
    op.create_index(
        "ix_plan_dismissed_findings_clinic_id", "plan_dismissed_findings", ["clinic_id"]
    )
    op.create_index(
        "ix_plan_dismissed_findings_plan_id",
        "plan_dismissed_findings",
        ["treatment_plan_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_plan_dismissed_findings_plan_id", table_name="plan_dismissed_findings")
    op.drop_index("ix_plan_dismissed_findings_clinic_id", table_name="plan_dismissed_findings")
    op.drop_table("plan_dismissed_findings")
