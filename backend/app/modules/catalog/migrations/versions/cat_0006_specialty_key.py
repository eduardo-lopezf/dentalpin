"""Give specialties a stable key.

Seeded specialties need an identifier that survives renaming, the same way
``treatment_categories.key`` does: without it, a clinic that renames
"Ortodoncia" gets a second one the next time the seed runs. Clinic-created
specialties keep ``key`` NULL, so the uniqueness index is partial.

Revision ID: cat_0006
Revises: cat_0005
Create Date: 2026-08-23

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "cat_0006"
down_revision: str | None = "cat_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("specialties", sa.Column("key", sa.String(length=50), nullable=True))
    op.create_index(
        "uq_specialty_clinic_key",
        "specialties",
        ["clinic_id", "key"],
        unique=True,
        postgresql_where=sa.text("key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_specialty_clinic_key", table_name="specialties")
    op.drop_column("specialties", "key")
