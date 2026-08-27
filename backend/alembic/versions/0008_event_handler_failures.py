"""core — record event-handler failures instead of only logging them.

The bus swallows handler exceptions so one broken subscriber cannot
abort a dispatch. Since ADR 0019 handlers run after the publisher's
commit, so a swallowed failure means the fact is durable and the
reaction is gone, with nothing queryable to say so. ``core_event_failure``
is that record.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "core_event_failure",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("handler", sa.String(length=255), nullable=False),
        sa.Column("module", sa.String(length=100), nullable=True),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error", sa.String(length=2000), nullable=False),
        sa.Column("traceback", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_core_event_failure_created", "core_event_failure", ["created_at"])
    op.create_index("ix_core_event_failure_event_type", "core_event_failure", ["event_type"])
    op.create_index("ix_core_event_failure_clinic_id", "core_event_failure", ["clinic_id"])


def downgrade() -> None:
    op.drop_index("ix_core_event_failure_clinic_id", table_name="core_event_failure")
    op.drop_index("ix_core_event_failure_event_type", table_name="core_event_failure")
    op.drop_index("ix_core_event_failure_created", table_name="core_event_failure")
    op.drop_table("core_event_failure")
