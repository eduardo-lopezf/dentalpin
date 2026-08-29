"""Core authentication and authorization models."""

from typing import TYPE_CHECKING, Final
from uuid import uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.privacy import DataClass, PiiKind, pii
from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.agenda.models import Appointment, Cabinet
    from app.modules.patients.models import Patient


# Reserved account/business tiers a Clinic row can operate under. Only
# "clinic" has real functionality today (the current staffed-clinic
# product); the others are reserved names for tiers agreed on but not
# yet built (see docs/adr for the tenant-tier roadmap). Root is
# deliberately not a value here — it is a platform-level actor, not a
# kind of clinic, and does not belong to this taxonomy.
ACCOUNT_TIERS: Final[list[str]] = [
    "basic",
    "medium",
    "advanced",
    "clinic",
    "clinic_pro",
    "hospital",
]


class Clinic(Base, TimestampMixin):
    """Clinic entity - the main organizational unit."""

    __tablename__ = "clinics"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), info=pii(PiiKind.NAME))
    # RFC in Mexico, CIF/NIF in Spain — the column is the tax identifier
    # of the clinic whatever the jurisdiction calls it.
    tax_id: Mapped[str] = mapped_column(
        String(20), info=pii(PiiKind.NATIONAL_ID, data_class=DataClass.FINANCIAL)
    )
    legal_name: Mapped[str | None] = mapped_column(
        String(200), default=None, info=pii(PiiKind.NAME, data_class=DataClass.FINANCIAL)
    )
    address: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    phone: Mapped[str | None] = mapped_column(String(20), info=pii(PiiKind.PHONE))
    email: Mapped[str | None] = mapped_column(String(255), info=pii(PiiKind.EMAIL))
    # IANA timezone id (e.g. "Europe/Madrid"). Single source of truth
    # for any module that needs local-time semantics — schedules,
    # reports, future billing date-windows, etc.
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="America/Mexico_City"
    )
    # ISO 4217 currency code. Single source of truth for any module
    # that renders money — budgets, invoices, catalog, reports.
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="MXN")
    # Account/business tier — see ACCOUNT_TIERS. No behavior is gated on
    # this yet; it only reserves the taxonomy ahead of building the
    # tiers beyond the current "clinic" product. Named ``account_tier``
    # and not ``tenant_type`` because a tenant is the DB-isolation unit
    # (ADR 0012) and a clinic lives *inside* one — the old name put two
    # unrelated concepts under the same word (ADR 0023).
    account_tier: Mapped[str] = mapped_column(String(20), nullable=False, server_default="clinic")
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    memberships: Mapped[list["ClinicMembership"]] = relationship(
        back_populates="clinic", cascade="all, delete-orphan"
    )
    patients: Mapped[list["Patient"]] = relationship(back_populates="clinic")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="clinic")
    cabinets: Mapped[list["Cabinet"]] = relationship(
        back_populates="clinic",
        cascade="all, delete-orphan",
        order_by="Cabinet.display_order",
    )


class User(Base, TimestampMixin):
    """User account for authentication."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, info=pii(PiiKind.EMAIL)
    )
    password_hash: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(100), info=pii(PiiKind.NAME))
    last_name: Mapped[str] = mapped_column(String(100), info=pii(PiiKind.NAME))
    professional_id: Mapped[str | None] = mapped_column(String(50))  # Colegiado number
    is_active: Mapped[bool] = mapped_column(default=True)
    token_version: Mapped[int] = mapped_column(default=0)  # For token revocation

    # Relationships
    memberships: Mapped[list["ClinicMembership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class ClinicMembership(Base, TimestampMixin):
    """Association between users and clinics with role."""

    __tablename__ = "clinic_memberships"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    role: Mapped[str] = mapped_column(
        String(20)
    )  # admin, dentist, hygienist, assistant, receptionist

    # Relationships
    user: Mapped["User"] = relationship(back_populates="memberships")
    clinic: Mapped["Clinic"] = relationship(back_populates="memberships")
