"""payments — a record of chasing a patient for money.

The receivables queue works without it, right up to the moment two people
work it on the same morning and the patient is called twice before lunch.
A queue with no memory of being worked gets worked badly.

Keyed on the **patient**, not on a treatment plan: what is owed can span
several plans and can come from work that never belonged to one. The
conversation is with the person.

Revision ID: pay_0005
Revises: pay_0004
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "pay_0005"
down_revision: str | None = "pay_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collection_contacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("contacted_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_collection_contacts_clinic_id", "collection_contacts", ["clinic_id"])
    op.create_index("ix_collection_contacts_patient_id", "collection_contacts", ["patient_id"])
    # The queue's question: when was each of these patients last chased.
    op.create_index(
        "idx_collection_contacts_clinic_patient",
        "collection_contacts",
        ["clinic_id", "patient_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_collection_contacts_clinic_patient", table_name="collection_contacts")
    op.drop_index("ix_collection_contacts_patient_id", table_name="collection_contacts")
    op.drop_index("ix_collection_contacts_clinic_id", table_name="collection_contacts")
    op.drop_table("collection_contacts")
