"""core — record exercised subject rights.

An erasure is irreversible and leaves the data looking as if it had never
been there, so without a record the clinic cannot prove it honoured the
request, and cannot tell an erasure apart from a bug that emptied the
columns. ``core_subject_request`` is that record (ADR 0026).

It holds no personal data of its own beyond the patient id it acted on —
the outcome describes what was done, not what the data said — so it
survives the erasure it documents.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "core_subject_request",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        # No FK on purpose: the record must outlive whatever happens to
        # the row it points at.
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("outcome", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_core_subject_request_clinic_id", "core_subject_request", ["clinic_id"]
    )
    op.create_index(
        "ix_core_subject_request_patient_id", "core_subject_request", ["patient_id"]
    )
    op.create_index(
        "ix_core_subject_request_created_at", "core_subject_request", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_core_subject_request_created_at", table_name="core_subject_request")
    op.drop_index("ix_core_subject_request_patient_id", table_name="core_subject_request")
    op.drop_index("ix_core_subject_request_clinic_id", table_name="core_subject_request")
    op.drop_table("core_subject_request")
