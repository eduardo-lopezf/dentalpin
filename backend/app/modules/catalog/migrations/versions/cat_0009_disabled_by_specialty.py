"""A treatment switched off with its discipline, apart from one retired by hand.

Disabling a specialty pack deactivates the treatments that belong to no
other enabled discipline. Enabling it again has to bring exactly those
back — and leave alone a treatment the clinic deactivated on its own.

Revision ID: cat_0009
Revises: cat_0008
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "cat_0009"
down_revision: str | None = "cat_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "treatment_catalog_items",
        sa.Column("disabled_by_specialty", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("treatment_catalog_items", "disabled_by_specialty")
