"""Exercising a patient's rights over HTTP.

Mounted at ``/api/v1/privacy``. Until this existed, answering a subject
request meant a developer with a database shell — which is not a
procedure a clinic can follow, and leaves no record that it happened.

Two things shape the endpoints. **The export returns personal data in
cleartext**, because that is what portability means, so it is gated on
its own permission rather than riding on `patients.read`. And **the
erasure is irreversible**, so it demands a stated reason and writes a
:class:`SubjectRequest` row before it is allowed to succeed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import (
    ClinicContext,
    get_clinic_context,
    require_permission,
)
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .models import SubjectRequest
from .subject import SubjectDataService

router = APIRouter(prefix="/privacy", tags=["privacy"])


class SubjectSectionResponse(BaseModel):
    module: str
    section: str
    erasable: bool
    retention_reason: str | None = None
    rows: list[dict[str, Any]]


class SubjectExportResponse(BaseModel):
    patient_id: UUID
    generated_at: datetime
    sections: list[SubjectSectionResponse]


class RetainedSectionResponse(BaseModel):
    module: str
    section: str
    reason: str


class ErasureRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)
    """Why the erasure is being performed. Short enough to be a sentence,
    long enough that it cannot be a keystroke — this is the only record
    of the request that survives it."""


class ErasureResponse(BaseModel):
    patient_id: UUID
    request_id: UUID
    scrubbed: dict[str, int]
    retained: list[RetainedSectionResponse]


class SubjectRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    action: str
    requested_by: UUID
    reason: str
    outcome: dict
    created_at: datetime


def _erasability() -> dict[str, tuple[bool, str | None]]:
    """``module.section`` -> (erasable, retention_reason).

    Read from the contributors themselves so the export document says,
    per section, whether an erasure would reach it — a patient reading
    their data should be able to see which parts they cannot have
    removed, and why, without asking twice.
    """
    from app.core.plugins.registry import module_registry

    return {
        f"{module.name}.{contributor.name}": (
            contributor.erasable,
            contributor.retention_reason,
        )
        for module in module_registry.list_modules()
        for contributor in module.get_subject_contributors()
    }


@router.get("/subjects/{patient_id}/export", response_model=ApiResponse[SubjectExportResponse])
async def export_subject_data(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("privacy.subject.export"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    reason: Annotated[str, Query(min_length=10, max_length=2000)],
) -> ApiResponse[SubjectExportResponse]:
    """Everything the installed modules hold on one patient.

    The reason is required and recorded: this endpoint hands out a
    clinic's most sensitive data in one response, so who pulled it and
    why is part of the operation, not an optional extra.
    """
    sections = await SubjectDataService.export(db, ctx.clinic_id, patient_id)
    erasability = _erasability()

    payload = [
        SubjectSectionResponse(
            module=section.module,
            section=section.section,
            erasable=erasability.get(section.qualified_name, (True, None))[0],
            retention_reason=erasability.get(section.qualified_name, (True, None))[1],
            rows=jsonable_encoder(section.rows),
        )
        for section in sections
    ]

    db.add(
        SubjectRequest(
            clinic_id=ctx.clinic_id,
            patient_id=patient_id,
            action="export",
            requested_by=ctx.user_id,
            reason=reason,
            outcome={s.qualified_name: len(s.rows) for s in sections},
        )
    )
    await db.commit()

    return ApiResponse(
        data=SubjectExportResponse(
            patient_id=patient_id,
            generated_at=datetime.now(),
            sections=payload,
        )
    )


@router.post(
    "/subjects/{patient_id}/erasure",
    response_model=ApiResponse[ErasureResponse],
    status_code=201,
)
async def erase_subject_data(
    patient_id: UUID,
    body: ErasureRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("privacy.subject.erase"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ErasureResponse]:
    """Anonymize what can be anonymized; report what legally cannot.

    Irreversible. The retained sections are not an error — they are the
    part of the answer the clinic owes the patient, so they come back in
    the response with the reason each one gave.

    The whole thing is one transaction: a partial erasure that committed
    half the modules would leave a record nobody could describe.
    """
    scrubbed, retained = await SubjectDataService.anonymize(db, ctx.clinic_id, patient_id)

    request = SubjectRequest(
        clinic_id=ctx.clinic_id,
        patient_id=patient_id,
        action="erasure",
        requested_by=ctx.user_id,
        reason=body.reason,
        outcome={
            "scrubbed": scrubbed,
            "retained": [{"section": r.qualified_name, "reason": r.reason} for r in retained],
        },
    )
    db.add(request)
    await db.commit()

    return ApiResponse(
        data=ErasureResponse(
            patient_id=patient_id,
            request_id=request.id,
            scrubbed=scrubbed,
            retained=[
                RetainedSectionResponse(module=r.module, section=r.section, reason=r.reason)
                for r in retained
            ],
        )
    )


@router.get("/subjects/requests", response_model=PaginatedApiResponse[SubjectRequestResponse])
async def list_subject_requests(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("privacy.subject.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    patient_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[SubjectRequestResponse]:
    """The log of exercised rights, newest first."""
    conditions = [SubjectRequest.clinic_id == ctx.clinic_id]
    if patient_id is not None:
        conditions.append(SubjectRequest.patient_id == patient_id)

    total = await db.scalar(select(func.count()).select_from(SubjectRequest).where(*conditions))
    result = await db.execute(
        select(SubjectRequest)
        .where(*conditions)
        .order_by(SubjectRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = result.scalars().all()

    return PaginatedApiResponse(
        data=[SubjectRequestResponse.model_validate(row) for row in rows],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/subjects/requests/{request_id}", response_model=ApiResponse[SubjectRequestResponse])
async def get_subject_request(
    request_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("privacy.subject.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SubjectRequestResponse]:
    row = (
        await db.execute(
            select(SubjectRequest).where(
                SubjectRequest.clinic_id == ctx.clinic_id, SubjectRequest.id == request_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Subject request not found")
    return ApiResponse(data=SubjectRequestResponse.model_validate(row))
