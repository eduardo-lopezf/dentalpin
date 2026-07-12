"""Database model for clinic dentists and collaborators."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class Professional(Base, TimestampMixin):
    """A person in a clinic's professional directory.

    The directory is deliberately independent of ``users``: a collaborator
    can be recorded before (or without) receiving an application account.
    """

    __tablename__ = "professionals"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    professional_type: Mapped[str] = mapped_column(String(20), nullable=False, default="dentist")
    specialty: Mapped[str | None] = mapped_column(String(150))
    license_number: Mapped[str | None] = mapped_column(String(80))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(30))
    photo_url: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("ix_professionals_clinic_name", "clinic_id", "last_name", "first_name"),
        Index("ix_professionals_clinic_type_active", "clinic_id", "professional_type", "is_active"),
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
