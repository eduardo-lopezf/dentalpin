"""Record endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse
from app.database import get_db

from .schemas import RecordResponse
from .service import RecordService

router = APIRouter()


@router.get("/patients/{patient_id}", response_model=ApiResponse[RecordResponse])
async def get_patient_record(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("record.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    include_retracted: bool = Query(
        default=False,
        description=(
            "Include entries that were taken back. They are never deleted, so "
            "'what did the chart say that day' stays answerable — but an entry "
            "that should not have existed is not part of what a colleague is "
            "handed, so asking for it is explicit."
        ),
    ),
) -> ApiResponse[RecordResponse]:
    """The patient's clinical record, composed from the installed modules.

    Not a table: every section comes from the module that owns that data, so
    the record cannot drift from the source. A module that holds nothing about
    this patient still returns its section, empty — "nothing here" is an
    answer, a missing section is not.
    """
    record = await RecordService.compose(
        db, ctx.clinic_id, patient_id, include_retracted=include_retracted
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return ApiResponse(data=RecordResponse.model_validate(record))
