"""A history entry names the professional responsible for it.

The half of ADR 0032's attribution that `pc_0002` could not carry. Two things
blocked it then, and both are gone:

1. *Nothing linked an account to a directory professional.* `professionals`
   now has `user_id` (`pro_0003`), stated by an admin rather than inferred
   from a matching email.
2. *A foreign key from this chain to the `professionals` branch failed on a
   fresh install*, because `patients_clinical` rides the core linear chain
   that boot applies first while `professionals` is a removable module on its
   own branch, applied afterwards. `depends_on` is the answer the project
   already uses for this — see `liq_0001`, which FKs into the same table from
   another branch. It orders the two revisions without threading one module's
   chain through another's, which is what issue #56 and ADR 0002 forbid.

Nullable, no backfill. Every existing row predates the rule; NULL reads as
"recorded before this was required", and assigning a professional who never
signed the entry would be a fabrication in a document meant to be evidence.

Revision ID: pc_0003
Revises: pc_0002
Create Date: 2026-09-28

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "pc_0003"
down_revision: str | None = "pc_0002"
branch_labels: str | Sequence[str] | None = None
#: Orders this revision after `pro_0001` — the revision that carries the
#: `professionals` branch label and creates the table — without merging the two
#: chains. Note that the label names *that* revision, not the branch head: an
#: upgrade to here pulls in pro_0001 and nothing later on that branch, which is
#: all this needs. Without the declaration the FK below refers to a table that
#: does not exist yet on an empty database, and boot fails. Verified both ways.
depends_on: str | Sequence[str] | None = ("professionals",)


_TABLES: tuple[str, ...] = (
    "patients_clinical_allergy",
    "patients_clinical_medication",
    "patients_clinical_systemic_disease",
    "patients_clinical_surgical_history",
)


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("recorded_by_professional_id", sa.UUID(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_recorded_by_professional",
            table,
            "professionals",
            ["recorded_by_professional_id"],
            ["id"],
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_constraint(f"fk_{table}_recorded_by_professional", table, type_="foreignkey")
        op.drop_column(table, "recorded_by_professional_id")
