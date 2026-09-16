"""Handing the settlement over, and the till movement that is the same fact.

Before this, the quincena ended half-done: you issued a settlement saying
699 and then typed a movement of 699 into the till by hand. Two entries, no
link, one figure copied by a person — and when somebody types 700, or pays
in two goes, or forgets, the arqueo comes up wrong and nobody knows why.

The rules worth holding: only cash touches the drawer, the movement and the
payout are written in one transaction, and undoing a payout stops being
possible once the till day it landed on has been counted.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.utils.clinic_time import clinic_date
from app.modules.cashbox.models import CashMovement
from app.modules.patients.models import Patient
from app.modules.payments.models import PatientEarnedEntry, Payment, PaymentAllocation
from app.modules.professionals.models import Professional

BASE = "/api/v1/liquidations"
CASH = "/api/v1/cashbox"
TZ = "America/Mexico_City"
TODAY = clinic_date(datetime.now(UTC), TZ)
FROM, TO = TODAY - timedelta(days=10), TODAY - timedelta(days=1)


@pytest.fixture
async def ctx(
    db_session: AsyncSession,
    auth_headers: dict,
    client: AsyncClient,
    test_clinic: Clinic,
) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    patient = Patient(id=uuid4(), clinic_id=test_clinic.id, first_name="Pago", last_name="Prueba")
    ana = Professional(
        id=uuid4(),
        clinic_id=test_clinic.id,
        first_name="Ana",
        last_name="Asociada",
        professional_type="dentist",
    )
    db_session.add_all([patient, ana])
    await db_session.commit()
    return {
        "clinic_id": test_clinic.id,
        "user_id": UUID(me.json()["data"]["user"]["id"]),
        "patient_id": patient.id,
        "ana": ana.id,
        "currency": test_clinic.currency,
    }


async def _settled(
    db: AsyncSession, client: AsyncClient, headers: dict, ctx: dict, amount: str = "1000.00"
) -> dict:
    """A professional with 1.000 earned and collected, settled at 40 %."""
    db.add(
        PatientEarnedEntry(
            id=uuid4(),
            clinic_id=ctx["clinic_id"],
            patient_id=ctx["patient_id"],
            treatment_id=uuid4(),
            description="Endodoncia",
            amount=Decimal(amount),
            performed_at=datetime.combine(FROM, datetime.min.time(), tzinfo=UTC)
            + timedelta(hours=18),
            professional_id=ctx["ana"],
            source_event="test",
        )
    )
    payment = Payment(
        id=uuid4(),
        clinic_id=ctx["clinic_id"],
        patient_id=ctx["patient_id"],
        amount=Decimal(amount),
        currency=ctx["currency"],
        method="cash",
        payment_date=FROM,
        recorded_by=ctx["user_id"],
    )
    db.add(payment)
    await db.flush()
    db.add(
        PaymentAllocation(
            id=uuid4(),
            clinic_id=ctx["clinic_id"],
            payment_id=payment.id,
            target_type="on_account",
            amount=Decimal(amount),
            created_by=ctx["user_id"],
        )
    )
    await db.commit()

    await client.put(
        f"{BASE}/commissions/{ctx['ana']}",
        json={"basis": "collected", "percent": "40.00"},
        headers=headers,
    )
    issued = await client.post(
        BASE,
        json={
            "professional_id": str(ctx["ana"]),
            "date_from": FROM.isoformat(),
            "date_to": TO.isoformat(),
        },
        headers=headers,
    )
    assert issued.status_code == 201, issued.text
    return issued.json()["data"]


async def _movements(client: AsyncClient, headers: dict, day: date) -> list[dict]:
    response = await client.get(
        f"{CASH}/movements",
        params={"date_from": day.isoformat(), "date_to": day.isoformat()},
        headers=headers,
    )
    return response.json()["data"]


# --- Paying in cash ---------------------------------------------------


async def test_paying_in_cash_writes_the_till_movement(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """One figure, one act. Nobody retypes 400 into the till by hand."""
    settled = await _settled(db_session, client, auth_headers, ctx)
    assert Decimal(settled["amount_due"]) == Decimal("400.00")

    paid = await client.post(
        f"{BASE}/{settled['id']}/pay",
        json={"method": "cash", "business_date": TODAY.isoformat()},
        headers=auth_headers,
    )
    assert paid.status_code == 200, paid.text
    data = paid.json()["data"]

    assert data["paid_at"] is not None
    assert data["payment_method"] == "cash"
    assert data["payer"]["id"] == str(ctx["user_id"])
    assert data["cash_movement_id"] is not None

    movements = await _movements(client, auth_headers, TODAY)
    assert len(movements) == 1
    movement = movements[0]
    assert movement["id"] == data["cash_movement_id"]
    assert movement["direction"] == "out"
    assert Decimal(movement["amount"]) == Decimal("400.00")
    assert movement["category"] == "professional_payout"
    # Readable from the till without following the link back.
    assert "Ana Asociada" in movement["concept"]


async def test_the_payout_is_its_own_category(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Not `advance`: an advance is deducted later, a settlement is the pay.

    A report that cannot tell them apart is useless for both.
    """
    settled = await _settled(db_session, client, auth_headers, ctx)
    await client.post(
        f"{BASE}/{settled['id']}/pay",
        json={"method": "cash", "business_date": TODAY.isoformat()},
        headers=auth_headers,
    )
    movement = (await _movements(client, auth_headers, TODAY))[0]
    assert movement["category"] == "professional_payout"


