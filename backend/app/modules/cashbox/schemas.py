"""Cashbox module Pydantic schemas for API request/response."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

MovementDirection = Literal["in", "out"]
MovementCategory = Literal[
    "lab",
    "supplies",
    "advance",
    "professional_payout",
    "bank_deposit",
    "float_adjustment",
    "other",
]


class UserBrief(BaseModel):
    id: UUID
    first_name: str
    last_name: str

    model_config = ConfigDict(from_attributes=True)


class CashMovementCreate(BaseModel):
    business_date: date
    direction: MovementDirection
    # Always positive. Direction carries the sign, so a negative amount
    # here is a mistake rather than a shorthand — see the model.
    amount: Decimal = Field(gt=0)
    category: MovementCategory
    concept: str = Field(min_length=1, max_length=160)
    reference: str | None = Field(default=None, max_length=100)
    notes: str | None = None

    @field_validator("concept")
    @classmethod
    def _concept_not_blank(cls, value: str) -> str:
        """A row whose concept is three spaces is a row nobody can audit."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("concept cannot be blank")
        return cleaned


class CashMovementUpdate(BaseModel):
    """Every field optional — a correction usually touches one of them.

    `business_date` is included: the commonest correction is a movement
    filed on the wrong day, and forbidding it would mean deleting and
    retyping the row.
    """

    business_date: date | None = None
    direction: MovementDirection | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    category: MovementCategory | None = None
    concept: str | None = Field(default=None, min_length=1, max_length=160)
    reference: str | None = Field(default=None, max_length=100)
    notes: str | None = None

    @field_validator("concept")
    @classmethod
    def _concept_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("concept cannot be blank")
        return cleaned


class CashMovementResponse(BaseModel):
    id: UUID
    business_date: date
    direction: str
    amount: Decimal
    currency: str
    category: str
    concept: str
    reference: str | None = None
    notes: str | None = None
    # Null while the day is open. Its presence is what makes the row
    # read-only, so the client needs it to decide whether to offer editing.
    closing_id: UUID | None = None
    recorded_by: UUID
    recorder: UserBrief | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CashMovementDayTotals(BaseModel):
    """What the movements of a day add up to, split by direction.

    Kept apart from the list because the till's arithmetic reads them
    separately: the expected cash adds the ins and subtracts the outs, and
    a single net figure would hide a day of 5.000 in and 5.000 out behind
    a zero.
    """

    business_date: date
    currency: str
    total_in: Decimal
    total_out: Decimal
    net: Decimal
    count: int


# --- The arqueo -------------------------------------------------------


class MethodTotal(BaseModel):
    method: str
    amount: Decimal
    count: int


class CashPosition(BaseModel):
    """What the drawer should hold right now, and where the figure came from.

    Returned before the count so the screen can show the workings — the
    collections, the refunds, the movements — **without** showing the total.
    Handing someone the expected figure before they count is how a till
    reconciliation turns into a year of zeroes: they type what it says.
    `expected_cash` is here because the same endpoint serves the history
    view, where the day is already closed and there is nothing left to bias.
    """

    business_date: date
    currency: str
    opening_float: Decimal
    cash_collected: Decimal
    cash_refunded: Decimal
    movements_in: Decimal
    movements_out: Decimal
    expected_cash: Decimal
    # Everything that came in that day, cash or not. Information only: a
    # card batch settles itself and a transfer is not till money at all, so
    # neither is part of anything to count.
    collected_by_method: list[MethodTotal]
    #: The standing count, when the day already has one.
    closing: "CashClosingResponse | None" = None


class CashClosingCreate(BaseModel):
    business_date: date
    counted_cash: Decimal = Field(ge=0)
    opening_float: Decimal = Field(ge=0)
    #: What stays in the drawer for tomorrow. The rest was taken out.
    closing_float: Decimal = Field(ge=0)
    #: The service requires it when the count does not match.
    notes: str | None = None


class CashClosingReopen(BaseModel):
    """Reopening throws away a count somebody signed. It states why."""

    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def _reason_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("reason cannot be blank")
        return cleaned


