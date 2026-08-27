"""Durable record of event handlers that failed.

The bus catches handler exceptions so one broken subscriber cannot take
down the rest of a dispatch — and, before this table existed, that was
the whole story: a log line and nothing else.

Since [ADR 0019](../../../../docs/adr/0019-events-publish-after-commit.md)
handlers run strictly after the publisher's commit, which makes the
silence expensive: the fact is durable, the reaction is lost, and
nothing queryable says a reaction was ever owed. One row per failed
handler call closes that gap.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

ERROR_MAX = 2000
TRACEBACK_MAX = 8000


class EventHandlerFailure(Base):
    """One handler, one event, one exception."""

    __tablename__ = "core_event_failure"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    handler: Mapped[str] = mapped_column(String(255), nullable=False)
    """Qualified name of the handler, e.g. ``billing.events.on_payment_refunded``."""

    module: Mapped[str | None] = mapped_column(String(100))
    """Module the handler belongs to, when it can be derived from its module path."""

    clinic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    """Taken from the payload — no FK, because the payload is not a contract."""

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error: Mapped[str] = mapped_column(String(ERROR_MAX), nullable=False)
    traceback: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_core_event_failure_created", "created_at"),
        Index("ix_core_event_failure_event_type", "event_type"),
    )
