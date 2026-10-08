"""Work that only one process may do at a time, across every replica.

Rule 1 of ADR 0051 (``docs/adr/0051-a-backend-process-is-one-of-several.md``).

Starting a backend is not read-only: it migrates the schema, reconciles
the module registry, carries out pending installs and uninstalls — one of
which drops tables — and, on a demo deployment, seeds. With one container
that is a sequence. With two started together it is a race, and the first
thing it broke was the first statement of the first migration: both
created ``alembic_version`` and one of them died on the duplicate.

A Postgres advisory lock serialises that work without a table of its own.
It belongs to the connection, so a process that dies holding it releases
it by dying — nothing to expire, nothing to clean up. The replica that
gets there second waits, then finds the work done and does none.

The names:

- :data:`MIGRATION_LOCK` — one Alembic run. Taken in ``alembic/env.py``,
  so it covers the entrypoint, the module processor and a person typing
  ``alembic upgrade`` alike.
- :data:`BOOT_LOCK` — registry reconciliation and pending module
  operations, in the lifespan.
- :data:`SEED_LOCK` — ``scripts/seed_demo.py``.

Order matters where they nest: the boot lock is held while the processor
runs Alembic, so it is always boot, then migration. Nothing takes them
the other way round, which is what keeps two replicas from waiting on
each other.

Session-level locks do not survive a pooler in transaction mode
(PgBouncer hands the next statement to another server connection). The
application connects to PostgreSQL directly; putting such a pooler in
between means revisiting this.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

from sqlalchemy import text

from app import database

logger = logging.getLogger(__name__)

MIGRATION_LOCK: Final = "core:migrations"
BOOT_LOCK: Final = "core:boot"
SEED_LOCK: Final = "core:seed"

# The lock functions take a bigint; the name is hashed to one in SQL, as
# the Verifactu submission queue already does for its per-clinic lock.
TRY_LOCK_SQL: Final = "SELECT pg_try_advisory_lock(hashtextextended(:name, 0))"
LOCK_SQL: Final = "SELECT pg_advisory_lock(hashtextextended(:name, 0))"


@asynccontextmanager
async def advisory_lock(name: str) -> AsyncIterator[None]:
    """Hold the lock called ``name`` for the duration of the block.

    Waits for as long as another process holds it; there is no timeout,
    because giving up would mean doing the work unguarded. The wait is
    logged, so a replica that is slow to start says why.

    ``database.engine`` is read on each call, not imported by name: the
    test suite rebinds it to its own database.
    """
    async with database.engine.connect() as conn:
        acquired = (await conn.execute(text(TRY_LOCK_SQL), {"name": name})).scalar()
        if not acquired:
            logger.info("Waiting for %s: another process holds it", name)
            await conn.execute(text(LOCK_SQL), {"name": name})
            logger.info("Acquired %s", name)
        # End the transaction the statements above opened. The lock is the
        # session's and stays; an idle connection is all that is held.
        await conn.commit()
        try:
            yield
        finally:
            # Closing the server connection is what releases the lock.
            # Unlocking with a statement would need the connection to be
            # alive; this works when it is not, and a connection returned
            # to the pool still holding the lock would never let go.
            await conn.invalidate()
