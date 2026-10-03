"""agenda: an appointment needs neither a professional nor a patient.

Patients and Professionals are Apps the agenda links to when they run
and does without when they do not (ADR 0037). ``patient_id`` was already
nullable; ``professional_id`` was not, so no appointment could be booked
in a clinic without the Professionals App.

``title`` is what identifies an appointment that has no patient to name
it by.

Both changes only widen what the table accepts: no existing row is
touched. The slot index needs no change — a NULL professional never
collides with another, which is right, since there is nobody to
double-book.

Revision ID: ag_0007
Revises: ag_0006
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "ag_0007"
down_revision: str | None = "ag_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("appointments", "professional_id", existing_type=sa.UUID(), nullable=True)
    op.add_column("appointments", sa.Column("title", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("appointments", "title")
    # Fails, on purpose, if any appointment was booked without a
    # professional: there is no professional to invent for it.
    op.alter_column("appointments", "professional_id", existing_type=sa.UUID(), nullable=False)
