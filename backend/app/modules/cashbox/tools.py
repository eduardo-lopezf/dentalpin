"""Agent tools for the cashbox module.

Read only, and that is a decision rather than a stage of work. Recording a
movement is a claim about physical money — someone took notes out of a
drawer and says what for — and an agent has no way to witness that. What an
agent can usefully do is answer "where did the cash go last Tuesday",
which is a question the clinic currently cannot ask at all.

Thin wrappers over ``MovementService``; no logic duplicated, and every
handler scoped by ``ctx.clinic_id`` exactly as the routers are.
"""

from __future__ import annotations

from datetime import date as date_cls

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.agents import AgentContext, Tool, ToolCategory
from app.core.auth.models import Clinic

from .schemas import MovementCategory, MovementDirection, PeriodKind
from .service import ClosingService, MovementService, PeriodService


class MovementPeriodArgs(BaseModel):
    date_from: date_cls = Field(description="Inicio del periodo (YYYY-MM-DD).")
    date_to: date_cls = Field(description="Fin del periodo (YYYY-MM-DD).")
    direction: MovementDirection | None = Field(
        default=None, description="'in' entradas, 'out' salidas. Omitir para ambas."
    )
    category: MovementCategory | None = Field(
        default=None, description="Filtrar por categoría de movimiento."
    )


class DayTotalsArgs(BaseModel):
    business_date: date_cls = Field(description="Día de la clínica (YYYY-MM-DD).")


async def _currency(ctx: AgentContext) -> str:
    return (await ctx.db.scalar(select(Clinic.currency).where(Clinic.id == ctx.clinic_id))) or "MXN"


async def _cash_movements(ctx: AgentContext, args: MovementPeriodArgs) -> list[dict]:
    movements = await MovementService.list(
        ctx.db,
        ctx.clinic_id,
        date_from=args.date_from,
        date_to=args.date_to,
        direction=args.direction,
        category=args.category,
    )
    # Native values throughout — `jsonify` at the registry chokepoint
    # coerces Decimal and date, so coercing here would be work that also
    # loses precision.
    return [
        {
            "business_date": m.business_date,
            "direction": m.direction,
            "amount": m.amount,
            "currency": m.currency,
            "category": m.category,
            "concept": m.concept,
            "reference": m.reference,
            "closed": m.closing_id is not None,
        }
        for m in movements
    ]


async def _cash_movements_day_totals(ctx: AgentContext, args: DayTotalsArgs) -> dict:
    totals = await MovementService.day_totals(
        ctx.db, ctx.clinic_id, await _currency(ctx), args.business_date
    )
    return totals.model_dump()


class ClosingPeriodArgs(BaseModel):
    date_from: date_cls = Field(description="Inicio del periodo (YYYY-MM-DD).")
    date_to: date_cls = Field(description="Fin del periodo (YYYY-MM-DD).")


async def _cash_closings(ctx: AgentContext, args: ClosingPeriodArgs) -> list[dict]:
    closings = await ClosingService.list(
        ctx.db, ctx.clinic_id, date_from=args.date_from, date_to=args.date_to
    )
    return [
        {
            "business_date": c.business_date,
            "opening_float": c.opening_float,
            "expected_cash": c.expected_cash,
            "counted_cash": c.counted_cash,
            "difference": c.difference,
            "currency": c.currency,
            "notes": c.notes,
            "closed_at": c.closed_at,
        }
        for c in closings
    ]


class PeriodArgs(BaseModel):
    kind: PeriodKind = Field(description="week | fortnight | month.")
    day: date_cls = Field(description="Cualquier día dentro del periodo (YYYY-MM-DD).")


async def _cash_period(ctx: AgentContext, args: PeriodArgs) -> dict:
    clinic = await ctx.db.scalar(select(Clinic).where(Clinic.id == ctx.clinic_id))
    period = await PeriodService.summary(
        ctx.db,
        ctx.clinic_id,
        clinic.currency if clinic else "MXN",
        clinic.timezone if clinic else "UTC",
        args.kind,
        args.day,
    )
    # The closings themselves are dropped: the agent gets the shape of the
    # period, and `cash_closings` is the tool for the day-by-day detail.
    return period.model_dump(exclude={"closings"})


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="cash_movements",
            description=(
                "Movimientos de caja de un periodo: el dinero que entró o "
                "salió del cajón sin ser un cobro de paciente (laboratorio, "
                "material, adelantos, depósitos a banco, ajustes de fondo)."
            ),
            parameters=MovementPeriodArgs,
            handler=_cash_movements,
            permissions=["cashbox.movement.read"],
            category=ToolCategory.READ,
            # `concept` is whatever the person at the counter typed.
            exposes_free_text=True,
        ),
        Tool(
            name="cash_movements_day_totals",
            description=(
                "Entradas y salidas de caja de un día, por separado. No las "
                "netea: 5.000 que entran y 5.000 que salen no es un día "
                "tranquilo."
            ),
            parameters=DayTotalsArgs,
            handler=_cash_movements_day_totals,
            permissions=["cashbox.movement.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="cash_closings",
            description=(
                "Arqueos de caja de un periodo: lo esperado, lo contado y la "
                "diferencia de cada día, con su explicación. Solo los conteos "
                "vigentes; los reabiertos no cuentan."
            ),
            parameters=ClosingPeriodArgs,
            handler=_cash_closings,
            permissions=["cashbox.closing.read"],
            category=ToolCategory.READ,
            # `notes` is whatever the person who counted wrote.
            exposes_free_text=True,
        ),
        Tool(
            name="cash_period_summary",
            description=(
                "Corte de caja de una semana, quincena o mes, construido a "
                "partir de los arqueos diarios. Incluye los días en los que "
                "se movió dinero y nadie contó: sus importes NO están en los "
                "totales, y un periodo con días pendientes está incompleto."
            ),
            parameters=PeriodArgs,
            handler=_cash_period,
            permissions=["cashbox.closing.read"],
            category=ToolCategory.READ,
        ),
    ]
