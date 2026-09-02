"""Core authentication and authorization models."""

from datetime import datetime
from typing import TYPE_CHECKING, Final
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.privacy import AccountTier, DataClass, PiiKind, pii
from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.agenda.models import Appointment, Cabinet
    from app.modules.patients.models import Patient


# Account/business tiers a Clinic row can operate under. The taxonomy and
# the rule pairing it with a custody mode live in
# ``app.core.privacy.tiers``; this is the string view of it, kept because
# the column stores text and the CHECK constraint below is built from it.
# Root is deliberately not a value — it is a platform-level actor, not a
# kind of clinic, and does not belong to this taxonomy.
ACCOUNT_TIERS: Final[list[str]] = [tier.value for tier in AccountTier]


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
    # Account/business tier — see ``AccountTier``. Mandatory at creation
    # and deliberately without a server default: a clinic that came into
    # existence without anyone deciding its tier would get one by
    # accident, and the tier is half of a commercial pairing whose other
    # half (custody) is decided by the deployment. Still gates no
    # behaviour at runtime (ADR 0024 rule 3) — what a tier is *allowed*
    # to be pairs with ``CustodyMode`` in ``app.core.privacy.tiers``, and
    # that check runs at creation, not on every request. Named
    # ``account_tier`` and not ``tenant_type`` because a tenant is the
    # DB-isolation unit (ADR 0012) and a clinic lives *inside* one — the
    # old name put two unrelated concepts under the same word (ADR 0023).
    account_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        CheckConstraint(
            "account_tier IN (" + ", ".join(f"'{tier}'" for tier in ACCOUNT_TIERS) + ")",
            name="ck_clinics_account_tier",
        ),
    )

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


class AuthSession(Base, TimestampMixin):
    """One refresh token's lifetime, so a session can be ended (ADR 0029, invariant 3).

    Before this table the only revocation was ``User.token_version``: a
    global switch that logs a user out of every device at once and is
    incremented in exactly one place, when an account is deactivated. A
    clinic that loses a laptop could not end *that* session without
    ending every other one.

    One row per refresh token. ``id`` is the token's ``jti``, so the
    token itself carries no state — the row is the state. Rotation
    creates a new row and stamps ``rotated_at`` on the old one, and every
    row from one login shares a ``family_id``.

    That pairing is what makes theft detectable. A refresh token is a
    bearer credential: a stolen one is indistinguishable from the real
    one *until somebody uses it twice*. When a token that has already
    been rotated (or revoked) is presented again, one of the two holders
    is an attacker and there is no way to tell which — so the whole
    family dies and both parties have to log in.

    Deliberately holds no IP and no user agent. Both are personal data
    under GDPR and would need classification and a retention policy
    (ADR 0025); neither is needed to *end* a session, only to label one
    in a UI that does not exist yet.
    """

    __tablename__ = "auth_sessions"

    # The refresh token's ``jti``. Not a surrogate key: the token names
    # the row it depends on.
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Constant across every rotation descending from one login, so
    # revoking a compromised chain does not need to walk it.
    family_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Set when this token was exchanged for the next one. A rotated token
    # is spent; presenting it again is the reuse signal.
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # ``logout`` | ``reuse`` | ``superseded`` — why the row stopped being
    # usable. Prose for an operator reading the table after an incident.
    revoked_reason: Mapped[str | None] = mapped_column(String(20), default=None)

    @property
    def is_usable(self) -> bool:
        return self.revoked_at is None and self.rotated_at is None


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
