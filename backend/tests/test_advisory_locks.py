"""Startup work is serialised across replicas by ``advisory_lock``.

What is pinned here is the lock itself: one holder at a time, released
however the block ends, and the two names that nest at boot not standing
in each other's way. That two real Alembic runs survive each other is in
``test_alembic_roundtrip.py``, which is where a database gets migrated.
"""

import asyncio

import pytest

from app.core.advisory_locks import BOOT_LOCK, MIGRATION_LOCK, advisory_lock

NAME = "test:advisory-lock"


async def test_a_second_holder_waits_for_the_first() -> None:
    order: list[str] = []
    first_is_in = asyncio.Event()
    let_first_out = asyncio.Event()

    async def first() -> None:
        async with advisory_lock(NAME):
            order.append("first in")
            first_is_in.set()
            await let_first_out.wait()
            order.append("first out")

    async def second() -> None:
        await first_is_in.wait()
        async with advisory_lock(NAME):
            order.append("second in")

    tasks = [asyncio.create_task(first()), asyncio.create_task(second())]
    await first_is_in.wait()
    # Long enough for the second to have got in, were nothing stopping it.
    await asyncio.sleep(0.5)
    assert order == ["first in"]

    let_first_out.set()
    async with asyncio.timeout(10):
        await asyncio.gather(*tasks)
    assert order == ["first in", "first out", "second in"]


async def test_the_lock_is_released_when_the_block_raises() -> None:
    with pytest.raises(RuntimeError, match="boom"):
        async with advisory_lock(NAME):
            raise RuntimeError("boom")

    # A lock that outlived the failure would leave every later boot waiting.
    async with asyncio.timeout(10):
        async with advisory_lock(NAME):
            pass


async def test_boot_and_migration_locks_nest() -> None:
    """The lifespan holds the boot lock while the processor runs Alembic,
    which takes the migration lock on a connection of its own. Were they
    one lock, a single backend would wait on itself at every start."""
    async with asyncio.timeout(10):
        async with advisory_lock(BOOT_LOCK), advisory_lock(MIGRATION_LOCK):
            pass
