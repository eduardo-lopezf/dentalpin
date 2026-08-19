"""Request and response schemas for the professionals directory."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Only dentists and hygienists can receive appointments. Collaborators
# remain useful in the directory (labs, suppliers, assistants) but are not
# schedulable resources.
ProfessionalType = Literal["dentist", "hygienist", "collaborator"]


class ProfessionalCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    professional_type: ProfessionalType = "dentist"
    specialty: str | None = Field(default=None, max_length=150)
    license_number: str | None = Field(default=None, max_length=80)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    photo_url: str | None = Field(default=None, max_length=500)
    notes: str | None = None
    is_active: bool = True


class ProfessionalUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    professional_type: ProfessionalType | None = None
    specialty: str | None = Field(default=None, max_length=150)
    license_number: str | None = Field(default=None, max_length=80)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    photo_url: str | None = Field(default=None, max_length=500)
    notes: str | None = None
    is_active: bool | None = None


class ProfessionalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    first_name: str
    last_name: str
    full_name: str
    professional_type: ProfessionalType
    specialty: str | None
    license_number: str | None
    email: EmailStr | None
    phone: str | None
    photo_url: str | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
