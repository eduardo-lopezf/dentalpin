"""Pydantic schemas for the patients module.

After Fase B.4 this module only owns patient identity + demographics +
billing. Medical history, emergency contact, legal guardian and alert
shapes live in ``app.modules.patients_clinical.schemas``.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# --- Identity documents --------------------------------------------------

# Accepted values for ``Patient.national_id_type``, grouped by the country
# whose document it is. The set was Mexico-only, which made every patient
# imported from Gesdén (Spanish software, ``migration_import`` labels them
# ``nif``) unsaveable: the value round-trips through the edit form, and the
# validator rejected it on the first save of that patient's demographics.
#
# The deployment serves both markets — ``verifactu`` files with the Spanish
# AEAT while the default currency is MXN — so the accepted set is the union.
# Narrowing it *per tenant* from ``PrivacyPolicy.jurisdictions`` (ADR 0023)
# is the coherent next step, and it needs the check to move out of the
# Pydantic validator, which cannot see the tenant. Grouped here so that
# move is a rewiring rather than a rediscovery.
NATIONAL_ID_TYPES_BY_JURISDICTION: dict[str, tuple[str, ...]] = {
    "MX": ("curp", "ine"),
    "ES": ("dni", "nie", "nif"),
}
UNIVERSAL_NATIONAL_ID_TYPES: tuple[str, ...] = ("passport",)

NATIONAL_ID_TYPES: frozenset[str] = frozenset(UNIVERSAL_NATIONAL_ID_TYPES).union(
    *NATIONAL_ID_TYPES_BY_JURISDICTION.values()
)


# --- Billing -------------------------------------------------------------


class BillingAddress(BaseModel):
    street: str | None = None
    city: str | None = None
    postal_code: str | None = None
    province: str | None = None
    country: str = "ES"


# --- Patient CRUD --------------------------------------------------------


class PatientCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    date_of_birth: date | None = None
    notes: str | None = None
    do_not_contact: bool = False
    billing_name: str | None = Field(default=None, max_length=200)
    billing_tax_id: str | None = Field(default=None, max_length=50)
    billing_address: BillingAddress | None = None
    billing_email: EmailStr | None = None


class PatientUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    date_of_birth: date | None = None
    notes: str | None = None
    status: str | None = None
    do_not_contact: bool | None = None
    billing_name: str | None = Field(default=None, max_length=200)
    billing_tax_id: str | None = Field(default=None, max_length=50)
    billing_address: BillingAddress | None = None
    billing_email: EmailStr | None = None


class PatientResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    first_name: str
    last_name: str
    phone: str | None
    email: str | None
    date_of_birth: date | None
    notes: str | None
    status: str
    do_not_contact: bool
    billing_name: str | None
    billing_tax_id: str | None
    billing_address: dict | None
    billing_email: str | None
    has_complete_billing_info: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PatientBrief(BaseModel):
    """Brief patient info for lists and references across modules."""

    id: UUID
    first_name: str
    last_name: str
    phone: str | None
    email: str | None

    model_config = ConfigDict(from_attributes=True)


# --- Extended demographics ----------------------------------------------


class PatientAddress(BaseModel):
    street: str | None = None
    city: str | None = None
    postal_code: str | None = None
    province: str | None = None
    country: str = "ES"


class PatientExtendedResponse(PatientResponse):
    gender: str | None = None
    national_id: str | None = None
    national_id_type: str | None = None
    profession: str | None = None
    workplace: str | None = None
    preferred_language: str = "es"
    address: PatientAddress | None = None
    photo_url: str | None = None


class PatientExtendedUpdate(PatientUpdate):
    gender: str | None = Field(default=None, max_length=20)
    national_id: str | None = Field(default=None, max_length=50)
    national_id_type: str | None = Field(default=None, max_length=20)
    profession: str | None = Field(default=None, max_length=100)
    workplace: str | None = Field(default=None, max_length=200)
    preferred_language: str | None = Field(default=None, max_length=10)
    address: PatientAddress | None = None
    photo_url: str | None = Field(default=None, max_length=500)

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in {"male", "female"}:
            raise ValueError("gender must be either 'male' or 'female'")
        return value

    @field_validator("national_id_type")
    @classmethod
    def validate_national_id_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in NATIONAL_ID_TYPES:
            accepted = ", ".join(sorted(NATIONAL_ID_TYPES))
            raise ValueError(f"national_id_type must be one of: {accepted}")
        return value
