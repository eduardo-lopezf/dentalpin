"""How a consent was signed: on screen, or on paper and scanned.

Revision ID: con_0002
Revises: con_0001
Create Date: 2026-10-03

Every signature recorded so far was drawn on a screen — it was the only
way — so the rows that carry one are marked as such.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "con_0002"
down_revision: str | None = "con_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("consents_consent", sa.Column("signature_method", sa.String(20), nullable=True))
    op.execute(
        "UPDATE consents_consent SET signature_method = 'screen' WHERE signed_at IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("consents_consent", "signature_method")