async def test_the_payout_lands_on_todays_till_by_default(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    settled = await _settled(db_session, client, auth_headers, ctx)
    await client.post(f"{BASE}/{settled['id']}/pay", json={"method": "cash"}, headers=auth_headers)
    assert len(await _movements(client, auth_headers, TODAY)) == 1


# --- Paying any other way ---------------------------------------------


async def test_a_transfer_never_touches_the_drawer(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """The money reaches the bank without the till opening.

    Writing a movement for it would make the next arqueo come up short by
    the whole payout — a bug that looks exactly like theft.
    """
    settled = await _settled(db_session, client, auth_headers, ctx)

    paid = await client.post(
        f"{BASE}/{settled['id']}/pay", json={"method": "transfer"}, headers=auth_headers
    )
    assert paid.status_code == 200, paid.text
    data = paid.json()["data"]

    assert data["paid_at"] is not None
    assert data["payment_method"] == "transfer"
    assert data["cash_movement_id"] is None
    assert await _movements(client, auth_headers, TODAY) == []


# --- The state machine ------------------------------------------------


async def test_a_settlement_is_paid_once(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    settled = await _settled(db_session, client, auth_headers, ctx)
    body = {"method": "cash", "business_date": TODAY.isoformat()}
    assert (
        await client.post(f"{BASE}/{settled['id']}/pay", json=body, headers=auth_headers)
    ).status_code == 200
    second = await client.post(f"{BASE}/{settled['id']}/pay", json=body, headers=auth_headers)
    assert second.status_code == 422
    assert "already been paid" in second.json()["message"]
    # And it did not write a second movement.
    assert len(await _movements(client, auth_headers, TODAY)) == 1


async def test_paying_does_not_move_the_settled_figures(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """The freeze survives the payout: it records a later fact, not a change."""
    settled = await _settled(db_session, client, auth_headers, ctx)
    await client.post(
        f"{BASE}/{settled['id']}/pay",
        json={"method": "cash", "business_date": TODAY.isoformat()},
        headers=auth_headers,
    )
    reread = (await client.get(f"{BASE}/{settled['id']}", headers=auth_headers)).json()["data"]
    assert Decimal(reread["amount_due"]) == Decimal(settled["amount_due"])
    assert Decimal(reread["collected_total"]) == Decimal(settled["collected_total"])
    assert reread["lines"] == settled["lines"]


async def test_an_unpaid_settlement_cannot_be_unpaid(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    settled = await _settled(db_session, client, auth_headers, ctx)
    response = await client.post(f"{BASE}/{settled['id']}/unpay", headers=auth_headers)
    assert response.status_code == 422


# --- Undoing ----------------------------------------------------------


async def test_undoing_a_payout_takes_the_movement_with_it(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """An irreversible mistaken payout is what makes people distrust a screen."""
    settled = await _settled(db_session, client, auth_headers, ctx)
    await client.post(
        f"{BASE}/{settled['id']}/pay",
        json={"method": "cash", "business_date": TODAY.isoformat()},
        headers=auth_headers,
    )
    assert len(await _movements(client, auth_headers, TODAY)) == 1

    undone = await client.post(f"{BASE}/{settled['id']}/unpay", headers=auth_headers)
    assert undone.status_code == 200, undone.text
    data = undone.json()["data"]

    assert data["paid_at"] is None
    assert data["payment_method"] is None
    assert data["cash_movement_id"] is None
    assert await _movements(client, auth_headers, TODAY) == []

    # And it can be paid again, which is the point of undoing it.
    again = await client.post(
        f"{BASE}/{settled['id']}/pay",
        json={"method": "cash", "business_date": TODAY.isoformat()},
        headers=auth_headers,
    )
    assert again.status_code == 200


async def test_undoing_a_transfer_leaves_nothing_to_clean_up(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    settled = await _settled(db_session, client, auth_headers, ctx)
    await client.post(
        f"{BASE}/{settled['id']}/pay", json={"method": "transfer"}, headers=auth_headers
    )
    undone = await client.post(f"{BASE}/{settled['id']}/unpay", headers=auth_headers)
    assert undone.status_code == 200
    assert undone.json()["data"]["paid_at"] is None


async def test_a_counted_payout_can_no_longer_be_undone(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """The rule every other edit in the till follows, reaching this one.

    Once the day is counted the movement is part of a number somebody stood
    behind, and the way back is to reopen the day.
    """
    settled = await _settled(db_session, client, auth_headers, ctx)
    await client.post(
        f"{BASE}/{settled['id']}/pay",
        json={"method": "cash", "business_date": TODAY.isoformat()},
        headers=auth_headers,
    )
    closed = await client.post(
        f"{CASH}/closings",
        json={
            "business_date": TODAY.isoformat(),
            "counted_cash": "0",
            "opening_float": "0",
            "closing_float": "0",
            "notes": "Contado con el pago a Ana dentro.",
        },
        headers=auth_headers,
    )
    assert closed.status_code == 201, closed.text

    refused = await client.post(f"{BASE}/{settled['id']}/unpay", headers=auth_headers)
    assert refused.status_code == 422
    assert "Reopen the day" in refused.json()["message"]

    # Nothing was half-undone: the settlement still reads paid and the
    # movement is still inside the count.
    reread = (await client.get(f"{BASE}/{settled['id']}", headers=auth_headers)).json()["data"]
    assert reread["paid_at"] is not None
    assert reread["cash_movement_id"] is not None


async def test_the_payout_is_counted_by_the_arqueo(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """The loop closing: what the settlement paid is what the drawer is short."""
    settled = await _settled(db_session, client, auth_headers, ctx)
    await client.post(
        f"{BASE}/{settled['id']}/pay",
        json={"method": "cash", "business_date": TODAY.isoformat()},
        headers=auth_headers,
    )

    position = await client.get(
        f"{CASH}/position",
        params={"business_date": TODAY.isoformat()},
        headers=auth_headers,
    )
    data = position.json()["data"]
    assert Decimal(data["movements_out"]) == Decimal("400.00")
    assert Decimal(data["expected_cash"]) == Decimal("-400.00")


async def test_the_payout_movement_cannot_be_edited_from_the_till(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Editing it there would succeed and leave the settlement lying.

    The settlement would keep claiming it paid 400 while the till moved
    something else. Deleting is refused too — the foreign key would have
    turned that into a 500 rather than an explanation.
    """
    settled = await _settled(db_session, client, auth_headers, ctx)
    paid = await client.post(
        f"{BASE}/{settled['id']}/pay",
        json={"method": "cash", "business_date": TODAY.isoformat()},
        headers=auth_headers,
    )
    movement_id = paid.json()["data"]["cash_movement_id"]

    edit = await client.put(
        f"{CASH}/movements/{movement_id}",
        json={"amount": "1.00"},
        headers=auth_headers,
    )
    assert edit.status_code == 422
    assert "payout of a settlement" in edit.json()["message"]

    delete = await client.delete(f"{CASH}/movements/{movement_id}", headers=auth_headers)
    assert delete.status_code == 422

    # And the sanctioned way out still works.
    undone = await client.post(f"{BASE}/{settled['id']}/unpay", headers=auth_headers)
    assert undone.status_code == 200, undone.text
    assert await _movements(client, auth_headers, TODAY) == []


async def test_another_clinics_settlement_cannot_be_paid(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    response = await client.post(
        f"{BASE}/{uuid4()}/pay", json={"method": "cash"}, headers=auth_headers
    )
    assert response.status_code == 404


async def test_the_movement_belongs_to_the_paying_clinic(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    settled = await _settled(db_session, client, auth_headers, ctx)
    paid = await client.post(
        f"{BASE}/{settled['id']}/pay",
        json={"method": "cash", "business_date": TODAY.isoformat()},
        headers=auth_headers,
    )
    movement_id = UUID(paid.json()["data"]["cash_movement_id"])
    movement = await db_session.scalar(select(CashMovement).where(CashMovement.id == movement_id))
    assert movement.clinic_id == ctx["clinic_id"]
