"""Treatment plan module database models.

Note: clinical-notes models live in the ``clinical_notes`` module since
issue #60. The ``clinical_notes`` and ``clinical_note_attachments`` tables
remain in the database, but ownership of the schema/migrations moved.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.core.auth.models import Clinic, User
    from app.modules.budget.models import Budget
    from app.modules.catalog.models import TreatmentCatalogItem
    from app.modules.odontogram.models import Treatment
    from app.modules.patients.models import Patient
    from app.modules.professionals.models import Professional


class TreatmentPlan(Base, TimestampMixin):
    """Treatment plan that groups treatments for a patient.

    Orchestrates the patient workflow by linking treatments from the odontogram
    with budgets and appointments. Communicates with other modules via event bus.
    """

    __tablename__ = "treatment_plans"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)

    # Identification
    plan_number: Mapped[str] = mapped_column(String(50))  # PLAN-2024-0001
    title: Mapped[str | None] = mapped_column(String(200))

    # Status workflow: draft → pending → active → completed → archived
    # Terminal non-completed state: closed (with closure_reason). Reactivable
    # back to draft. See ADR 0006 and docs/workflows/plan-budget-flow.md.
    status: Mapped[str] = mapped_column(String(20), default="draft")

    # Closure metadata (set when status becomes ``closed``).
    # Allowed closure_reason values:
    #   rejected_by_patient | expired | cancelled_by_clinic |
    #   patient_abandoned  | other
    closure_reason: Mapped[str | None] = mapped_column(String(50))
    closure_note: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Confirmation timestamp (set on draft → pending). Used for
    # pipeline analytics and "days waiting" sorting.
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Budget integration (one-to-one)
    budget_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("budgets.id"), unique=True, index=True
    )

    # Assignments
    assigned_professional_id: Mapped[UUID | None] = mapped_column(ForeignKey("professionals.id"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))

    # Clinical notes
    diagnosis_notes: Mapped[str | None] = mapped_column(Text)
    internal_notes: Mapped[str | None] = mapped_column(Text)

    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])
    patient: Mapped["Patient"] = relationship()
    budget: Mapped["Budget | None"] = relationship()
    assigned_professional: Mapped["Professional | None"] = relationship(
        foreign_keys=[assigned_professional_id]
    )
    creator: Mapped["User"] = relationship(foreign_keys=[created_by])
    items: Mapped[list["PlannedTreatmentItem"]] = relationship(
        back_populates="treatment_plan",
        cascade="all, delete-orphan",
        order_by="PlannedTreatmentItem.sequence_order",
    )

    __table_args__ = (
        UniqueConstraint("clinic_id", "plan_number", name="uq_treatment_plan_number"),
        Index("idx_treatment_plans_patient", "patient_id"),
        Index("idx_treatment_plans_status", "clinic_id", "status"),
        Index("idx_treatment_plans_budget", "budget_id"),
        # Tab "Cerrados" of the pipeline filters by closed_at desc.
        Index(
            "idx_treatment_plans_clinic_status_closed",
            "clinic_id",
            "status",
            "closed_at",
        ),
    )


class PlannedTreatmentItem(Base, TimestampMixin):
    """Individual treatment within a plan.

    Always references a single Treatment (from the odontogram module). Globalness,
    per-tooth / multi-tooth, pricing and catalog link all live on the Treatment.
    """

    __tablename__ = "planned_treatment_items"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    treatment_plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("treatment_plans.id", ondelete="CASCADE"), index=True
    )

    # Single link to Treatment. Unique: no two items may reference the same Treatment.
    treatment_id: Mapped[UUID] = mapped_column(
        ForeignKey("treatments.id", ondelete="CASCADE"), index=True
    )

    # Stage of care for this item, seeded from the catalog item's
    # `default_phase` but decided here: the same extraction is an emergency
    # for one patient and a planned rehabilitation step for another.
    # Values: app.modules.catalog.models.TREATMENT_PHASES.
    phase: Mapped[str | None] = mapped_column(String(20), default=None, index=True)

    # Ordering and status
    sequence_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending|completed|cancelled

    # Completion tracking
    completed_without_appointment: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))

    # Doctor responsible for performing this treatment line. Snapshot from the
    # plan's assigned_professional_id at creation time; once set it is
    # independent — changing the plan-level doctor does not cascade here unless
    # the caller passes ``reassign_pending_items=True`` on the plan update.
    assigned_professional_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("professionals.id"), nullable=True, index=True
    )

    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    clinic: Mapped["Clinic"] = relationship()
    treatment_plan: Mapped["TreatmentPlan"] = relationship(back_populates="items")
    treatment: Mapped["Treatment"] = relationship()
    completer: Mapped["User | None"] = relationship(foreign_keys=[completed_by])
    assigned_professional: Mapped["Professional | None"] = relationship(
        foreign_keys=[assigned_professional_id]
    )
    sessions: Mapped[list["PlannedTreatmentItemSession"]] = relationship(
        back_populates="plan_item",
        cascade="all, delete-orphan",
        order_by="PlannedTreatmentItemSession.sequence",
    )

    __table_args__ = (
        UniqueConstraint("treatment_id", name="uq_planned_item_treatment"),
        Index("idx_planned_items_plan", "treatment_plan_id"),
        Index("idx_planned_items_treatment", "treatment_id"),
        Index("idx_planned_items_status", "treatment_plan_id", "status"),
        Index(
            "idx_planned_items_plan_professional",
            "treatment_plan_id",
            "assigned_professional_id",
        ),
    )


class PlannedTreatmentItemSession(Base, TimestampMixin):
    """One billable / executable step of a ``PlannedTreatmentItem``.

    Snapshotted from ``CatalogItemSession`` at plan-add time. After
    creation the session is independent — editing the catalog template
    does not retro-affect existing plan instances. Once a session is
    marked ``completed`` its label and amount are immutable.
    """

    __tablename__ = "planned_treatment_item_sessions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    plan_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("planned_treatment_items.id", ondelete="CASCADE"), index=True
    )

    sequence: Mapped[int] = mapped_column(Integer)
    label: Mapped[str | None] = mapped_column(String(120))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending|completed|cancelled

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    plan_item: Mapped["PlannedTreatmentItem"] = relationship(back_populates="sessions")
    completer: Mapped["User | None"] = relationship(foreign_keys=[completed_by])

    __table_args__ = (
        UniqueConstraint("plan_item_id", "sequence", name="uq_plan_item_session_sequence"),
        Index("idx_pti_session_plan_item", "plan_item_id"),
        Index("ix_pti_session_plan_item_status", "plan_item_id", "status"),
    )


class PlanTemplate(Base, TimestampMixin):
    """A reusable shape of a treatment plan.

    Clinical plans are not invented one by one — a practice runs a handful of
    recurring shapes (primera visita, fase higiénica, endo + reconstrucción +
    corona, implante unitario) and rebuilds them by hand every time. A template
    is that shape: an ordered list of catalog items with their stage of care.

    What a template deliberately does **not** carry is teeth. A template that
    fixed tooth 16 would be useless on the next patient; the teeth are supplied
    when the template is applied (see ``PlanTemplateService.apply``).

    Templates are per-clinic. ``key`` is set only on the starter set shipped
    with the module, so re-seeding can match an existing row instead of
    duplicating it; templates a clinic creates itself leave it NULL.
    """

    __tablename__ = "plan_templates"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    # Stable identifier for the shipped starter set; NULL for clinic-authored
    # templates. Re-seeding matches on it, so it must never be reused.
    key: Mapped[str | None] = mapped_column(String(50), default=None)

    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)

    # Soft delete: a template that built existing plans stays referenced in
    # nothing, but hiding beats deleting for something a clinic curates.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))

    clinic: Mapped["Clinic"] = relationship()
    items: Mapped[list["PlanTemplateItem"]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="PlanTemplateItem.sequence",
    )

    __table_args__ = (
        UniqueConstraint("clinic_id", "key", name="uq_plan_template_clinic_key"),
        Index("idx_plan_templates_clinic_active", "clinic_id", "is_active"),
    )


class PlanTemplateItem(Base, TimestampMixin):
    """One line of a ``PlanTemplate``: a catalog item and where it sits.

    ``phase`` overrides the catalog item's ``default_phase`` for this template
    only — the same crown is rehabilitation in one shape and an emergency
    provisional in another. NULL means "whatever the catalog says".
    """

    __tablename__ = "plan_template_items"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    template_id: Mapped[UUID] = mapped_column(
        ForeignKey("plan_templates.id", ondelete="CASCADE"), index=True
    )

    sequence: Mapped[int] = mapped_column(Integer)
    catalog_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("treatment_catalog_items.id", ondelete="CASCADE"), index=True
    )

    # See app.modules.catalog.models.TREATMENT_PHASES. NULL → catalog default.
    phase: Mapped[str | None] = mapped_column(String(20), default=None)
    notes: Mapped[str | None] = mapped_column(Text)

    template: Mapped["PlanTemplate"] = relationship(back_populates="items")
    catalog_item: Mapped["TreatmentCatalogItem"] = relationship()

    __table_args__ = (
        UniqueConstraint("template_id", "sequence", name="uq_plan_template_item_sequence"),
        Index("idx_plan_template_items_template", "template_id"),
    )
