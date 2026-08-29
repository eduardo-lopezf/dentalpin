"""core — rename clinics.tenant_type to clinics.account_tier.

The column added in 0007 holds a commercial tier (basic … hospital) for
one clinic. "Tenant" means something else in this codebase: the
DB-isolation unit that a clinic lives *inside* (ADR 0012). With the
custody model landing on the tenant (ADR 0023), a future control plane
would carry ``tenants.custody_mode`` next to ``clinics.tenant_type`` and
the two would read as the same axis. They are not related at all.

Rename now, while nothing gates on the column.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A rename, not a drop/add: existing tiers survive, and the NOT NULL
    # plus the ``clinic`` server_default ride along with the column.
    op.alter_column("clinics", "tenant_type", new_column_name="account_tier")


def downgrade() -> None:
    op.alter_column("clinics", "account_tier", new_column_name="tenant_type")
