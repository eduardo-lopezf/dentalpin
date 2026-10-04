"""core — the workspace's own logo.

What the sidebar shows next to the workspace's name, in place of the
product's mark. The name is a key of ``clinics.settings``; the image is
here, because the settings travel with every request.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clinic_brand_logos",
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("image", sa.LargeBinary(), nullable=False),
        sa.Column("mime_type", sa.String(40), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("clinic_id"),
    )


def downgrade() -> None:
    op.drop_table("clinic_brand_logos")
