"""core — account_tier is mandatory and constrained.

``clinics.account_tier`` carried ``server_default='clinic'``, which made
it optional at insert: a clinic could come into existence without anyone
deciding its tier and silently be sold as the current product. The tier
is now half of a commercial pairing — the other half is the deployment's
custody mode, which lives outside this database by design (ADR 0024
rule 2) — so defaulting either half decides an offer by accident.

Two changes: drop the server default, so an INSERT must name the tier,
and add a CHECK restricting it to the known taxonomy. The pairing itself
(``basic``/``medium`` are only sold ``managed``) cannot be a CHECK here,
because the custody half is not a column in this database; it is enforced
in the application, at clinic creation and at boot
(``app.core.privacy.tiers``).

Existing rows already hold 'clinic' via the old default; the backfill is
defensive, for a row that predates the column or arrived through a path
that wrote NULL.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TIERS = ("basic", "medium", "advanced", "clinic", "clinic_pro", "hospital")


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE clinics SET account_tier = 'clinic' "
            "WHERE account_tier IS NULL OR account_tier = ''"
        )
    )
    op.alter_column("clinics", "account_tier", server_default=None)
    op.create_check_constraint(
        "ck_clinics_account_tier",
        "clinics",
        sa.column("account_tier").in_(_TIERS),
    )


def downgrade() -> None:
    op.drop_constraint("ck_clinics_account_tier", "clinics", type_="check")
    op.alter_column("clinics", "account_tier", server_default="clinic")
