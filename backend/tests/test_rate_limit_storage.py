"""Where the rate limiter counts, and how many connections a process holds.

Both are per process by default, which is right for one backend and wrong
for several: each would allow the full limit, and each would open a full
pool. They are settings so that a deployment with several backends can
say otherwise — and these tests pin that a deployment which says nothing
keeps exactly what it had.
"""

from limits.storage import MemoryStorage

from app.config import Settings
from app.core.auth.router import build_limiter


def test_one_backend_keeps_what_it_had() -> None:
    fields = Settings.model_fields

    assert fields["RATE_LIMIT_STORAGE_URI"].default == ""
    assert fields["DB_POOL_SIZE"].default == 10
    assert fields["DB_MAX_OVERFLOW"].default == 20


def test_without_a_store_the_limiter_counts_in_memory() -> None:
    limiter = build_limiter("", enabled=True)

    assert isinstance(limiter._storage, MemoryStorage)
    # Nothing to fall back from.
    assert limiter._in_memory_fallback_enabled is False


def test_with_a_store_the_limiter_survives_losing_it() -> None:
    """A shared store is one more thing that can be down, and the limiter
    sits in front of the login. ``memory://`` stands in for it here: what
    is pinned is that naming a store turns the fallback on."""
    limiter = build_limiter("memory://", enabled=True)

    assert limiter._storage_uri == "memory://"
    assert limiter._in_memory_fallback_enabled is True
