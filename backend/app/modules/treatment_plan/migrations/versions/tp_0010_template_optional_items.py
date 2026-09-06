"""Template lines that a clinic — or a patient — may not need.

A plan shape is rarely all-or-nothing. An orthognathic case needs pre- and
post-surgical orthodontics, but the clinic may refer that out, and the
genioplasty depends on the chin. Forcing those into the template meant
applying it and then deleting rows; leaving them out meant remembering to add
them by hand on most patients.

``is_optional`` marks a line as a decision rather than a given. Optional lines
are offered ticked when the template is applied — the author put them there
because they usually apply — and one click removes them.

Revision ID: tp_0010
Revises: tp_0009
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "tp_0010"
down_revision: str | None = "tp_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "plan_template_items",
        sa.Column("is_optional", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("plan_template_items", "is_optional")
