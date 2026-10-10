"""core — the Apps a clinic may switch on by itself.

Beside ``clinics.apps`` (what the clinic has), the Apps its administrator
can enable from Settings → Apps without asking the operator. Anything on
neither list is not available to the clinic. Empty for every clinic that
exists: nobody offered them anything.

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("clinics", sa.Column("available_apps", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("clinics", "available_apps")
