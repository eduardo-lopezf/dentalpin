"""Prescriptions written from a plan treatment.

A prescription is printed and handed to the patient, so what was printed
has to be on record: the text, and the doctor's name and licence as they
were that day. The doctor block is a snapshot for the same reason.

``plan_item_id`` is ``ON DELETE SET NULL``: removing a treatment from a
plan hard-deletes the line, and the prescription is clinical history that
outlives it.

Revision ID: tp_0013
Revises: tp_0012
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "tp_0013"
down_revision: str | None = "tp_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "treatment_prescriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("treatment_label", sa.String(length=200), nullable=True),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("professional_name", sa.String(length=200), nullable=False),
        sa.Column("professional_license", sa.String(length=80), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("issued_by", postgresql.UUID(as_uuid=True), nullable=True),
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
        # `patients` and `professionals` are in this module's `depends`.
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(
            ["plan_item_id"], ["planned_treatment_items.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["professional_id"], ["professionals.id"]),
        sa.ForeignKeyConstraint(["issued_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_treatment_prescriptions_clinic_id", "treatment_prescriptions", ["clinic_id"]
    )
    op.create_index(
        "ix_treatment_prescriptions_patient_id", "treatment_prescriptions", ["patient_id"]
    )
    op.create_index(
        "ix_treatment_prescriptions_plan_item_id", "treatment_prescriptions", ["plan_item_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_treatment_prescriptions_plan_item_id", table_name="treatment_prescriptions")
    op.drop_index("ix_treatment_prescriptions_patient_id", table_name="treatment_prescriptions")
    op.drop_index("ix_treatment_prescriptions_clinic_id", table_name="treatment_prescriptions")
    op.drop_table("treatment_prescriptions")
