"""Family history: the conditions that run in a patient's family.

The *antecedentes heredo-familiares* a clinical history carries under
NOM-004-SSA3-2012. Born with the lifecycle and attribution columns the
other history tables acquired in `pc_0002` and `pc_0003` (ADR 0032).

Revision ID: pc_0004
Revises: pc_0003
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "pc_0004"
down_revision: str | None = "pc_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "patients_clinical_family_history"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("condition", sa.String(200), nullable=False),
        sa.Column("relative", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retraction_reason", sa.Text(), nullable=True),
        sa.Column("recorded_by_user_id", sa.UUID(), nullable=True),
        sa.Column("recorded_by_professional_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["recorded_by_professional_id"], ["professionals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("patient_id", "clinic_id", "ended_at", "retracted_at"):
        op.create_index(f"ix_{_TABLE}_{column}", _TABLE, [column])


def downgrade() -> None:
    op.drop_table(_TABLE)
