"""professionals: initial clinic directory schema.

Revision ID: pro_0001
Revises: 0001
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "pro_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("professionals",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "professionals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("professional_type", sa.String(length=20), nullable=False),
        sa.Column("specialty", sa.String(length=150), nullable=True),
        sa.Column("license_number", sa.String(length=80), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("photo_url", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_professionals_clinic_id", "professionals", ["clinic_id"], unique=False)
    op.create_index(
        "ix_professionals_clinic_name",
        "professionals",
        ["clinic_id", "last_name", "first_name"],
        unique=False,
    )
    op.create_index(
        "ix_professionals_clinic_type_active",
        "professionals",
        ["clinic_id", "professional_type", "is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_professionals_clinic_type_active", table_name="professionals")
    op.drop_index("ix_professionals_clinic_name", table_name="professionals")
    op.drop_index("ix_professionals_clinic_id", table_name="professionals")
    op.drop_table("professionals")
