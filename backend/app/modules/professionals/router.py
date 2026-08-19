"""HTTP endpoints for the clinic professional directory."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

# Declared dependency (see manifest: depends=["media"]) — reuses the
# storage abstraction and validation helpers, not the patient-scoped
# Document model. No Document row is created for professional photos.
from app.modules.media.storage import get_storage_backend
from app.modules.media.validation import validate_file_size, validate_mime_type

from .schemas import ProfessionalCreate, ProfessionalResponse, ProfessionalUpdate
from .service import ProfessionalService

router = APIRouter()


@router.get("", response_model=PaginatedApiResponse[ProfessionalResponse])
async def list_professionals(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("professionals.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = None,
    professional_type: str | None = Query(
        default=None, pattern="^(dentist|hygienist|collaborator)$"
    ),
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


@router.post(
    "", response_model=ApiResponse[ProfessionalResponse], status_code=status.HTTP_201_CREATED
)
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
    updated = await ProfessionalService.update(
        db, professional, data.model_dump(exclude_unset=True)
    )
    return ApiResponse(data=ProfessionalResponse.model_validate(updated))


_PHOTO_EXTENSION_BY_MIME = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
    "image/heif": "heif",
    "image/gif": "gif",
}
_PHOTO_MIME_BY_EXTENSION = {ext: mime for mime, ext in _PHOTO_EXTENSION_BY_MIME.items()}


def _photo_storage_path(clinic_id: UUID, professional_id: UUID, extension: str) -> str:
    return f"professionals/{clinic_id}/{professional_id}/photo.{extension}"


@router.post("/{professional_id}/photo", response_model=ApiResponse[ProfessionalResponse])
async def upload_professional_photo(
    professional_id: UUID,
    file: Annotated[UploadFile, File()],
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("professionals.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ProfessionalResponse]:
    professional = await ProfessionalService.get(db, ctx.clinic_id, professional_id)
    if professional is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Professional not found")

    validate_file_size(file)
    mime_type = validate_mime_type(file)
    extension = _PHOTO_EXTENSION_BY_MIME.get(mime_type)
    if extension is None:
        raise HTTPException(status_code=400, detail=f"Unsupported photo type '{mime_type}'")

    data = await file.read()
    storage = get_storage_backend()
    await storage.store(data, _photo_storage_path(ctx.clinic_id, professional_id, extension))

    photo_url = f"/api/v1/professionals/{professional_id}/photo"
    updated = await ProfessionalService.update(db, professional, {"photo_url": photo_url})
    return ApiResponse(data=ProfessionalResponse.model_validate(updated))


@router.get("/{professional_id}/photo")
async def get_professional_photo(
    professional_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("professionals.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    professional = await ProfessionalService.get(db, ctx.clinic_id, professional_id)
    if professional is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Professional not found")

    storage = get_storage_backend()
    for extension, mime_type in _PHOTO_MIME_BY_EXTENSION.items():
        path = _photo_storage_path(ctx.clinic_id, professional_id, extension)
        if await storage.exists(path):
            return Response(content=await storage.retrieve(path), media_type=mime_type)

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
