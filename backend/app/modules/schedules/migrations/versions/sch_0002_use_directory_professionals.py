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


def _reverse_migrate_profiles(bind) -> None:
    """Best-effort reverse of ``_migrate_profiles``.

    For every directory profile a schedule/override row now points at,
    find the clinic member whose ``(clinic_id, user_id)`` hashes to that
    id and point the row back at the account. A profile with no matching
    member (created directly in the directory, never derived from a
    user) can't be reversed — those rows are left pointing at the
    profile id, which violates the FK the caller recreates next; that's
    the expected, documented data loss for a downgrade of this migration.
    """
    for table in ("professional_weekly_schedules", "professional_overrides"):
        rows = bind.execute(
            sa.text(
                f"""
                SELECT DISTINCT clinic_id, professional_id
                FROM {table}
                WHERE professional_id IS NOT NULL
                """
            )
        ).mappings()
        for row in rows:
            candidates = bind.execute(
                sa.text(
                    """
                    SELECT user_id FROM clinic_memberships
                    WHERE clinic_id = :clinic_id AND role IN ('dentist', 'hygienist')
                    """
                ),
                {"clinic_id": row["clinic_id"]},
            ).scalars()
            for user_id in candidates:
                if _directory_id(row["clinic_id"], user_id) == row["professional_id"]:
                    bind.execute(
                        sa.text(
                            f"""
                            UPDATE {table}
                            SET professional_id = :user_id
                            WHERE clinic_id = :clinic_id AND professional_id = :professional_id
                            """
                        ),
                        {
                            "user_id": user_id,
                            "clinic_id": row["clinic_id"],
                            "professional_id": row["professional_id"],
                        },
                    )
                    break


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
    # Both FKs to `users` must go before the data migration, not just this
    # table's: `_migrate_profiles` repoints `user_id` on *both* tables to a
    # synthetic professional id that by definition has no row in `users`.
    # Dropping `professional_overrides`' FK later (with the rest of its
    # index churn) let the UPDATE below run against a live constraint and
    # fail with ForeignKeyViolationError — invisible on a fresh database,
    # where the table is empty and the UPDATE touches no rows, and fatal on
    # any deployment that already had overrides.
    op.drop_constraint(
        "professional_overrides_user_id_fkey", "professional_overrides", type_="foreignkey"
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
    bind = op.get_bind()

    op.drop_index(
        "ix_professional_overrides_clinic_professional_range",
        table_name="professional_overrides",
    )
    op.drop_index(
        "ix_professional_overrides_professional_id",
        table_name="professional_overrides",
    )
    op.drop_constraint(
        "professional_overrides_professional_id_fkey",
        "professional_overrides",
        type_="foreignkey",
    )

    op.drop_constraint(
        "uq_professional_weekly_schedule_professional",
        "professional_weekly_schedules",
        type_="unique",
    )
    op.drop_index(
        "ix_professional_weekly_schedules_professional_id",
        table_name="professional_weekly_schedules",
    )
    op.drop_constraint(
        "professional_weekly_schedules_professional_id_fkey",
        "professional_weekly_schedules",
        type_="foreignkey",
    )

    # Reverse the data before renaming the columns back — same reason
    # the forward migration migrates before renaming: the helper reads
    # `professional_id`, which only exists under that name until now.
    _reverse_migrate_profiles(bind)

    op.alter_column("professional_overrides", "professional_id", new_column_name="user_id")
    op.create_foreign_key(
        "professional_overrides_user_id_fkey",
        "professional_overrides",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_professional_overrides_user_id",
        "professional_overrides",
        ["user_id"],
    )
    op.create_index(
        "ix_professional_overrides_clinic_user_range",
        "professional_overrides",
        ["clinic_id", "user_id", "start_date", "end_date"],
    )

    op.alter_column("professional_weekly_schedules", "professional_id", new_column_name="user_id")
    op.create_foreign_key(
        "professional_weekly_schedules_user_id_fkey",
        "professional_weekly_schedules",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_professional_weekly_schedules_user_id",
        "professional_weekly_schedules",
        ["user_id"],
    )
    op.create_unique_constraint(
        "uq_professional_weekly_schedule_user",
        "professional_weekly_schedules",
        ["clinic_id", "user_id"],
    )
