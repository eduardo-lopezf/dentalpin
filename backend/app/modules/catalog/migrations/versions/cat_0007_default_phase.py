"""Add the stage-of-care axis to catalog items.

Third and last axis alongside category (where a treatment is filed) and
specialty (who performs it): ``default_phase`` says *when* in a course of
care it belongs — diagnóstico, urgencia, preventivo, estabilización,
rehabilitación, estética electiva, mantenimiento.

Nullable: an unclassified treatment is honest about being unclassified, and
the seeder fills the known ones.

Revision ID: cat_0007
Revises: cat_0006
Create Date: 2026-08-23

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "cat_0007"
down_revision: str | None = "cat_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "treatment_catalog_items",
        sa.Column("default_phase", sa.String(length=20), nullable=True),
    )
    op.create_index(
        "idx_catalog_items_phase",
        "treatment_catalog_items",
        ["default_phase"],
    )


def downgrade() -> None:
    op.drop_index("idx_catalog_items_phase", table_name="treatment_catalog_items")
    op.drop_column("treatment_catalog_items", "default_phase")
