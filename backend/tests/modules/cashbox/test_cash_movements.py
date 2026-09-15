"""Till movements — the money that leaves the drawer without being a payment.

These exist because the arqueo that lands in phase 2 is arithmetic on top of
them, and every rule that arithmetic depends on is pinned here: the amount is
always positive with the direction carrying the sign, the day is the clinic's
own calendar day, the two directions are never netted into one figure, and a
movement stops being editable the moment its day is closed.

The last one is tested against a hand-stamped `closing_id` rather than a real
closing, because closings do not exist yet. When they do, the rule they rely
on is already nailed down.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.utils.clinic_time import clinic_date
from app.modules.cashbox.models import CashClosing, CashMovement

BASE = "/api/v1/cashbox"

# The clinic's own day, not the container's — see the note in
# `test_cash_closings.py`. Movements themselves accept any day, but the
# closing tests share these helpers and the API refuses a future one.
TODAY = clinic_date(datetime.now(UTC), "America/Mexico_City")


@pytest.fixture
async def ctx(
    db_session: AsyncSession,
    auth_headers: dict,
    client: AsyncClient,
    test_clinic: Clinic,
) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    return {
        "clinic_id": test_clinic.id,
        "user_id": UUID(me.json()["data"]["user"]["id"]),
        "currency": test_clinic.currency,
    }


def _payload(**overrides) -> dict:
    body = {
        "business_date": TODAY.isoformat(),
        "direction": "out",
        "amount": "450.00",
        "category": "lab",
        "concept": "Mensajero del laboratorio, coronas de Pérez",
    }
    body.update(overrides)
    return body


async def _create(client: AsyncClient, headers: dict, **overrides):
    return await client.post(f"{BASE}/movements", json=_payload(**overrides), headers=headers)


# --- The basics -------------------------------------------------------


async def test_records_money_leaving_the_till(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    response = await _create(client, auth_headers)
    assert response.status_code == 201, response.text
    data = response.json()["data"]

    assert data["direction"] == "out"
    assert Decimal(data["amount"]) == Decimal("450.00")
    assert data["category"] == "lab"
    # An open day: nothing has frozen this row yet.
    assert data["closing_id"] is None
    # Currency is the clinic's, snapshotted like `Payment` does.
    assert data["currency"] == ctx["currency"]
    assert data["recorder"]["id"] == str(ctx["user_id"])


async def test_records_money_entering_the_till(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    response = await _create(
        client,
        auth_headers,
        direction="in",
        category="float_adjustment",
        amount="1000.00",
        concept="Cambio traído de la caja fuerte",
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["direction"] == "in"


async def test_the_amount_is_always_positive(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Direction carries the sign, so a negative amount is a mistake.

    A negative number in a till listing reads as a correction, and with a
    signed amount half the rows would carry one.
    """
    assert (await _create(client, auth_headers, amount="-450.00")).status_code == 422
    assert (await _create(client, auth_headers, amount="0")).status_code == 422


