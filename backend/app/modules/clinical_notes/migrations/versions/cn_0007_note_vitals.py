"""Vital signs on a clinical note.

An evolution note carries the readings taken at that visit — blood
pressure, heart and respiratory rate, temperature — next to its text.

Revision ID: cn_0007
Revises: cn_0006
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "cn_0007"
down_revision: str | None = "cn_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("clinical_notes", sa.Column("vitals", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("clinical_notes", "vitals")
