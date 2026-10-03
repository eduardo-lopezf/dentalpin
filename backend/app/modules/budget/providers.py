"""What budget offers other modules without being imported (ADR 0039).

Read-only by rule (ADR 0042): budgets are created, cancelled and deleted
by this module's own handlers and endpoints, never through a contract.
"""

from __future__ import annotations

from collections.abc import Collection
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contracts import BudgetBrief

from .models import Budget, BudgetItem


def _brief(budget: Budget) -> BudgetBrief:
    return BudgetBrief(
        id=budget.id,
        budget_number=budget.budget_number,
        status=budget.status,
        total=float(budget.total or 0),
        patient_id=budget.patient_id,
    )


def _of_plan(plan_number: str | None, budget_id: UUID | None) -> list:
    conditions = []
    if plan_number:
        conditions.append(Budget.plan_number_snapshot == plan_number)
    if budget_id is not None:
        conditions.append(Budget.id == budget_id)
    return conditions


class BudgetPlanBudgets:
    async def briefs(
        self, db: AsyncSession, clinic_id: UUID, budget_ids: Collection[UUID]
    ) -> dict[UUID, BudgetBrief]:
        if not budget_ids:
            return {}
        result = await db.execute(
            select(Budget).where(Budget.clinic_id == clinic_id, Budget.id.in_(budget_ids))
        )
        return {budget.id: _brief(budget) for budget in result.scalars()}

    async def ids_for_plan(
        self, db: AsyncSession, clinic_id: UUID, plan_number: str | None, budget_id: UUID | None
    ) -> list[UUID]:
        conditions = _of_plan(plan_number, budget_id)
        if not conditions:
            return []
        result = await db.execute(
            select(Budget.id).where(Budget.clinic_id == clinic_id, or_(*conditions))
        )
        return list(result.scalars().all())

    async def live_for_plan(
        self, db: AsyncSession, clinic_id: UUID, plan_number: str | None
    ) -> list[BudgetBrief]:
        if not plan_number:
            return []
        result = await db.execute(
            select(Budget)
            .where(
                Budget.clinic_id == clinic_id,
                Budget.deleted_at.is_(None),
                Budget.status != "cancelled",
                Budget.plan_number_snapshot == plan_number,
            )
            .order_by(Budget.created_at.asc())
        )
        return [_brief(budget) for budget in result.scalars()]

    async def priced_treatment_ids(
        self, db: AsyncSession, clinic_id: UUID, plan_number: str | None, budget_id: UUID | None
    ) -> set[UUID]:
        conditions = _of_plan(plan_number, budget_id)
        if not conditions:
            return set()
        result = await db.execute(
            select(BudgetItem.treatment_id)
            .join(Budget, Budget.id == BudgetItem.budget_id)
            .where(
                Budget.clinic_id == clinic_id,
                Budget.deleted_at.is_(None),
                Budget.status != "cancelled",
                BudgetItem.treatment_id.is_not(None),
                or_(*conditions),
            )
        )
        return set(result.scalars().all())


plan_budgets = BudgetPlanBudgets()
