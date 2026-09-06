"""Agreed payment schedules: create, read with settlement, cancel.

Two views over the same money, and they must never be added together:

- **Devengado** — what the patient owes for work already done
  (``LedgerService.compute_pending_charges``).
- **Calendario** — what was agreed to be paid, and when (here).

A 19.020 MXN orthognathic case collects most of its money before most of its
work exists, so the first view reads zero while the clinic is perfectly on
track. The second is what reception acts on. Both settle against the same
payments; summing them would double the patient's bill.

Settlement is derived, never stored: instalments are covered in order by net
payments, the same walk the earned ledger uses. There is no ``paid`` column to
fall out of sync with the ledger, and recording a payment updates both views
at once without touching either.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import (
    Payment,
    PaymentAllocation,
    PaymentSchedule,
    PaymentScheduleInstalment,
    Refund,
)

logger = logging.getLogger(__name__)


class ScheduleService:
    """Agreed payment schedules for a patient."""

    @staticmethod
    async def _settling_money(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID, budget_id: UUID | None
    ) -> Decimal:
        """What this schedule may count as paid.

        **Attached to a budget → only money allocated to that budget.** The
        patient may have paid other budgets long ago; crediting an
        orthognathic agreement with the 75 MXN of a first visit that was
        collected and closed months earlier reads as a discount nobody gave.
        The "Cobrar" button on the plan allocates to this budget precisely so
        the schedule sees it.

        **No budget → every net payment the patient has made.** There is
        nothing narrower to go on, and a schedule with no document behind it
        is the patient's whole account by definition.
        """
        if budget_id is not None:
            allocated = await db.execute(
                select(func.coalesce(func.sum(PaymentAllocation.amount), Decimal("0"))).where(
                    PaymentAllocation.clinic_id == clinic_id,
                    PaymentAllocation.target_type == "budget",
                    PaymentAllocation.budget_id == budget_id,
                )
            )
            # Refunds sit on the payment, not the allocation, so a payment
            # split across budgets cannot have its refund attributed exactly.
            # Subtracting the refunds of payments that touched this budget is
            # the conservative reading: it never reports more collected than
            # the clinic actually kept.
            refunded = await db.execute(
                select(func.coalesce(func.sum(Refund.amount), Decimal("0")))
                .join(Payment, Payment.id == Refund.payment_id)
                .join(PaymentAllocation, PaymentAllocation.payment_id == Payment.id)
                .where(
                    Payment.clinic_id == clinic_id,
                    Payment.patient_id == patient_id,
                    PaymentAllocation.target_type == "budget",
                    PaymentAllocation.budget_id == budget_id,
                )
            )
            return max(Decimal("0"), allocated.scalar_one() - refunded.scalar_one())

        paid = await db.execute(
            select(func.coalesce(func.sum(Payment.amount), Decimal("0"))).where(
                Payment.clinic_id == clinic_id, Payment.patient_id == patient_id
            )
        )
        refunded = await db.execute(
            select(func.coalesce(func.sum(Refund.amount), Decimal("0")))
            .join(Payment, Payment.id == Refund.payment_id)
            .where(Payment.clinic_id == clinic_id, Payment.patient_id == patient_id)
        )
        return paid.scalar_one() - refunded.scalar_one()

    @staticmethod
    async def list_schedules(
        db: AsyncSession,
        clinic_id: UUID,
        *,
        patient_id: UUID | None = None,
        budget_id: UUID | None = None,
        include_cancelled: bool = False,
    ) -> list[PaymentSchedule]:
        stmt = (
            select(PaymentSchedule)
            .options(selectinload(PaymentSchedule.instalments))
            .where(PaymentSchedule.clinic_id == clinic_id)
            .order_by(PaymentSchedule.created_at.desc())
        )
        if patient_id is not None:
            stmt = stmt.where(PaymentSchedule.patient_id == patient_id)
        if budget_id is not None:
            stmt = stmt.where(PaymentSchedule.budget_id == budget_id)
        if not include_cancelled:
            stmt = stmt.where(PaymentSchedule.status == "active")
        result = await db.execute(stmt)
        return list(result.scalars().unique().all())

    @staticmethod
    async def get(db: AsyncSession, clinic_id: UUID, schedule_id: UUID) -> PaymentSchedule | None:
        result = await db.execute(
            select(PaymentSchedule)
            .options(selectinload(PaymentSchedule.instalments))
            .where(
                PaymentSchedule.id == schedule_id,
                PaymentSchedule.clinic_id == clinic_id,
            )
            .execution_options(populate_existing=True)
        )
        return result.scalars().unique().one_or_none()

    @staticmethod
    async def create(
        db: AsyncSession,
        clinic_id: UUID,
        user_id: UUID | None,
        data: dict,
    ) -> PaymentSchedule:
        """Record what was agreed.

        Amounts are taken as given. The caller decides how to split the total
        — by phase, by percentage, monthly — because only it knows what the
        total is *for*; a plan knows its phases, payments does not.
        """
        instalments = data.get("instalments") or []
        if not instalments:
            raise ValueError("A schedule needs at least one instalment")

        # Every clinic that has ever agreed a schedule has been asked "and how
        # much is left?" — a negative or zero line makes that answer nonsense.
        for raw in instalments:
            if Decimal(str(raw["amount"])) <= 0:
                raise ValueError("Instalment amounts must be greater than zero")

        schedule = PaymentSchedule(
            clinic_id=clinic_id,
            patient_id=UUID(str(data["patient_id"])),
            budget_id=UUID(str(data["budget_id"])) if data.get("budget_id") else None,
            notes=data.get("notes"),
            created_by=user_id,
        )
        db.add(schedule)
        await db.flush()

        for index, raw in enumerate(instalments, start=1):
            db.add(
                PaymentScheduleInstalment(
                    clinic_id=clinic_id,
                    schedule_id=schedule.id,
                    sequence=index,
                    label=raw.get("label"),
                    due_date=raw.get("due_date"),
                    amount=Decimal(str(raw["amount"])),
                )
            )
        await db.flush()
        return schedule

    @staticmethod
    async def update(
        db: AsyncSession, clinic_id: UUID, schedule_id: UUID, data: dict
    ) -> PaymentSchedule | None:
        """Renegotiate an agreement in place.

        Deliberately allowed after money has been collected — "the patient
        cannot manage March, spread it over the rest" is the normal reason to
        touch a schedule at all. Nothing is corrupted by it: settlement is
        derived from the payments, never stored, so the new instalments are
        simply re-covered in order. If the new total ends up below what has
        already been paid, the surplus shows as ``unapplied`` rather than
        disappearing.

        ``instalments`` is a full replace when present, left alone when the
        key is absent — the same contract the catalog session template and
        plan templates use.
        """
        schedule = await ScheduleService.get(db, clinic_id, schedule_id)
        if schedule is None:
            return None

        if "notes" in data:
            schedule.notes = data["notes"]

        instalments = data.get("instalments")
        if instalments is not None:
            if not instalments:
                raise ValueError("A schedule needs at least one instalment")
            for raw in instalments:
                if Decimal(str(raw["amount"])) <= 0:
                    raise ValueError("Instalment amounts must be greater than zero")

            # Replace by statement rather than through the relationship: the
            # collection was just eagerly loaded, and mutating it while the
            # rows are being deleted is how you get a stale line-up back.
            await db.execute(
                delete(PaymentScheduleInstalment).where(
                    PaymentScheduleInstalment.schedule_id == schedule.id
                )
            )
            await db.flush()
            for index, raw in enumerate(instalments, start=1):
                db.add(
                    PaymentScheduleInstalment(
                        clinic_id=clinic_id,
                        schedule_id=schedule.id,
                        sequence=index,
                        label=raw.get("label"),
                        due_date=raw.get("due_date"),
                        amount=Decimal(str(raw["amount"])),
                    )
                )

        await db.flush()
        return schedule

    @staticmethod
    async def cancel(db: AsyncSession, clinic_id: UUID, schedule_id: UUID) -> bool:
        """Supersede an agreement without erasing it.

        A schedule that was renegotiated is part of what happened, and
        reception is asked about it later.
        """
        schedule = await ScheduleService.get(db, clinic_id, schedule_id)
        if schedule is None:
            return False
        schedule.status = "cancelled"
        await db.flush()
        return True

    @staticmethod
    async def settlement(
        db: AsyncSession, clinic_id: UUID, schedule: PaymentSchedule, today: date | None = None
    ) -> dict:
        """Cover the instalments in order with what the patient has paid.

        Instalments are covered in order — a patient hands over money, not
        money-for-instalment-3. What counts as paid depends on whether the
        schedule has a budget behind it; see ``_settling_money``. Anything
        left over after the last instalment is money paid ahead of the
        agreement, which is a fact reception wants to see rather than an
        error.
        """
        reference = today or date.today()
        remaining = await ScheduleService._settling_money(
            db, clinic_id, schedule.patient_id, schedule.budget_id
        )

        lines: list[dict] = []
        for instalment in sorted(schedule.instalments, key=lambda i: i.sequence):
            covered = min(remaining, instalment.amount) if remaining > 0 else Decimal("0")
            remaining -= covered
            pending = instalment.amount - covered

            if pending <= 0:
                status = "paid"
            elif instalment.due_date is not None and instalment.due_date < reference:
                # Overdue is about the date, not the amount: a partially paid
                # instalment whose date has passed is still late.
                status = "overdue"
            elif covered > 0:
                status = "partial"
            else:
                status = "pending"

            lines.append(
                {
                    "instalment_id": instalment.id,
                    "sequence": instalment.sequence,
                    "label": instalment.label,
                    "due_date": instalment.due_date,
                    "amount": instalment.amount,
                    "collected": covered,
                    "pending": pending,
                    "status": status,
                }
            )

        total = sum((line["amount"] for line in lines), Decimal("0"))
        collected = sum((line["collected"] for line in lines), Decimal("0"))
        overdue = sum(
            (line["pending"] for line in lines if line["status"] == "overdue"), Decimal("0")
        )
        return {
            "total": total,
            "collected": collected,
            "pending": total - collected,
            "overdue": overdue,
            # Paid beyond the whole agreement — an advance, not an error.
            "unapplied": max(Decimal("0"), remaining),
            "instalments": lines,
        }
