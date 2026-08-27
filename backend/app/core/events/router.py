"""Read access to event-handler failures.

Mounted at ``/api/v1/events``. There is no UI for this yet: it exists so
an admin (or an agent debugging a clinic) can answer "did anything fail
to react?" without shell access to the logs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import (
    ClinicContext,
    get_clinic_context,
    require_permission,
)
from app.core.schemas import PaginatedApiResponse
from app.database import get_db

from .models import EventHandlerFailure

router = APIRouter(prefix="/events", tags=["events"])


class EventFailureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    handler: str
    module: str | None
    payload: dict
    error: str
    created_at: datetime


@router.get("/failures", response_model=PaginatedApiResponse[EventFailureResponse])
async def list_event_failures(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.events.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    event_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[EventFailureResponse]:
    """Handler failures for this clinic, newest first.

    Failures whose payload carried no ``clinic_id`` are not listed: they
    cannot be attributed to a tenant, and guessing would leak one
    clinic's operational detail into another's. They remain in the
    table and in the logs.
    """
    filters = [EventHandlerFailure.clinic_id == ctx.clinic_id]
    if event_type:
        filters.append(EventHandlerFailure.event_type == event_type)

    total = await db.scalar(select(func.count()).select_from(EventHandlerFailure).where(*filters))
    rows = await db.execute(
        select(EventHandlerFailure)
        .where(*filters)
        .order_by(EventHandlerFailure.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    return PaginatedApiResponse(
        data=[EventFailureResponse.model_validate(row) for row in rows.scalars()],
        total=total or 0,
        page=page,
        page_size=page_size,
    )
