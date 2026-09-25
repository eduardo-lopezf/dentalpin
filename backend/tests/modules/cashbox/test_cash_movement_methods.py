"""Money that leaves the clinic without leaving the drawer.

The table was the till and nothing else, so the only outflow the product
could record was cash. A clinic pays its lab by transfer, its rent by
direct debit and its supplier on thirty days — none of it passed through
a drawer, so none of it could be written down, and every outflow figure
in the system was the drawer's alone.

`method` is what lets those rows exist. The rule that keeps the arqueo
honest is that **only `cash` is counted**: the tests below pin it from
both ends, because getting it wrong is invisible until a clinic is short
by exactly its bank payments every single evening.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.utils.clinic_time import clinic_date
from app.modules.patients.models import Patient

BASE = "/api/v1/cashbox"
TODAY = clinic_date(datetime.now(UTC), "America/Mexico_City")


@pytest.fixture
async def ctx(
    db_session: AsyncSession,
    auth_headers: dict,
    client: AsyncClient,
    test_clinic: Clinic,
) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    patient = Patient(id=uuid4(), clinic_id=test_clinic.id, first_name="Caja", last_name="Metodo")
    db_session.add(patient)
    await db_session.commit()
    return {
        "clinic_id": test_clinic.id,
        "user_id": UUID(me.json()["data"]["user"]["id"]),
        "currency": test_clinic.currency,
    }


async def _movement(
    client: AsyncClient,
    headers: dict,
    direction: str,
    amount: str,
    *,
    method: str | None = None,
) -> dict:
    body = {
        "business_date": TODAY.isoformat(),
        "direction": direction,
        "amount": amount,
        "category": "lab",
        "concept": "Laboratorio",
    }
    if method is not None:
        body["method"] = method
    response = await client.post(f"{BASE}/movements", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _totals(client: AsyncClient, headers: dict) -> dict:
    response = await client.get(
        f"{BASE}/movements/totals",
        params={"business_date": TODAY.isoformat()},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def _close(client: AsyncClient, headers: dict, counted: str):
    """Declare the count. `opening_float` is required and zero here — the
    tests build whatever float they need out of movements instead."""
    return await client.post(
        f"{BASE}/closings",
        json={
            "business_date": TODAY.isoformat(),
            "counted_cash": counted,
            "opening_float": "0",
            "closing_float": "0",
        },
        headers=headers,
    )


async def _position(client: AsyncClient, headers: dict) -> dict:
    response = await client.get(
        f"{BASE}/position",
        params={"business_date": TODAY.isoformat()},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


@pytest.mark.asyncio
async def test_a_movement_is_cash_unless_it_says_otherwise(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Every row written before this column existed was cash, and still is."""
    created = await _movement(client, auth_headers, "out", "100.00")
    assert created["method"] == "cash"


@pytest.mark.asyncio
async def test_a_transfer_never_reaches_the_expected_cash(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """The one rule. Counting it would make every arqueo report a shortfall."""
    before = await _position(client, auth_headers)

    await _movement(client, auth_headers, "out", "700.00", method="bank_transfer")

    after = await _position(client, auth_headers)
    assert after["expected_cash"] == before["expected_cash"]
    assert after["movements_out"] == before["movements_out"]


@pytest.mark.asyncio
async def test_cash_still_moves_the_expected_cash(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """The other end of the same rule — the guard must not silence the till."""
    before = await _position(client, auth_headers)

    await _movement(client, auth_headers, "out", "40.00", method="cash")

    after = await _position(client, auth_headers)
    assert float(before["expected_cash"]) - float(after["expected_cash"]) == 40.0


@pytest.mark.asyncio
async def test_the_day_counts_everything_and_the_drawer_counts_its_share(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Two true totals, side by side. Conflating them is the whole danger."""
    await _movement(client, auth_headers, "out", "60.00", method="cash")
    await _movement(client, auth_headers, "out", "900.00", method="bank_transfer")
    await _movement(client, auth_headers, "in", "20.00", method="cash")

    totals = await _totals(client, auth_headers)
    assert float(totals["total_out"]) == 960.0
    assert float(totals["cash_out"]) == 60.0
    assert float(totals["total_in"]) == 20.0
    assert float(totals["cash_in"]) == 20.0


@pytest.mark.asyncio
async def test_closing_the_day_freezes_the_drawer_and_leaves_the_rest_alone(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """A closing is a statement about the drawer, so it freezes the drawer.

    Freezing the rent paid by transfer because somebody counted the notes
    would make a typo in it uncorrectable for a reason that has nothing to
    do with it.
    """
    # A float to spend out of, so the drawer does not go negative — a count
    # below zero is refused, and rightly.
    await _movement(client, auth_headers, "in", "100.00", method="cash")
    cash = await _movement(client, auth_headers, "out", "30.00", method="cash")
    transfer = await _movement(client, auth_headers, "out", "500.00", method="bank_transfer")

    position = await _position(client, auth_headers)
    closed = await _close(client, auth_headers, position["expected_cash"])
    assert closed.status_code == 201, closed.text

    listed = await client.get(
        f"{BASE}/movements",
        params={"business_date": TODAY.isoformat()},
        headers=auth_headers,
    )
    rows = {r["id"]: r for r in listed.json()["data"]}
    assert rows[cash["id"]]["closing_id"] is not None, "the counted row must be frozen"
    assert rows[transfer["id"]]["closing_id"] is None, "the transfer was never counted"

    # And the transfer stays correctable, which is the point of not stamping it.
    edited = await client.put(
        f"{BASE}/movements/{transfer['id']}",
        json={"concept": "Alquiler de septiembre"},
        headers=auth_headers,
    )
    assert edited.status_code == 200, edited.text


@pytest.mark.asyncio
async def test_a_transfer_in_a_closed_day_is_not_reported_late(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Otherwise the list this screen exists to empty could never empty."""
    transfer = await _movement(client, auth_headers, "out", "250.00", method="bank_transfer")

    position = await _position(client, auth_headers)
    # The count is unmoved by the transfer, which is the rule under test:
    # the day closes clean with nothing counted against those 250.
    closed = await _close(client, auth_headers, position["expected_cash"])
    assert closed.status_code == 201, closed.text

    late = await client.get(
        f"{BASE}/late-entries",
        params={"date_from": TODAY.isoformat(), "date_to": TODAY.isoformat()},
        headers=auth_headers,
    )
    assert late.status_code == 200, late.text
    ids = [e["entry_id"] for e in late.json()["data"]]
    assert transfer["id"] not in ids
