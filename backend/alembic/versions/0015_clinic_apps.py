"""core — the Apps chosen for a clinic when it was created.

A list of App names from ``apps.json``, recorded by the control plane's
``POST /api/v1/ops/clinics``. Nullable and left empty for every clinic
that already exists: nobody chose for them, and they have every App.

Recorded, not enforced — what runs is still decided for the whole
deployment (ADR 0038).

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("clinics", sa.Column("apps", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("clinics", "apps")
