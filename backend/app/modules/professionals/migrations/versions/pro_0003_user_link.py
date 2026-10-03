"""A directory professional can name the account they sign in with.

The missing half of clinical attribution. ADR 0032 asks every clinical entry
to name the licensed professional responsible for it, separately from the
account that typed it — and there was no way to get from one to the other.
`professionals` is deliberately independent of `users` (a collaborator can be
in the directory with no account at all), and the only bridge was a lowercased
email comparison used to display "has system access here".

`user_id` is that link, stated rather than inferred. **No backfill**: matching
on email would write a coincidence into the column that clinical authorship is
then derived from, and a shared family address or a reused clinic mailbox would
attribute someone's notes to another person. The existing email hint keeps
doing what it did — suggesting to an admin that a link is probably wanted.

Unique per clinic, partial: the same person can hold a profile in two clinics,
and "no account" is the normal state for many rows.

Revision ID: pro_0003
Revises: pro_0002
Create Date: 2026-09-28

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "pro_0003"
down_revision: str | None = "pro_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("professionals", sa.Column("user_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_professionals_user", "professionals", "users", ["user_id"], ["id"])
    op.create_index("ix_professionals_user_id", "professionals", ["user_id"])
    op.create_index(
        "uq_professionals_clinic_user",
        "professionals",
        ["clinic_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_professionals_clinic_user", table_name="professionals")
    op.drop_index("ix_professionals_user_id", table_name="professionals")
    op.drop_constraint("fk_professionals_user", "professionals", type_="foreignkey")
    op.drop_column("professionals", "user_id")
