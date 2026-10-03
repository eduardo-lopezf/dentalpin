"""Wire shapes for the composition."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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


class RecordResponse(BaseModel):
    """A patient's clinical record at the instant it was composed."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: UUID
    clinic_id: UUID
    composed_at: datetime
    sections: list[RecordSectionResponse] = []
