"""The health questionnaire a patient answers at a visit.

A dated declaration — chief complaint, yes/no answers with their cause,
the conditions ticked — kept as given, on screen or as a scanned sheet.

Revision ID: pc_0005
Revises: pc_0004
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "pc_0005"
down_revision: str | None = "pc_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "patients_clinical_health_questionnaire"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("form_version", sa.String(10), nullable=False),
        sa.Column("chief_complaint", sa.Text(), nullable=True),
        sa.Column("blood_type", sa.String(10), nullable=True),
        sa.Column("declared_allergies", sa.Text(), nullable=True),
        sa.Column("answers", postgresql.JSONB(), nullable=False),
        sa.Column("conditions", postgresql.JSONB(), nullable=False),
        sa.Column("drugs_detail", sa.String(300), nullable=True),
        sa.Column("other_conditions", sa.Text(), nullable=True),
        sa.Column("scan_document_id", sa.UUID(), nullable=True),
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