async def test_a_blank_concept_is_refused(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """A row whose concept is three spaces is a row nobody can audit."""
    assert (await _create(client, auth_headers, concept="   ")).status_code == 422


async def test_the_concept_is_trimmed_not_just_accepted(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    response = await _create(client, auth_headers, concept="  Guantes de nitrilo  ")
    assert response.status_code == 201
    assert response.json()["data"]["concept"] == "Guantes de nitrilo"


async def test_an_unknown_category_is_refused(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """The list is closed so a report can group by it and mean something."""
    assert (await _create(client, auth_headers, category="misc")).status_code == 422


# --- The day ----------------------------------------------------------


async def test_listing_is_filtered_by_the_days_asked_for(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    today = TODAY
    yesterday = today - timedelta(days=1)
    await _create(client, auth_headers, business_date=today.isoformat())
    await _create(client, auth_headers, business_date=yesterday.isoformat())

    response = await client.get(
        f"{BASE}/movements",
        params={"date_from": today.isoformat(), "date_to": today.isoformat()},
        headers=auth_headers,
    )
    assert response.status_code == 200
    rows = response.json()["data"]
    assert len(rows) == 1
    assert rows[0]["business_date"] == today.isoformat()


async def test_day_totals_never_net_the_two_directions(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """5.000 in and 5.000 out is not a quiet day, and must not read as one."""
    today = TODAY
    await _create(client, auth_headers, direction="in", amount="5000.00")
    await _create(client, auth_headers, direction="out", amount="5000.00")

    response = await client.get(
        f"{BASE}/movements/totals",
        params={"business_date": today.isoformat()},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    totals = response.json()["data"]
    assert Decimal(totals["total_in"]) == Decimal("5000.00")
    assert Decimal(totals["total_out"]) == Decimal("5000.00")
    assert Decimal(totals["net"]) == Decimal("0")
    # The count is what stops the zero being read as "nothing happened".
    assert totals["count"] == 2


async def test_day_totals_of_an_empty_day_are_zero_not_an_error(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    response = await client.get(
        f"{BASE}/movements/totals",
        params={"business_date": (TODAY - timedelta(days=30)).isoformat()},
        headers=auth_headers,
    )
    assert response.status_code == 200
    totals = response.json()["data"]
    assert Decimal(totals["total_in"]) == Decimal("0")
    assert Decimal(totals["total_out"]) == Decimal("0")
    assert totals["count"] == 0


async def test_totals_resolves_before_the_movement_id_route(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """`/movements/totals` must not parse as `/movements/{id}`.

    FastAPI resolves in registration order; the same trap returned a 422
    from `payments`' own `/reports/refunds` for weeks.
    """
    response = await client.get(
        f"{BASE}/movements/totals",
        params={"business_date": TODAY.isoformat()},
        headers=auth_headers,
    )
    assert response.status_code == 200


# --- Correcting, and the point at which you no longer can --------------


async def test_an_open_movement_can_be_corrected(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    created = (await _create(client, auth_headers)).json()["data"]

    response = await client.put(
        f"{BASE}/movements/{created['id']}",
        json={"amount": "500.00", "concept": "Mensajero: eran 500, no 450"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert Decimal(data["amount"]) == Decimal("500.00")
    # Untouched fields survive a partial update.
    assert data["category"] == "lab"


async def test_a_movement_filed_on_the_wrong_day_can_be_moved(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """The commonest correction there is, so it must not need a delete."""
    created = (await _create(client, auth_headers)).json()["data"]
    yesterday = (TODAY - timedelta(days=1)).isoformat()

    response = await client.put(
        f"{BASE}/movements/{created['id']}",
        json={"business_date": yesterday},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["business_date"] == yesterday


async def test_an_open_movement_can_be_deleted(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    created = (await _create(client, auth_headers)).json()["data"]
    assert (
        await client.delete(f"{BASE}/movements/{created['id']}", headers=auth_headers)
    ).status_code == 204
    assert (
        await client.get(f"{BASE}/movements/{created['id']}", headers=auth_headers)
    ).status_code == 404


async def test_a_movement_of_a_closed_day_can_no_longer_be_changed(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """The rule the whole arqueo rests on.

    Once a person has counted the drawer and signed off the day, the rows
    that produced that number stop being notes and become part of an
    accounting record. Changing one afterwards would make the signed number
    a lie. `closing_id` is stamped by hand here because `CashClosing`
    arrives in phase 2 — the rule it will depend on is already held.
    """
    created = (await _create(client, auth_headers)).json()["data"]

    closing = CashClosing(
        id=uuid4(),
        clinic_id=ctx["clinic_id"],
        business_date=TODAY,
        status="closed",
        currency=ctx["currency"],
        opening_float=Decimal("0"),
        expected_cash=Decimal("-450.00"),
        counted_cash=Decimal("0"),
        difference=Decimal("450.00"),
        closing_float=Decimal("0"),
        snapshot={},
        notes="Contado a mano para la prueba.",
        closed_at=datetime.now(UTC),
        closed_by=ctx["user_id"],
    )
    db_session.add(closing)
    await db_session.flush()

    movement = await db_session.scalar(
        select(CashMovement).where(CashMovement.id == UUID(created["id"]))
    )
    movement.closing_id = closing.id
    await db_session.commit()

    edit = await client.put(
        f"{BASE}/movements/{created['id']}",
        json={"amount": "1.00"},
        headers=auth_headers,
    )
    assert edit.status_code == 422
    # The app wraps HTTPException in `ErrorResponse`, so the reason lands
    # in `message`, not `detail`.
    assert "closed day" in edit.json()["message"]

    delete = await client.delete(f"{BASE}/movements/{created['id']}", headers=auth_headers)
    assert delete.status_code == 422

    # And the row is still exactly as it was.
    await db_session.refresh(movement)
    assert movement.amount == Decimal("450.00")


# --- Multi-tenancy ----------------------------------------------------


async def test_another_clinics_movement_is_not_found(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Not 403 — a row of another tenant should not confirm it exists."""
    other = Clinic(
        id=uuid4(),
        name="Otra Clínica",
        tax_id="B99999999",
        settings={},
        account_tier="clinic",
    )
    db_session.add(other)
    await db_session.flush()
    stranger = CashMovement(
        id=uuid4(),
        clinic_id=other.id,
        business_date=TODAY,
        direction="out",
        amount=Decimal("100.00"),
        currency="MXN",
        category="other",
        concept="No es de esta clínica",
        recorded_by=ctx["user_id"],
    )
    db_session.add(stranger)
    await db_session.commit()

    assert (
        await client.get(f"{BASE}/movements/{stranger.id}", headers=auth_headers)
    ).status_code == 404

    listed = await client.get(f"{BASE}/movements", headers=auth_headers)
    assert all(row["id"] != str(stranger.id) for row in listed.json()["data"])
