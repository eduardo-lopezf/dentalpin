"""Reusable plan templates.

A practice runs a handful of recurring plan shapes and rebuilds them by hand
on every patient. These two tables store the shape — an ordered list of
catalog items with their stage of care — and nothing patient-specific: the
teeth are supplied when the template is applied.

``depends_on`` pins cat_0001, which creates ``treatment_catalog_items``; the
FK on ``plan_template_items`` is a cross-module reference and ``catalog`` is
in this module's ``manifest.depends``.

Revision ID: tp_0009
Revises: tp_0008
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "tp_0009"
down_revision: str | None = "tp_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = "cat_0001"


def upgrade() -> None:
    op.create_table(
        "plan_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=50), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "key", name="uq_plan_template_clinic_key"),
    )
    op.create_index("ix_plan_templates_clinic_id", "plan_templates", ["clinic_id"])
    op.create_index(
        "idx_plan_templates_clinic_active", "plan_templates", ["clinic_id", "is_active"]
    )

    op.create_table(
        "plan_template_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("catalog_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phase", sa.String(length=20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["plan_templates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["catalog_item_id"], ["treatment_catalog_items.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_id", "sequence", name="uq_plan_template_item_sequence"),
    )
    op.create_index("ix_plan_template_items_clinic_id", "plan_template_items", ["clinic_id"])
    op.create_index("ix_plan_template_items_template_id", "plan_template_items", ["template_id"])
    op.create_index(
        "ix_plan_template_items_catalog_item_id", "plan_template_items", ["catalog_item_id"]
    )
    op.create_index("idx_plan_template_items_template", "plan_template_items", ["template_id"])


def downgrade() -> None:
    op.drop_table("plan_template_items")
    op.drop_table("plan_templates")
