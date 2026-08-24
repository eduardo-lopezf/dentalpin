"""Record the stage of care on each planned item.

Seeded from the catalog item's ``default_phase`` when the item is added to
a plan, then owned by the plan: the same extraction is an emergency for one
patient and a step of a planned rehabilitation for another, so the decision
belongs to the plan rather than to the catalog row.

``depends_on`` pins cat_0007, which introduces the vocabulary.

Revision ID: tp_0008
Revises: tp_0007
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "tp_0008"
down_revision: str | None = "tp_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = "cat_0007"


def upgrade() -> None:
    op.add_column(
        "planned_treatment_items",
        sa.Column("phase", sa.String(length=20), nullable=True),
    )
    op.create_index("idx_planned_items_phase", "planned_treatment_items", ["phase"])


def downgrade() -> None:
    op.drop_index("idx_planned_items_phase", table_name="planned_treatment_items")
    op.drop_column("planned_treatment_items", "phase")
