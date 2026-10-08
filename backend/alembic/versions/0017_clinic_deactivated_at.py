"""core — when a clinic was deactivated.

Set by the operator's control plane (``POST /api/v1/ops/clinics/{id}/deactivate``).
While it is set nobody can work in the clinic: ``get_clinic_context``
refuses it. Nothing of the clinic is touched, and clearing it brings
everything back. Empty for every clinic that exists.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("clinics", sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("clinics", "deactivated_at")
