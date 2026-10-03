"""An amendment to a note becomes a version instead of overwriting it.

Step 2 of the clinical-record work (ADR 0032, `docs/features/expediente-clinico.md`
§8 phase 0). `NoteService.update` assigned `note.body = body`: the prior text
was destroyed, so a correction and an original were indistinguishable and the
question a complaint turns on — what did the note say on the day of the
procedure — had no answer.

Adds `clinical_note_versions`, holding each superseded body with its number,
the instant it stopped being current, the account that replaced it and an
optional reason. The current text stays on `clinical_notes.body`, because that
is what every consumer reads and reading it must not cost a join.

Two columns on the note itself: `version` (which number `body` currently is,
existing rows being version 1 — they have never been amended, or rather no
amendment of theirs was ever recorded) and `amended_at` (NULL means the note
still says what it said when written, which a reader could not tell before).

`version` gets a server default so the existing rows fill in without a second
pass. `amended_at` deliberately stays NULL: claiming a date for amendments made
before this migration would be inventing one.

Revision ID: cn_0005
Revises: cn_0004
Create Date: 2026-09-26

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "cn_0005"
down_revision: str | None = "cn_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "clinical_notes",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "clinical_notes",
        sa.Column("amended_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "clinical_note_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("note_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_by_user_id", sa.UUID(), nullable=False),
        sa.Column("amendment_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["note_id"], ["clinical_notes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["superseded_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("note_id", "version", name="uq_clinical_note_version"),
    )
    op.create_index("ix_clinical_note_versions_clinic_id", "clinical_note_versions", ["clinic_id"])
    op.create_index("ix_clinical_note_versions_note_id", "clinical_note_versions", ["note_id"])
    op.create_index(
        "idx_clinical_note_versions_note", "clinical_note_versions", ["note_id", "version"]
    )


def downgrade() -> None:
    op.drop_index("idx_clinical_note_versions_note", table_name="clinical_note_versions")
    op.drop_index("ix_clinical_note_versions_note_id", table_name="clinical_note_versions")
    op.drop_index("ix_clinical_note_versions_clinic_id", table_name="clinical_note_versions")
    op.drop_table("clinical_note_versions")
    op.drop_column("clinical_notes", "amended_at")
    op.drop_column("clinical_notes", "version")
