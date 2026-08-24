"""Add specialties table.

First step towards classifying treatments by dental specialty
(e.g. "Cirugía Oral y Maxilofacial") independently from their
catalog category, and eventually matching them to the professionals
qualified to perform them. This migration only introduces the
specialty catalog itself; assigning specialties to treatments and
dentists is a separate follow-up.

Revision ID: cat_0004
Revises: cat_0003
Create Date: 2026-08-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "cat_0004"
down_revision: str | None = "cat_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "specialties",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "clinic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clinics.id"),
            nullable=False,
        ),
        sa.Column(
            "names",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
    )
    op.create_index("idx_specialties_clinic", "specialties", ["clinic_id"])


def downgrade() -> None:
    op.drop_index("idx_specialties_clinic", table_name="specialties")
    op.drop_table("specialties")
