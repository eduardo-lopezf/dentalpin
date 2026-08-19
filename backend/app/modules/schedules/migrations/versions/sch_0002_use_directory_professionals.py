"""Use directory professionals for schedules and overrides.

Revision ID: sch_0002
Revises: sch_0001
Create Date: 2026-08-17
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa

from alembic import op

revision: str = "sch_0002"
down_revision: str | None = "sch_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = ("ag_0006",)


def _directory_id(clinic_id, user_id):
    return uuid5(NAMESPACE_URL, f"dentalpin:legacy-professional:{clinic_id}:{user_id}")


def _migrate_profiles(bind) -> None:
    rows = bind.execute(
        sa.text(
            """
            SELECT DISTINCT legacy.clinic_id, legacy.user_id,
                   u.first_name, u.last_name, u.email, u.is_active, cm.role
            FROM (
                SELECT clinic_id, user_id FROM professional_weekly_schedules
                UNION
                SELECT clinic_id, user_id FROM professional_overrides
            ) AS legacy
            JOIN users AS u ON u.id = legacy.user_id
            LEFT JOIN clinic_memberships AS cm
              ON cm.clinic_id = legacy.clinic_id AND cm.user_id = legacy.user_id
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
                UPDATE professional_weekly_schedules
                SET user_id = :professional_id
                WHERE clinic_id = :clinic_id AND user_id = :user_id
                """
            ),
            {
                "professional_id": professional_id,
                "clinic_id": row["clinic_id"],
                "user_id": row["user_id"],
            },
        )
        bind.execute(
            sa.text(
                """
                UPDATE professional_overrides
                SET user_id = :professional_id
                WHERE clinic_id = :clinic_id AND user_id = :user_id
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
        "professional_weekly_schedules_user_id_fkey",
        "professional_weekly_schedules",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_professional_weekly_schedule_user",
        "professional_weekly_schedules",
        type_="unique",
    )
    op.drop_index(
        "ix_professional_weekly_schedules_user_id",
        table_name="professional_weekly_schedules",
    )
    # Migrate legacy user-based schedules/overrides into directory professionals
    # before renaming the columns. Running the migration step after the
    # rename causes SELECTs against `user_id` to fail because the column
    # no longer exists. Move the migration here so both tables still expose
    # `user_id` for the legacy extraction.
    _migrate_profiles(bind)

    op.alter_column("professional_weekly_schedules", "user_id", new_column_name="professional_id")
    op.create_foreign_key(
        "professional_weekly_schedules_professional_id_fkey",
        "professional_weekly_schedules",
        "professionals",
        ["professional_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_professional_weekly_schedules_professional_id",
        "professional_weekly_schedules",
        ["professional_id"],
    )
    op.create_unique_constraint(
        "uq_professional_weekly_schedule_professional",
        "professional_weekly_schedules",
        ["clinic_id", "professional_id"],
    )

    op.drop_constraint(
        "professional_overrides_user_id_fkey", "professional_overrides", type_="foreignkey"
    )

    op.drop_index("ix_professional_overrides_user_id", table_name="professional_overrides")
    op.drop_index(
        "ix_professional_overrides_clinic_user_range", table_name="professional_overrides"
    )
    op.alter_column("professional_overrides", "user_id", new_column_name="professional_id")
    op.create_foreign_key(
        "professional_overrides_professional_id_fkey",
        "professional_overrides",
        "professionals",
        ["professional_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_professional_overrides_professional_id",
        "professional_overrides",
        ["professional_id"],
    )
    op.create_index(
        "ix_professional_overrides_clinic_professional_range",
        "professional_overrides",
        ["clinic_id", "professional_id", "start_date", "end_date"],
    )


def downgrade() -> None:
    raise NotImplementedError(
        "sch_0002 is irreversible: account IDs are intentionally replaced by independent profiles"
    )
