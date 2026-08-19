"""Use directory professionals for appointments.

Existing appointment IDs referred to product accounts.  Each historical
account is converted to a deterministic directory profile, so the schedules
migration can reuse the exact same profile without name/email matching.

Revision ID: ag_0006
Revises: ag_0005
Create Date: 2026-08-17
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa

from alembic import op

revision: str = "ag_0006"
down_revision: str | None = "ag_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = "pro_0001"


def _directory_id(clinic_id, user_id):
    return uuid5(NAMESPACE_URL, f"dentalpin:legacy-professional:{clinic_id}:{user_id}")


def upgrade() -> None:
    bind = op.get_bind()
    op.drop_constraint("appointments_professional_id_fkey", "appointments", type_="foreignkey")
    rows = bind.execute(
        sa.text(
            """
            SELECT DISTINCT a.clinic_id, a.professional_id AS user_id,
                   u.first_name, u.last_name, u.email, u.is_active,
                   cm.role
            FROM appointments AS a
            JOIN users AS u ON u.id = a.professional_id
            LEFT JOIN clinic_memberships AS cm
              ON cm.clinic_id = a.clinic_id AND cm.user_id = a.professional_id
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
                UPDATE appointments
                SET professional_id = :professional_id
                WHERE clinic_id = :clinic_id AND professional_id = :user_id
                """
            ),
            {
                "professional_id": professional_id,
                "clinic_id": row["clinic_id"],
                "user_id": row["user_id"],
            },
        )

    op.create_foreign_key(
        "appointments_professional_id_fkey",
        "appointments",
        "professionals",
        ["professional_id"],
        ["id"],
    )


def downgrade() -> None:
    raise NotImplementedError(
        "ag_0006 is irreversible: account IDs are intentionally replaced by independent profiles"
    )
