"""A note names the professional responsible for it, not just the account.

ADR 0032's third defect, for this module: `clinical_notes.author_id` is a
foreign key to `users.id`, and the legal author of a clinical entry is a
professional with a credential — *cédula profesional*, número de colegiado —
which lives on `professionals.license_number`.

`author_id` stays exactly as it was: it is the audit trail of who operated the
software, and every existing read keeps working.
`authored_by_professional_id` is the clinical responsibility, resolved from the
acting account's directory profile (`professionals.user_id`, added in
`pro_0003`). The version rows get the same treatment for whoever amended the
text, so a correction is attributable the way the original is.

Both nullable, no backfill: an account with no profile is a real case (an
assistant typing what a dentist dictates), and inventing an author for the
notes that already exist would be a fabrication in a document meant to be
evidence.

`depends_on` orders this after the revision that creates `professionals` —
this module is on its own branch, so without the declaration the foreign key
below refers to a table an empty database has not built yet.

Revision ID: cn_0006
Revises: cn_0005
Create Date: 2026-09-28

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "cn_0006"
down_revision: str | None = "cn_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = ("professionals",)


def upgrade() -> None:
    op.add_column(
        "clinical_notes", sa.Column("authored_by_professional_id", sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        "fk_clinical_notes_authored_by_professional",
        "clinical_notes",
        "professionals",
        ["authored_by_professional_id"],
        ["id"],
    )
    op.create_index(
        "ix_clinical_notes_authored_by_professional",
        "clinical_notes",
        ["authored_by_professional_id"],
    )

    op.add_column(
        "clinical_note_versions",
        sa.Column("superseded_by_professional_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_clinical_note_versions_superseded_by_professional",
        "clinical_note_versions",
        "professionals",
        ["superseded_by_professional_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_clinical_note_versions_superseded_by_professional",
        "clinical_note_versions",
        type_="foreignkey",
    )
    op.drop_column("clinical_note_versions", "superseded_by_professional_id")

    op.drop_index("ix_clinical_notes_authored_by_professional", table_name="clinical_notes")
    op.drop_constraint(
        "fk_clinical_notes_authored_by_professional", "clinical_notes", type_="foreignkey"
    )
    op.drop_column("clinical_notes", "authored_by_professional_id")
