"""Disclosures of a clinical record.

The first table the record owns: not clinical data — that stays with the
modules that recorded it — but the act of handing a record over, with the
document as it left and its digest (ADR 0033).

No foreign key to ``professionals``: that is another App's table
(ADR 0042). ``patients`` is ordered first through ``depends_on``.

Revision ID: exp_0002
Revises: exp_0001
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "exp_0002"
down_revision: str | None = "exp_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = ("pat_0001",)


def upgrade() -> None:
    op.create_table(
        "record_disclosure",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("recipient_name", sa.String(200), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("identity_verified", sa.Boolean(), nullable=False),
        sa.Column("scope", postgresql.JSONB(), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("document", sa.LargeBinary(), nullable=False),
        sa.Column("document_sha256", sa.String(64), nullable=False),
        sa.Column("locale", sa.String(5), nullable=False),
        sa.Column("disclosed_by_user_id", sa.UUID(), nullable=False),
        sa.Column("disclosed_by_professional_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["disclosed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_record_disclosure_clinic_id", "record_disclosure", ["clinic_id"])
    op.create_index(
        "ix_record_disclosure_patient", "record_disclosure", ["clinic_id", "patient_id"]
    )


def downgrade() -> None:
    op.drop_table("record_disclosure")
