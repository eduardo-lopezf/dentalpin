"""liquidations module — initial schema.

Both tables carry a foreign key to `professionals.id`, so that module's
tables have to exist first — but the dependency is declared with
`depends_on` rather than by hanging `down_revision` off the professionals
head. Threading one module's revisions through another's chain is what
`alembic downgrade professionals@base` then drags this module into, and the
project forbids it for exactly that reason (issue #56, ADR 0002).
`depends_on` orders the two without merging their branches.

Revision ID: liq_0001
Revises: 0001
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "liq_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("liquidations",)
depends_on: str | Sequence[str] | None = ("professionals",)


def upgrade() -> None:
    op.create_table(
        "professional_commissions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("professional_id", sa.UUID(), nullable=False),
        sa.Column("basis", sa.String(length=10), nullable=False),
        sa.Column("percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("percent >= 0 AND percent <= 100", name="ck_commission_percent_range"),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["professional_id"], ["professionals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "professional_id", name="uq_professional_commission"),
    )
    op.create_index(
        op.f("ix_professional_commissions_clinic_id"),
        "professional_commissions",
        ["clinic_id"],
    )
    op.create_index(
        op.f("ix_professional_commissions_professional_id"),
        "professional_commissions",
        ["professional_id"],
    )

    op.create_table(
        "liquidations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("professional_id", sa.UUID(), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("basis", sa.String(length=10), nullable=False),
        sa.Column("percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("earned_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("collected_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("base_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("amount_due", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "lines",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("issued_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("percent >= 0 AND percent <= 100", name="ck_liquidation_percent_range"),
        sa.CheckConstraint("date_to >= date_from", name="ck_liquidation_period"),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        # RESTRICT: a settlement is what somebody was paid on, so a
        # professional who has ever been settled with cannot be deleted out
        # from under the record.
        sa.ForeignKeyConstraint(["professional_id"], ["professionals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["issued_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_liquidations_clinic_id"), "liquidations", ["clinic_id"])
    op.create_index(op.f("ix_liquidations_professional_id"), "liquidations", ["professional_id"])
    op.create_index(
        "idx_liquidation_clinic_period", "liquidations", ["clinic_id", "date_from", "date_to"]
    )
    op.create_index(
        "idx_liquidation_professional", "liquidations", ["clinic_id", "professional_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_liquidation_professional", table_name="liquidations")
    op.drop_index("idx_liquidation_clinic_period", table_name="liquidations")
    op.drop_index(op.f("ix_liquidations_professional_id"), table_name="liquidations")
    op.drop_index(op.f("ix_liquidations_clinic_id"), table_name="liquidations")
    op.drop_table("liquidations")
    op.drop_index(
        op.f("ix_professional_commissions_professional_id"),
        table_name="professional_commissions",
    )
    op.drop_index(
        op.f("ix_professional_commissions_clinic_id"),
        table_name="professional_commissions",
    )
    op.drop_table("professional_commissions")
