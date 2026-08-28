"""Database model for clinic dentists and collaborators."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, Column, ForeignKey, Index, String, Table, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.privacy import PiiKind, pii
from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.catalog.models import Specialty


# Many-to-many: a dentist who does both endodontics and periodontics is
# ordinary, and it is what makes "which disciplines does my staff cover"
# answerable. `specialties` is owned by the catalog module, which is in
# manifest.depends for exactly this FK.
professional_specialties = Table(
    "professional_specialties",
    Base.metadata,
    Column(
        "professional_id",
        UUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "specialty_id",
        UUID(as_uuid=True),
        ForeignKey("specialties.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Index("idx_professional_specialties_specialty", "specialty_id"),
)


class Professional(Base, TimestampMixin):
    """A person in a clinic's professional directory.

    The directory is deliberately independent of ``users``: a collaborator
    can be recorded before (or without) receiving an application account.
    """

    __tablename__ = "professionals"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False, info=pii(PiiKind.NAME))
    last_name: Mapped[str] = mapped_column(String(100), nullable=False, info=pii(PiiKind.NAME))
    professional_type: Mapped[str] = mapped_column(String(20), nullable=False, default="dentist")
    # Disciplines drawn from the clinic's specialty catalog — see
    # `professional_specialties`. Replaces the former free-text column.
    license_number: Mapped[str | None] = mapped_column(String(80))
    email: Mapped[str | None] = mapped_column(String(255), info=pii(PiiKind.EMAIL))
    phone: Mapped[str | None] = mapped_column(String(30), info=pii(PiiKind.PHONE))
    photo_url: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    specialties: Mapped[list[Specialty]] = relationship(
        secondary=professional_specialties,
        lazy="selectin",
        order_by="Specialty.created_at",
    )

    __table_args__ = (
        Index("ix_professionals_clinic_name", "clinic_id", "last_name", "first_name"),
        Index("ix_professionals_clinic_type_active", "clinic_id", "professional_type", "is_active"),
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
