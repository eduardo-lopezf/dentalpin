"""record: the module's Alembic branch, which creates nothing yet.

The record is a **composition**, not a table: it reads what the modules that
own the clinical data already hold, and copying any of it here is the failure
`docs/features/expediente-clinico.md` exists to prevent
([ADR 0034](../../../../../../docs/adr/0034-the-record-is-composed-not-stored.md)).
So this revision has no schema in it.

It exists because `removable=True` requires a self-contained branch —
`REMOVABLE_BRANCH_NOT_ISOLATED` in the manifest validator — and that
requirement is right: uninstalling a module has to be able to downgrade
something of its own, and a module whose revisions hang off another's chain
drags that one down with it (issue #56, ADR 0002).

It is also where the tables of phase 2 land. What the record will genuinely
own is what is genuinely new: the authorisations that permit a disclosure and
the artifacts one produces. Those are not other modules' data, so they belong
here — unlike everything the composition reads.

Revision ID: exp_0001
Revises: (branch root)

The ``exp_`` prefix, not ``rec_``: ``recalls`` got there first, and an id
collision does not fail loudly — ``alembic heads`` quietly reported *its*
second revision as belonging to this branch, because its ``down_revision =
"rec_0001"`` resolved to the new file. The two modules' graphs would have been
merged by a name.
Create Date: 2026-10-01

"""

from collections.abc import Sequence

revision: str = "exp_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("record",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Nothing. The branch is the point; see the module docstring."""


def downgrade() -> None:
    """Nothing to undo."""
