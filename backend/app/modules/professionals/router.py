"""HTTP endpoints for the clinic professional directory."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import ProfessionalCreate, ProfessionalResponse, ProfessionalUpdate
from .service import ProfessionalService

router = APIRouter()


@router.get("", response_model=PaginatedApiResponse[ProfessionalResponse])
async def list_professionals(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("professionals.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = None,
    professional_type: str | None = Query(default=None, pattern="^(dentist|collaborator)$"),
    include_inactive: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[ProfessionalResponse]:
    professionals, total = await ProfessionalService.list(
        db,
        ctx.clinic_id,
        search=search,
        professional_type=professional_type,
        include_inactive=include_inactive,
        page=page,
        page_size=page_size,
    )
    return PaginatedApiResponse(
        data=[ProfessionalResponse.model_validate(item) for item in professionals],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{professional_id}", response_model=ApiResponse[ProfessionalResponse])
async def get_professional(
    professional_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("professionals.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ProfessionalResponse]:
    professional = await ProfessionalService.get(db, ctx.clinic_id, professional_id)
    if professional is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Professional not found")
    return ApiResponse(data=ProfessionalResponse.model_validate(professional))


@router.post("", response_model=ApiResponse[ProfessionalResponse], status_code=status.HTTP_201_CREATED)
async def create_professional(
    data: ProfessionalCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("professionals.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ProfessionalResponse]:
    professional = await ProfessionalService.create(db, ctx.clinic_id, data.model_dump())
    return ApiResponse(data=ProfessionalResponse.model_validate(professional))


@router.put("/{professional_id}", response_model=ApiResponse[ProfessionalResponse])
async def update_professional(
    professional_id: UUID,
    data: ProfessionalUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("professionals.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ProfessionalResponse]:
    professional = await ProfessionalService.get(db, ctx.clinic_id, professional_id)
    if professional is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Professional not found")
    updated = await ProfessionalService.update(db, professional, data.model_dump(exclude_unset=True))
    return ApiResponse(data=ProfessionalResponse.model_validate(updated))