class CashClosingResponse(BaseModel):
    id: UUID
    business_date: date
    status: str
    currency: str
    opening_float: Decimal
    expected_cash: Decimal
    counted_cash: Decimal
    difference: Decimal
    closing_float: Decimal
    snapshot: dict
    notes: str | None = None
    closed_at: datetime
    closed_by: UUID
    closer: UserBrief | None = None
    reopened_at: datetime | None = None
    reopen_reason: str | None = None
    reopener: UserBrief | None = None

    model_config = ConfigDict(from_attributes=True)


CashPosition.model_rebuild()


# --- The period cut ---------------------------------------------------

PeriodKind = Literal["week", "fortnight", "month"]


class CashPeriod(BaseModel):
    """A week, a fortnight or a month of the till, built from the arqueos.

    **Aggregated from the closings, never recalculated from `payments`.**
    That is the decision the whole phase turns on: a fortnight recomputed
    from payments looks perfectly balanced with three days nobody counted
    inside it, while one built from closings can say *three days still
    open* — which is the sentence a clinic owner actually needs.

    So every money figure here is a sum of frozen snapshots, and
    `pending_days` is what admits the rest.
    """

    kind: PeriodKind
    date_from: date
    date_to: date
    currency: str

    #: Days inside the period that carry a standing count.
    counted_days: int
    #: Days with money movement and **no** standing count. The product.
    pending_days: list[date]

    # Sums over the counted days only. Anything on a pending day is simply
    # not here, and `pending_days` is how the reader knows.
    cash_collected: Decimal
    cash_refunded: Decimal
    movements_in: Decimal
    movements_out: Decimal

    #: Net of every difference. Nets on purpose — a fortnight 50 short one
    #: day and 50 over the next is a fortnight that balances, and saying so
    #: is honest. `days_off` is what stops it reading as "nothing happened".
    difference_total: Decimal
    #: How many of the counted days did not match. The number worth watching.
    days_off: int

    #: What came in that period by every channel, cash included, from the
    #: same snapshots. Information: a card batch settles against the
    #: terminal and a transfer reaches the bank on its own schedule.
    collected_by_method: list[MethodTotal]

    #: The counts themselves, newest first — the difference history.
    closings: list["CashClosingResponse"]


CashPeriod.model_rebuild()


# --- Entries that landed after their day was counted -------------------

LateEntryKind = Literal["payment", "refund", "movement"]


class LateEntry(BaseModel):
    """Money recorded against a day that had already been counted.

    The count itself does not move — that is the whole point of a signed
    count — so this is how the clinic finds out that Friday's signed figure
    no longer describes Friday.

    **No patient identity here.** `cashbox` depends on `payments` and not on
    `patients`, and a name would be a dependency the manifest does not
    declare plus PII in a payload that does not need it. The reference and
    the amount are enough to find the row in Cobros, which is where the
    person belongs.
    """

    kind: LateEntryKind
    entry_id: UUID
    business_date: date
    currency: str
    #: Signed by its effect on the drawer: a collection adds, a refund or an
    #: outgoing movement subtracts. Summing the list gives what the day's
    #: count would say today.
    amount: Decimal
    #: The catalogue reference, the movement's concept — never a person.
    description: str | None = None
    #: When it was written down, as opposed to the day it belongs to.
    recorded_at: datetime
    #: When the day was signed off. The gap between the two is the story.
    closed_at: datetime
    acknowledged: bool = False
    resolution: str | None = None
    acknowledged_at: datetime | None = None
    acknowledger: UserBrief | None = None


class LateEntryAcknowledge(BaseModel):
    kind: LateEntryKind
    entry_id: UUID
    business_date: date
    resolution: str = Field(min_length=1, max_length=300)

    @field_validator("resolution")
    @classmethod
    def _resolution_not_blank(cls, value: str) -> str:
        """ "Seen" is not a decision anybody can act on three months later."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("resolution cannot be blank")
        return cleaned
