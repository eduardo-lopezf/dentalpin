"""core — letterheads for what a clinic prints.

One for the clinic and one for each professional who wants their own.
Every printed clinical document — the record, the consent letters, the
blank health questionnaire — takes the letterhead of the professional it
answers to, or the clinic's when they have none (ADR 0046).

``owner_key`` is ``"clinic"`` or a professional's id, as text: the
directory is a module, and the core chain cannot hold a foreign key into
a module's branch.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clinic_letterheads",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("owner_key", sa.String(36), nullable=False),
        sa.Column("heading", sa.String(120), nullable=True),
        sa.Column("subheading", sa.String(200), nullable=True),
        sa.Column("show_address", sa.Boolean(), nullable=False),
        sa.Column("show_contact", sa.Boolean(), nullable=False),
        sa.Column("logo", sa.LargeBinary(), nullable=True),
        sa.Column("logo_mime_type", sa.String(40), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "owner_key", name="uq_clinic_letterhead_owner"),
    )
    op.create_index("ix_clinic_letterheads_clinic_id", "clinic_letterheads", ["clinic_id"])


def downgrade() -> None:
    op.drop_table("clinic_letterheads")
