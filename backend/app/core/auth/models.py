"""Core authentication and authorization models."""

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import event, text, select
from sqlalchemy.orm import Session

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.agenda.models import Appointment, Cabinet
    from app.modules.patients.models import Patient


class Clinic(Base, TimestampMixin):
    """Clinic entity - the main organizational unit."""

    __tablename__ = "clinics"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    tax_id: Mapped[str] = mapped_column(String(20))  # CIF/NIF
    legal_name: Mapped[str | None] = mapped_column(String(200), default=None)
    address: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    # IANA timezone id (e.g. "Europe/Madrid"). Single source of truth
    # for any module that needs local-time semantics — schedules,
    # reports, future billing date-windows, etc.
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="America/Mexico_City"
    )
    # ISO 4217 currency code. Single source of truth for any module
    # that renders money — budgets, invoices, catalog, reports.
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="MXN")
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
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
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


@event.listens_for(Session, "after_flush")
def _ensure_professional_on_membership(session, flush_context) -> None:
    """After flush, create minimal `Professional` ORM rows for new
    `ClinicMembership` instances with clinical roles. This uses the same
    ORM session so pending `Clinic` rows are visible and the FK will not
    fail on subsequent inserts.
    """
    for obj in list(session.new):
        if not isinstance(obj, ClinicMembership):
            continue
        if obj.role not in ("dentist", "hygienist"):
            continue
        # Check if a Professional already exists for this id+clinic.
        # Use the ORM model to build a proper SELECT and avoid SQL string hacks.
        try:
            from app.modules.professionals.models import Professional

            exists = session.execute(
                select(Professional.id).where(
                    Professional.id == obj.user_id, Professional.clinic_id == obj.clinic_id
                )
            ).scalar_one_or_none()
            if exists:
                continue

            # Add minimal Professional via ORM so it's part of this unit-of-work.
            # If there's a corresponding `User`, mirror basic fields so the
            # directory profile contains a usable name and active flag.
            first_name = ""
            last_name = ""
            is_active = True
            try:
                user = session.get(User, obj.user_id)
                if user is not None:
                    first_name = getattr(user, "first_name", "") or ""
                    last_name = getattr(user, "last_name", "") or ""
                    is_active = bool(getattr(user, "is_active", True))
            except Exception:
                # Best-effort: ignore inspection failures and create a
                # minimal professional.
                pass

            prof = Professional(
                id=obj.user_id,
                clinic_id=obj.clinic_id,
                first_name=first_name,
                last_name=last_name,
                professional_type=obj.role,
                is_active=is_active,
            )
            session.add(prof)
        except Exception:
            # Best-effort: do not raise if something goes wrong in mirroring.
            continue
