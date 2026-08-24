"""Link catalog items to specialties.

Completes the follow-up left open by ``cat_0004``: treatments can now be
classified by dental specialty. Many-to-many because a treatment may be
performed under more than one discipline (e.g. a simple extraction is
both general practice and oral surgery).

Revision ID: cat_0005
Revises: cat_0004
Create Date: 2026-08-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "cat_0005"
down_revision: str | None = "cat_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "catalog_item_specialties",
        sa.Column(
            "catalog_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("treatment_catalog_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "specialty_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("specialties.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_index(
        "idx_catalog_item_specialties_specialty",
        "catalog_item_specialties",
        ["specialty_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_catalog_item_specialties_specialty",
        table_name="catalog_item_specialties",
    )
    op.drop_table("catalog_item_specialties")
