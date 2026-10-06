"""migration_import — rename the brand-named columns after DentalPin → Diente Azul.

``migration_import_entity_mappings`` carried the product name in two
column names: ``dentalpin_table`` and ``dentalpin_id``, the local side of
the source→local identity map. The product is now Diente Azul, so the
columns are ``dienteazul_table`` and ``dienteazul_id``.

``mig_0001`` deliberately still creates the old names. A migration is a
record of what happened, not a description of the current schema: if it
created the new names, this rename would find nothing on a fresh database
and the two paths would diverge. Creating the old name and renaming it
here is the only shape where a fresh install and an existing one end up
identical.

Neither column participates in an index or a unique constraint
(``uq_migration_entity_mapping_lookup`` is keyed on the *source* side), so
this is a plain rename with no constraint to drop and recreate first.

Revision ID: mig_0005
Revises: mig_0004
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "mig_0005"
down_revision: str | None = "mig_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "migration_import_entity_mappings"


def upgrade() -> None:
    op.alter_column(_TABLE, "dentalpin_table", new_column_name="dienteazul_table")
    op.alter_column(_TABLE, "dentalpin_id", new_column_name="dienteazul_id")


def downgrade() -> None:
    op.alter_column(_TABLE, "dienteazul_table", new_column_name="dentalpin_table")
    op.alter_column(_TABLE, "dienteazul_id", new_column_name="dentalpin_id")
