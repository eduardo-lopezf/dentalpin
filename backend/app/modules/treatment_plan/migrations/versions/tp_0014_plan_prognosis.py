"""A plan states its prognosis, next to its diagnosis.

NOM-004-SSA3-2012 asks a clinical history for diagnosis, prognosis and
therapeutic indication together. The plan already held the first and the
last.

Revision ID: tp_0014
Revises: tp_0013
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "tp_0014"
down_revision: str | None = "tp_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("treatment_plans", sa.Column("prognosis", sa.String(20), nullable=True))
    op.add_column("treatment_plans", sa.Column("prognosis_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("treatment_plans", "prognosis_notes")
    op.drop_column("treatment_plans", "prognosis")
