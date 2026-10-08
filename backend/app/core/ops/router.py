"""What the control plane reads from a deployment, and the one thing it
writes: a new clinic with its holder (ADR 0049 rules 4 and 6).

Mounted at ``/api/v1/ops``. Not for the clinic's users: no staff token
opens it. The caller is the operator's control plane, which signs a
short-lived token with ``CONTROL_PLANE_SECRET``.

The routes answer ``404`` — they do not exist — while that secret is
unset, and always under ``self`` custody: a self-hosted deployment
answers to nobody (ADR 0028).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.schemas import _validate_iana_timezone
from app.core.auth.service import hash_password, validate_password_strength
from app.core.contracts import ReferenceSpecialties, provider
from app.core.events import event_bus
from app.core.events.types import EventType
from app.core.plugins.apps import load_app_catalog, mandatory_apps, required_apps
from app.core.privacy.policy import CustodyMode
from app.core.privacy.tiers import AccountTier, TierCustodyError, validate_tier_custody
from app.core.schemas import ApiResponse
from app.core.tenancy import TenantContext
from app.core.tenancy.dependencies import get_tenant
from app.database import get_db

from .usage import ClinicState, cached_measure, clinic_log, clinic_states

#: What a control-plane token must name as its audience, so a token
#: signed for anything else — a staff session, a budget link — is refused
#: even if the keys were ever the same.
OPS_AUDIENCE = "dienteazul-ops"

_bearer = HTTPBearer(auto_error=False)


async def require_control_plane(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> None:
    if not settings.CONTROL_PLANE_SECRET or tenant.privacy.custody_mode is CustodyMode.SELF:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    if credentials is None:
        raise unauthorized
    try:
        jwt.decode(
            credentials.credentials,
            settings.CONTROL_PLANE_SECRET,
            algorithms=["HS256"],
            audience=OPS_AUDIENCE,
            options={"require": ["exp"]},
        )
    except PyJWTError:
        raise unauthorized from None


router = APIRouter(prefix="/ops", tags=["ops"], dependencies=[Depends(require_control_plane)])


class ClinicUsageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_at: datetime
    apps: list[str] | None
    users: int
    #: ``deactivated`` | ``active`` | ``offline`` | ``inactive``; read now,
    #: unlike the sizes, with the three dates it is worked out from.
    status: str
    last_access_at: datetime | None
    deactivated_at: datetime | None
    deletable_from: datetime | None
    database_bytes: int
    database_rows: int
    storage_bytes: int
    storage_files: int


class DeploymentUsageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    database_bytes: int
    shared_database_bytes: int
    storage_bytes: int
    storage_files: int
    measured_at: datetime
    clinics: list[ClinicUsageResponse]


class LogEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    at: datetime
    kind: str
    user_id: UUID | None
    role: str | None
    area: str | None


@router.get("/usage", response_model=ApiResponse[DeploymentUsageResponse])
async def get_usage(
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant: Annotated[TenantContext, Depends(get_tenant)],
    refresh: bool = False,
) -> ApiResponse[DeploymentUsageResponse]:
    """Database and file storage of the deployment, and of each clinic.

    Measured at most once every ten minutes; ``refresh=true`` measures
    again now. A clinic's database figure is its share of the tables it
    has rows in — see ``app.core.ops.usage``.
    """
    root = Path(settings.STORAGE_LOCAL_PATH) / tenant.storage_prefix
    usage = await cached_measure(db, root, refresh=refresh)
    states = await clinic_states(db)
    return ApiResponse(
        data=DeploymentUsageResponse(
            database_bytes=usage.database_bytes,
            shared_database_bytes=usage.shared_database_bytes,
            storage_bytes=usage.storage_bytes,
            storage_files=usage.storage_files,
            measured_at=usage.measured_at,
            clinics=[
                ClinicUsageResponse(**asdict(clinic), **asdict(states[clinic.id]))
                # One deleted since the sizes were measured has no state.
                for clinic in usage.clinics
                if clinic.id in states
            ],
        )
    )


@router.get("/clinics/{clinic_id}/log", response_model=ApiResponse[list[LogEntryResponse]])
async def get_clinic_log(
    clinic_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=100, ge=1, le=500),
) -> ApiResponse[list[LogEntryResponse]]:
    """Sign-ins, sign-outs and newly created records of one clinic,
    newest first. Identifiers and table names only."""
    if await db.get(Clinic, clinic_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clinic not found")
    entries = await clinic_log(db, clinic_id, limit)
    return ApiResponse(data=[LogEntryResponse.model_validate(e) for e in entries])


#: Tiers sold to one professional rather than to a clinic: the clinic
#: record carries the holder's own name and tax id.
_INDIVIDUAL_TIERS = frozenset({AccountTier.BASIC, AccountTier.MEDIUM, AccountTier.ADVANCED})


class ClinicCreate(BaseModel):
    """A new clinic and the professional who holds it."""

    account_tier: AccountTier
    timezone: str = Field(max_length=64)
    #: RFC — the holder's under an individual tier, the clinic's otherwise.
    tax_id: str = Field(min_length=1, max_length=20)

    holder_first_name: str = Field(min_length=1, max_length=100)
    holder_last_name: str = Field(min_length=1, max_length=100)
    holder_email: EmailStr
    #: Cédula profesional.
    holder_professional_id: str = Field(min_length=1, max_length=50)
    #: The holder's first password, given by the control plane. Only its
    #: hash is kept, and the holder has to replace it at the first sign-in
    #: (``users.must_change_password``).
    holder_password: str = Field(min_length=8)

    # The clinic's own details. Required by every tier that is not an
    # individual one, ignored by those that are.
    #: Apps the clinic is set up with, by name. Must hold every App that
    #: is mandatory for the tier, and whatever the chosen ones require.
    apps: list[str]
    #: Disciplines the clinic's treatment catalogue starts with, by key.
    #: Left out, it gets the baseline ones, as after ``/auth/setup``.
    specialties: list[str] | None = None

    clinic_name: str | None = Field(default=None, min_length=1, max_length=200)
    clinic_legal_name: str | None = Field(default=None, max_length=200)
    clinic_phone: str | None = Field(default=None, max_length=20)
    clinic_email: EmailStr | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        return _validate_iana_timezone(value)

    @model_validator(mode="after")
    def clinic_tiers_name_the_clinic(self) -> ClinicCreate:
        if self.account_tier not in _INDIVIDUAL_TIERS and not self.clinic_name:
            raise ValueError(f"clinic_name is required for the '{self.account_tier}' tier")
        return self


class AppResponse(BaseModel):
    name: str
    tier: str
    #: Whether the deployment runs it at all (``apps.json``).
    enabled: bool
    #: Other Apps it cannot run without.
    requires: list[str]
    #: Account tiers whose clinics always have it.
    mandatory_for: list[str]


@router.get("/apps", response_model=ApiResponse[list[AppResponse]])
async def list_apps() -> ApiResponse[list[AppResponse]]:
    """The deployment's Apps, and for which account tiers each is
    mandatory — what there is to choose from when creating a clinic."""
    mandatory = {tier.value: mandatory_apps(tier.value) for tier in AccountTier}
    return ApiResponse(
        data=[
            AppResponse(
                name=app.name,
                tier=app.tier.value,
                enabled=app.enabled,
                requires=required_apps(app),
                mandatory_for=[tier for tier, names in mandatory.items() if app.name in names],
            )
            for app in load_app_catalog()
        ]
    )


class SpecialtyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    names: dict[str, str]
    #: Every clinic has it.
    required: bool


@router.get("/specialties", response_model=ApiResponse[list[SpecialtyResponse]])
async def list_specialties() -> ApiResponse[list[SpecialtyResponse]]:
    """The disciplines a clinic's treatment catalogue can start with.
    None when the deployment does not run the Treatments App."""
    reference = provider(ReferenceSpecialties)
    return ApiResponse(
        data=[
            SpecialtyResponse.model_validate(s)
            for s in (reference.available() if reference else [])
        ]
    )


def _chosen_specialties(chosen: list[str] | None) -> list[str] | None:
    """``chosen``, once it is a set of disciplines a clinic can start with."""
    if chosen is None:
        return None
    reference = provider(ReferenceSpecialties)
    known = {s.key: s for s in (reference.available() if reference else [])}
    if unknown := [key for key in chosen if key not in known]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"not a specialty: {', '.join(unknown)}"
        )
    if missing := [key for key, s in known.items() if s.required and key not in chosen]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"every clinic has the specialty: {', '.join(missing)}",
        )
    return [key for key in known if key in chosen]


def _chosen_apps(chosen: list[str], tier: AccountTier) -> list[str]:
    """``chosen`` in catalog order, once it is a set a clinic can have."""
    catalog = {app.name: app for app in load_app_catalog()}
    refusal: str | None = None
    if unavailable := [name for name in chosen if name not in catalog or not catalog[name].enabled]:
        refusal = f"not an App of this deployment: {', '.join(unavailable)}"
    elif missing := [name for name in mandatory_apps(tier.value) if name not in chosen]:
        refusal = f"mandatory for the '{tier.value}' tier: {', '.join(missing)}"
    else:
        for name in chosen:
            if needs := [other for other in required_apps(catalog[name]) if other not in chosen]:
                refusal = f"'{name}' cannot run without: {', '.join(needs)}"
                break
    if refusal:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, refusal)
    return [name for name in catalog if name in chosen]


class ClinicCreatedResponse(BaseModel):
    clinic_id: UUID
    name: str
    holder_user_id: UUID


@router.post(
    "/clinics",
    response_model=ApiResponse[ClinicCreatedResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_clinic(
    data: ClinicCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> ApiResponse[ClinicCreatedResponse]:
    """Create a clinic and its holder, who becomes its administrator.

    What ``/auth/setup`` does for the first clinic of a deployment, for
    every one after it. Under an individual tier the clinic record is the
    holder's practice: it takes the holder's name.
    """
    try:
        validate_tier_custody(data.account_tier, tenant.privacy.custody_mode)
    except TierCustodyError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    is_valid, error = validate_password_strength(data.holder_password)
    if not is_valid:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, error)
    apps = _chosen_apps(data.apps, data.account_tier)
    specialties = _chosen_specialties(data.specialties)
    if await db.scalar(select(User.id).where(User.email == data.holder_email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this e-mail already exists")

    individual = data.account_tier in _INDIVIDUAL_TIERS
    clinic = Clinic(
        name=(
            f"{data.holder_first_name} {data.holder_last_name}" if individual else data.clinic_name
        ),
        tax_id=data.tax_id,
        legal_name=None if individual else data.clinic_legal_name,
        phone=None if individual else data.clinic_phone,
        email=None if individual else data.clinic_email,
        account_tier=data.account_tier.value,
        apps=apps,
        timezone=data.timezone,
    )
    holder = User(
        email=data.holder_email,
        password_hash=hash_password(data.holder_password),
        first_name=data.holder_first_name,
        last_name=data.holder_last_name,
        professional_id=data.holder_professional_id,
        must_change_password=True,
    )
    db.add_all([clinic, holder])
    await db.flush()
    db.add(ClinicMembership(user_id=holder.id, clinic_id=clinic.id, role="admin"))

    # Modules install their baseline data on this event — the catalog its
    # VAT types, categories and specialties — exactly as after /auth/setup.
    created = {"clinic_id": str(clinic.id), "created_by": str(holder.id), "name": clinic.name}
    if specialties is not None:
        created["specialties"] = specialties
    event_bus.publish_after_commit(db, EventType.CLINIC_CREATED, created)
    return ApiResponse(
        data=ClinicCreatedResponse(clinic_id=clinic.id, name=clinic.name, holder_user_id=holder.id)
    )


class ClinicStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    last_access_at: datetime | None
    deactivated_at: datetime | None
    deletable_from: datetime | None


async def _set_deactivated(db: AsyncSession, clinic_id: UUID, deactivated: bool) -> ClinicState:
    clinic = await db.get(Clinic, clinic_id)
    if clinic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clinic not found")
    if deactivated and clinic.deactivated_at is None:
        # Kept if already set: the wait before deletion counts from the
        # first time, not from the last click.
        clinic.deactivated_at = datetime.now(UTC)
    elif not deactivated:
        clinic.deactivated_at = None
    await db.flush()
    return (await clinic_states(db))[clinic_id]


@router.post("/clinics/{clinic_id}/deactivate", response_model=ApiResponse[ClinicStateResponse])
async def deactivate_clinic(
    clinic_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> ApiResponse[ClinicStateResponse]:
    """Close a clinic to its members. Nothing of it is deleted, and
    reactivating brings everything back."""
    state = await _set_deactivated(db, clinic_id, True)
    return ApiResponse(data=ClinicStateResponse.model_validate(state))


@router.post("/clinics/{clinic_id}/reactivate", response_model=ApiResponse[ClinicStateResponse])
async def reactivate_clinic(
    clinic_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> ApiResponse[ClinicStateResponse]:
    """Open a deactivated clinic again."""
    state = await _set_deactivated(db, clinic_id, False)
    return ApiResponse(data=ClinicStateResponse.model_validate(state))
