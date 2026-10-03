"""The medical history stops being deletable, and starts naming its author.

Step 1 of the clinical-record work (ADR 0032, `docs/features/expediente-clinico.md`
§8 phase 0). Adds to the four history tables — allergies, medications, systemic
diseases and surgical history — the columns that let a correction be an append
rather than a delete:

- ``ended_at``      the fact was true and stopped being true (a medication
                    discontinued). It stays in the record and stays readable.
- ``retracted_at``  the entry should never have existed (wrong patient, a
                    mistaken tap). It stops driving alerts and stops leaving
                    the clinic in a disclosure — and is still not deleted.
- ``retraction_reason``
- ``recorded_by_user_id``  who operated the software.

All four are nullable with no backfill, and that is deliberate on the last:
every existing row predates the rule and its author cannot be invented. NULL
means "recorded before this was required", which is the truth.

**The clinical author is not here.** ADR 0032 also asks each entry to name the
licensed professional responsible, and a first draft of this migration added
``recorded_by_professional_id`` with a foreign key to ``professionals``. It
does not work, and the failure is worth recording: this module is part of the
**core linear chain**, which boot applies first, while ``professionals`` is a
removable module on **its own branch**, applied afterwards by the lifespan
processor for installed modules. On an empty database the constraint therefore
refers to a table that does not exist yet:

    relation "professionals" does not exist
    [SQL: ALTER TABLE patients_clinical_allergy ADD CONSTRAINT ... REFERENCES professionals (id)]

Every fresh install would have failed at boot. The column waits until the
product decides where clinical authorship comes from — see the model docstring
for the second blocker, which is that no link exists from an account to a
directory professional in the first place.

Emergency contacts and legal guardians are left alone here. They are
1:1 rows keyed by ``patient_id``, so making them append-only means re-keying
the tables — a larger change than this one, and not the patient-safety case
that made this urgent.

Revision ID: pc_0002
Revises: pc_0001
Create Date: 2026-09-25

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "pc_0002"
down_revision: str | None = "pc_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: The history entries. Emergency contacts and legal guardians are 1:1 and
#: excluded on purpose — see the module docstring.
_TABLES: tuple[str, ...] = (
    "patients_clinical_allergy",
    "patients_clinical_medication",
    "patients_clinical_systemic_disease",
    "patients_clinical_surgical_history",
)


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("retracted_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("retraction_reason", sa.Text(), nullable=True))
        op.add_column(table, sa.Column("recorded_by_user_id", sa.UUID(), nullable=True))

        # Every read of a live history filters on both, so they are indexed
        # rather than left to a sequential scan per patient panel.
        op.create_index(f"ix_{table}_ended_at", table, ["ended_at"])
        op.create_index(f"ix_{table}_retracted_at", table, ["retracted_at"])

        # `users` is core, created by the same chain this migration is on, so
        # the constraint is safe here in a way the professional one was not.
        op.create_foreign_key(
            f"fk_{table}_recorded_by_user",
            table,
            "users",
            ["recorded_by_user_id"],
            ["id"],
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_constraint(f"fk_{table}_recorded_by_user", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_retracted_at", table_name=table)
        op.drop_index(f"ix_{table}_ended_at", table_name=table)
        op.drop_column(table, "recorded_by_user_id")
        op.drop_column(table, "retraction_reason")
        op.drop_column(table, "retracted_at")
        op.drop_column(table, "ended_at")
