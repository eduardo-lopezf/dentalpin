"""core — add clinics.tenant_type (account/business tier).

Reserves the account-tier taxonomy agreed for the individual/clinic
roadmap: basic, medium, advanced, clinic, clinic_pro, hospital. Only
``clinic`` has real functionality today (the current staffed-clinic
product) — the rest are reserved names with no gated behavior yet. Root
is deliberately excluded: it is a platform-level actor, not a tenant
type, and does not belong in this column.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "clinics",
        sa.Column("tenant_type", sa.String(length=20), nullable=False, server_default="clinic"),
    )


def downgrade() -> None:
    op.drop_column("clinics", "tenant_type")
