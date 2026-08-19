"""Use directory professionals for treatment plan assignments.

Mirrors the agenda (``ag_0006``) and schedules (``sch_0002``) rewire: the
assigned doctor on a plan / plan item used to be a product account
(``users.id``); it now points at an independent directory profile
(``professionals.id``). Reuses the same deterministic conversion so an
account that already got a directory profile via ``ag_0006``/``sch_0002``
is not duplicated.

Revision ID: tp_0007
Revises: tp_0006
Create Date: 2026-08-19
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa

from alembic import op

revision: str = "tp_0007"
down_revision: str | None = "tp_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = "pro_0001"


def _directory_id(clinic_id, user_id):
    return uuid5(NAMESPACE_URL, f"dentalpin:legacy-professional:{clinic_id}:{user_id}")


def _migrate_column(bind, table: str) -> None:
    rows = bind.execute(
        sa.text(
            f"""
            SELECT DISTINCT t.clinic_id, t.assigned_professional_id AS user_id,
                   u.first_name, u.last_name, u.email, u.is_active, cm.role
            FROM {table} AS t
            JOIN users AS u ON u.id = t.assigned_professional_id
            LEFT JOIN clinic_memberships AS cm
              ON cm.clinic_id = t.clinic_id AND cm.user_id = t.assigned_professional_id
            WHERE t.assigned_professional_id IS NOT NULL
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
                f"""
                UPDATE {table}
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


def upgrade() -> None:
    bind = op.get_bind()

    op.drop_constraint(
        "treatment_plans_assigned_professional_id_fkey",
        "treatment_plans",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_planned_items_assigned_professional",
        "planned_treatment_items",
        type_="foreignkey",
    )

    _migrate_column(bind, "treatment_plans")
    _migrate_column(bind, "planned_treatment_items")

    op.create_foreign_key(
        "treatment_plans_assigned_professional_id_fkey",
        "treatment_plans",
        "professionals",
        ["assigned_professional_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_planned_items_assigned_professional",
        "planned_treatment_items",
        "professionals",
        ["assigned_professional_id"],
        ["id"],
    )


def downgrade() -> None:
    raise NotImplementedError(
        "tp_0007 is irreversible: account IDs are intentionally replaced by independent profiles"
    )
