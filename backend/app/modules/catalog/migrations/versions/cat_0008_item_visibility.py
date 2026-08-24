"""Curate which treatments appear on the clinical list.

`is_visible` gates the /treatments page only. It is deliberately separate
from `is_active`: a clinic that shows its forty usual treatments still needs
the rest active so budgets, the odontogram and past invoices keep working.

Defaults to true so existing catalogs keep listing everything until someone
narrows the list on purpose — the alternative empties the page on upgrade.

Revision ID: cat_0008
Revises: cat_0007
Create Date: 2026-08-24

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "cat_0008"
down_revision: str | None = "cat_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "treatment_catalog_items",
        sa.Column(
            "is_visible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("treatment_catalog_items", "is_visible")
