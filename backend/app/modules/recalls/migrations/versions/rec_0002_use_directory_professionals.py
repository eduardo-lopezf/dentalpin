"""Use directory professionals for recall assignments.

Mirrors the agenda (``ag_0006``), schedules (``sch_0002``),
treatment_plan (``tp_0007``) and budget (``bud_0004``) rewire:
``recalls.assigned_professional_id`` used to point at a product account
(``users.id``); it now points at an independent directory profile
(``professionals.id``). ``recommended_by`` is left untouched — it
records who suggested the recall (a staff account), not who the
follow-up is clinically attributed to. Reuses the same deterministic
conversion so an account that already got a directory profile via one
of those migrations is not duplicated.

Revision ID: rec_0002
Revises: rec_0001
Create Date: 2026-08-19
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa

from alembic import op

revision: str = "rec_0002"
down_revision: str | None = "rec_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = "pro_0001"


def _directory_id(clinic_id, user_id):
    return uuid5(NAMESPACE_URL, f"dentalpin:legacy-professional:{clinic_id}:{user_id}")


def upgrade() -> None:
    bind = op.get_bind()

    op.drop_constraint(
        "recalls_assigned_professional_id_fkey",
        "recalls",
        type_="foreignkey",
    )

    rows = bind.execute(
        sa.text(
            """
            SELECT DISTINCT r.clinic_id, r.assigned_professional_id AS user_id,
                   u.first_name, u.last_name, u.email, u.is_active, cm.role
            FROM recalls AS r
            JOIN users AS u ON u.id = r.assigned_professional_id
            LEFT JOIN clinic_memberships AS cm
              ON cm.clinic_id = r.clinic_id AND cm.user_id = r.assigned_professional_id
            WHERE r.assigned_professional_id IS NOT NULL
            """
        )
    ).mappings()
    for row in rows:
        professional_id = _directory_id(row["clinic_id"], row["user_id"])
        profile_type = "hygienist" if row["role"] == "hygienist" else "dentist"
        bind.execute(
            sa.text(
                """
                INSERT INTO professionals
                    (id, clinic_id, first_name, last_name, professional_type,
                     email, is_active, created_at, updated_at)
                VALUES
                    (:id, :clinic_id, :first_name, :last_name, :professional_type,
                     :email, :is_active, now(), now())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": professional_id,
                "clinic_id": row["clinic_id"],
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "professional_type": profile_type,
                "email": row["email"],
                "is_active": row["is_active"],
            },
        )
        bind.execute(
            sa.text(
                """
                UPDATE recalls
                SET assigned_professional_id = :professional_id
                WHERE clinic_id = :clinic_id AND assigned_professional_id = :user_id
                """
            ),
            {
                "professional_id": professional_id,
                "clinic_id": row["clinic_id"],
                "user_id": row["user_id"],
            },
        )

    op.create_foreign_key(
        "recalls_assigned_professional_id_fkey",
        "recalls",
        "professionals",
        ["assigned_professional_id"],
        ["id"],
    )


def downgrade() -> None:
    raise NotImplementedError(
        "rec_0002 is irreversible: account IDs are intentionally replaced by independent profiles"
    )
