"""Database configuration and session management."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import settings

# Create async engine with connection pool settings.
#
# ``pool_pre_ping`` issues a cheap ``SELECT 1`` before checking out a
# connection so stale sockets (DB restart, NAT/firewall idle drop) are
# transparently recycled instead of failing the next request with a
# generic "connection lost". ``pool_recycle=3600`` ages connections out
# proactively so we don't accumulate idle ones a proxy might silently
# close.
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=settings.ENVIRONMENT == "development",
)


class UnitOfWorkSession(AsyncSession):
    """Session that announces its events only once they are true.

    Handlers subscribe to facts, not intentions, and they read them
    through their own sessions. Publishing from inside an open
    transaction therefore announces something no other connection can
    see — audit finding S2. Publishers queue with
    ``event_bus.publish_after_commit(db, ...)``; this session drains the
    queue after the commit lands and drops it on rollback.

    In-process and non-durable: a crash between the commit and the
    dispatch loses the events. A durable outbox is the next step up, and
    it is a separate decision — this closes the correctness hole without
    a new table.
    """

    async def commit(self) -> None:
        await super().commit()

        # Import here: ``app.core.events`` is imported by every module,
        # and half of them import ``app.database``.
        from app.core.events import event_bus

        await event_bus.dispatch_pending(self)

    async def rollback(self) -> None:
        from app.core.events import event_bus

        event_bus.discard_pending(self)
        await super().rollback()


# ``expire_on_commit=False`` keeps ORM objects hydrated after a commit
# so the router can serialise the response without an extra refresh
# round-trip. Anything streaming or kept across awaits (long-lived
# tasks, websockets) must re-fetch explicitly — but the request-scoped
# pattern that dominates the codebase relies on this.
async_session_maker = async_sessionmaker(
    engine,
    class_=UnitOfWorkSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables. For development only."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
