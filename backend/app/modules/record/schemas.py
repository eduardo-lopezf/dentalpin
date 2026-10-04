"""Wire shapes for the composition."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RecordEntryResponse(BaseModel):
    """One dated, attributed clinical fact."""

    model_config = ConfigDict(from_attributes=True)

    occurred_at: datetime
    summary: str
    detail: dict[str, Any] = {}
    status: str
    authored_by_professional_id: UUID | None = None
    recorded_by_user_id: UUID | None = None
    source_table: str | None = None
    source_id: UUID | None = None
    codes: list[dict[str, str]] = []


class RecordSectionResponse(BaseModel):
    """One module's part of the record."""

    model_config = ConfigDict(from_attributes=True)

    module: str
    name: str
    #: An i18n key. The record is read in the clinic's language and exported in
    #: the patient's, so the server never decides the wording.
    title_key: str
    category: str
    entries: list[RecordEntryResponse] = []


class RecordProfessionalResponse(BaseModel):
    """A professional an entry names as clinically responsible."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    license_number: str | None = None


class RecordRequirementResponse(BaseModel):
    """One thing a dental record is expected to hold, and whether it does."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    met: bool
    missing: list[str] = []


class RecordResponse(BaseModel):
    """A patient's clinical record at the instant it was composed."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: UUID
    clinic_id: UUID
    composed_at: datetime
    sections: list[RecordSectionResponse] = []
    professionals: list[RecordProfessionalResponse] = []
    coverage: list[RecordRequirementResponse] = []


Purpose = Literal[
    "continuity_of_care", "patient_copy", "authorised_third_party", "legal_requirement"
]


class DisclosureCreate(BaseModel):
    """Hand the record over: to whom, why, on what evidence, which sections."""

    purpose: Purpose
    recipient_name: str = Field(min_length=1, max_length=200)
    #: The clinical justification, the authorisation signed, or the order.
    evidence: str | None = Field(default=None, max_length=4000)
    identity_verified: bool = False
    #: Sections to include, by qualified name (``module.section``).
    scope: list[str] = Field(min_length=1)
    locale: Literal["es", "en"] = "es"


class DisclosureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    purpose: str
    recipient_name: str
    evidence: str | None
    identity_verified: bool
    scope: list[str]
    document_sha256: str
    disclosed_by_user_id: UUID
    disclosed_by_professional_id: UUID | None
    created_at: datetime


class RecordSectionOption(BaseModel):
    """A section a clinic can show, hide or move."""

    qualified_name: str
    title_key: str
    category: str


class RecordFormatResponse(BaseModel):
    """The clinic's layout, and what there is to lay out."""

    hidden_sections: list[str] = []
    section_order: list[str] = []
    disabled_requirements: list[str] = []
    #: Every section the installed modules offer, in default order.
    available_sections: list[RecordSectionOption] = []
    #: Every point the coverage check can review.
    requirements: list[str] = []
