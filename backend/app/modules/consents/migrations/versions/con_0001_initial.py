"""Consent letters and their templates.

Revision ID: con_0001
Revises: 0001 (branch root)
Create Date: 2026-10-03

``patients`` is declared through ``depends_on`` so its table exists first
without this branch hanging off that one (issue #56, ADR 0002). There is
deliberately no foreign key to ``professionals`` or to treatment plans:
those are other Apps' tables (ADR 0042).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "con_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("consents",)
depends_on: str | Sequence[str] | None = ("pat_0001",)


def upgrade() -> None:
    op.create_table(
        "consents_template",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consents_template_clinic_id", "consents_template", ["clinic_id"])

    op.create_table(
        "consents_consent",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("template_id", sa.UUID(), nullable=True),
        sa.Column("template_version", sa.Integer(), nullable=True),
        sa.Column("procedure_label", sa.String(length=200), nullable=True),
        sa.Column("plan_id", sa.UUID(), nullable=True),
        sa.Column("explained_by_professional_id", sa.UUID(), nullable=True),
        sa.Column("explained_by_name", sa.String(length=200), nullable=True),
        sa.Column("explained_by_license", sa.String(length=80), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signed_by_name", sa.String(length=200), nullable=True),
        sa.Column("signer_capacity", sa.String(length=20), nullable=True),
        sa.Column("signature_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("declined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_note", sa.Text(), nullable=True),
        sa.Column("recorded_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["consents_template.id"]),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consents_consent_clinic_id", "consents_consent", ["clinic_id"])
    op.create_index("ix_consents_consent_status", "consents_consent", ["status"])
    op.create_index("ix_consents_consent_patient", "consents_consent", ["clinic_id", "patient_id"])


def downgrade() -> None:
    op.drop_index("ix_consents_consent_patient", table_name="consents_consent")
    op.drop_index("ix_consents_consent_status", table_name="consents_consent")
    op.drop_index("ix_consents_consent_clinic_id", table_name="consents_consent")
    op.drop_table("consents_consent")
    op.drop_index("ix_consents_template_clinic_id", table_name="consents_template")
    op.drop_table("consents_template")
