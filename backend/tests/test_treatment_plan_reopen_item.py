"""Reopening a completed plan item.

A treatment ticked off by mistake used to have no way back: the dialog's
"Reabrir" only unlocked its own buttons, and the earned entry the completion
booked stayed on the patient's account as money owed for work the plan no
longer counted as done. Reopening now undoes the completion for real and
``payments`` drops that charge.
"""

from decimal import Decimal
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.odontogram.models import Treatment
from app.modules.payments.models import PatientEarnedEntry
from tests.test_treatment_plan import (
    _add_multi_session_item,
    _create_plan_with_items,
    _ensure_clinic_and_patient,
    _seed_catalog_crown,
    _seed_catalog_crown_with_sessions,
)


# Local fixtures over the same helpers `test_treatment_plan.py` uses:
# importing that module's fixtures would need an alias to keep ruff quiet,
# and pytest does not register a fixture under an alias.
@pytest.fixture
async def setup(db_session: AsyncSession, auth_headers: dict, client: AsyncClient) -> dict:
    ctx = await _ensure_clinic_and_patient(db_session, client, auth_headers)
    ctx["crown_id"] = await _seed_catalog_crown(db_session, ctx["clinic_id"])
    return ctx


@pytest.fixture
async def setup_multi_session(
    db_session: AsyncSession, auth_headers: dict, client: AsyncClient
) -> dict:
    ctx = await _ensure_clinic_and_patient(db_session, client, auth_headers)
    ctx["crown_ms_id"] = await _seed_catalog_crown_with_sessions(db_session, ctx["clinic_id"])
    return ctx


BASE = "/api/v1/treatment_plan/treatment-plans"


async def _earned(db: AsyncSession, treatment_id: str) -> list[PatientEarnedEntry]:
    rows = await db.execute(
        select(PatientEarnedEntry)
        .where(PatientEarnedEntry.treatment_id == UUID(treatment_id))
        .execution_options(populate_existing=True)
    )
    return list(rows.scalars().all())


async def _item(client: AsyncClient, auth_headers: dict, plan_id: str, item_id: str) -> dict:
    r = await client.get(f"{BASE}/{plan_id}", headers=auth_headers)
    assert r.status_code == 200, r.text
    return next(i for i in r.json()["data"]["items"] if i["id"] == item_id)


async def _complete(client: AsyncClient, auth_headers: dict, plan_id: str, item_id: str) -> dict:
    r = await client.patch(
        f"{BASE}/{plan_id}/items/{item_id}/complete", headers=auth_headers, json={}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _reopen(client: AsyncClient, auth_headers: dict, plan_id: str, item_id: str):
    return await client.patch(
        f"{BASE}/{plan_id}/items/{item_id}/reopen", headers=auth_headers, json={}
    )


async def _confirmed_plan(client: AsyncClient, auth_headers: dict, setup: dict, teeth: list[int]):
    plan_id, item_ids = await _create_plan_with_items(client, auth_headers, setup, teeth)
    r = await client.post(f"{BASE}/{plan_id}/confirm", headers=auth_headers)
    assert r.status_code == 200, r.text
    return plan_id, item_ids


@pytest.mark.asyncio
async def test_reopening_puts_the_item_back_to_pending(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, item_ids = await _confirmed_plan(client, auth_headers, setup, [16, 15])
    await _complete(client, auth_headers, plan_id, item_ids[0])

    r = await _reopen(client, auth_headers, plan_id, item_ids[0])
    assert r.status_code == 200, r.text
    item = r.json()["data"]
    assert item["status"] == "pending"
    assert item["completed_at"] is None
    assert all(s["status"] == "pending" for s in item["sessions"])
    assert all(s["completed_at"] is None for s in item["sessions"])


@pytest.mark.asyncio
async def test_reopening_drops_the_charge(
    client: AsyncClient, auth_headers: dict, setup: dict, db_session: AsyncSession
) -> None:
    """The whole point: nothing is left owed for work that is not done."""
    plan_id, item_ids = await _confirmed_plan(client, auth_headers, setup, [16, 15])
    item = await _complete(client, auth_headers, plan_id, item_ids[0])
    treatment_id = item["treatment_id"]
    assert sum(e.amount for e in await _earned(db_session, treatment_id)) == Decimal("500.00")

    r = await _reopen(client, auth_headers, plan_id, item_ids[0])
    assert r.status_code == 200, r.text

    assert await _earned(db_session, treatment_id) == []


@pytest.mark.asyncio
async def test_completing_again_charges_again_once(
    client: AsyncClient, auth_headers: dict, setup: dict, db_session: AsyncSession
) -> None:
    plan_id, item_ids = await _confirmed_plan(client, auth_headers, setup, [16, 15])
    item = await _complete(client, auth_headers, plan_id, item_ids[0])
    await _reopen(client, auth_headers, plan_id, item_ids[0])

    again = await _complete(client, auth_headers, plan_id, item_ids[0])
    assert again["status"] == "completed"
    entries = await _earned(db_session, item["treatment_id"])
    assert sum(e.amount for e in entries) == Decimal("500.00")


@pytest.mark.asyncio
async def test_reopening_unperforms_the_treatment_on_the_chart(
    client: AsyncClient, auth_headers: dict, setup: dict, db_session: AsyncSession
) -> None:
    plan_id, item_ids = await _confirmed_plan(client, auth_headers, setup, [16, 15])
    item = await _complete(client, auth_headers, plan_id, item_ids[0])

    await _reopen(client, auth_headers, plan_id, item_ids[0])

    treatment = (
        await db_session.execute(
            select(Treatment)
            .where(Treatment.id == UUID(item["treatment_id"]))
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert treatment.status == "planned"
    assert treatment.performed_at is None
    assert treatment.performed_by is None


@pytest.mark.asyncio
async def test_a_finished_plan_goes_back_to_active(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, item_ids = await _confirmed_plan(client, auth_headers, setup, [16])
    await _complete(client, auth_headers, plan_id, item_ids[0])
    r = await client.get(f"{BASE}/{plan_id}", headers=auth_headers)
    assert r.json()["data"]["status"] == "completed"

    await _reopen(client, auth_headers, plan_id, item_ids[0])

    r = await client.get(f"{BASE}/{plan_id}", headers=auth_headers)
    assert r.json()["data"]["status"] == "active"

    history = await client.get(f"{BASE}/{plan_id}/history", headers=auth_headers)
    newest = history.json()["data"]["entries"][0]
    assert newest["action"] == "item_reopened"
    assert (newest["from_status"], newest["to_status"]) == ("completed", "active")


@pytest.mark.asyncio
async def test_an_active_plan_stays_active_and_logs_it(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, item_ids = await _confirmed_plan(client, auth_headers, setup, [16, 15])
    await _complete(client, auth_headers, plan_id, item_ids[0])

    await _reopen(client, auth_headers, plan_id, item_ids[0])

    r = await client.get(f"{BASE}/{plan_id}", headers=auth_headers)
    assert r.json()["data"]["status"] == "active"
    history = await client.get(f"{BASE}/{plan_id}/history", headers=auth_headers)
    newest = history.json()["data"]["entries"][0]
    assert newest["action"] == "item_reopened"
    assert newest["from_status"] is None
    assert newest["payload"]["treatment"]


@pytest.mark.asyncio
async def test_only_a_completed_item_can_be_reopened(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, item_ids = await _confirmed_plan(client, auth_headers, setup, [16])

    r = await _reopen(client, auth_headers, plan_id, item_ids[0])
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_a_closed_plan_must_be_reactivated_first(
    client: AsyncClient, auth_headers: dict, setup: dict, db_session: AsyncSession
) -> None:
    plan_id, item_ids = await _confirmed_plan(client, auth_headers, setup, [16, 15])
    item = await _complete(client, auth_headers, plan_id, item_ids[0])
    r = await client.post(
        f"{BASE}/{plan_id}/close",
        headers=auth_headers,
        json={"closure_reason": "cancelled_by_clinic"},
    )
    assert r.status_code == 200, r.text

    r = await _reopen(client, auth_headers, plan_id, item_ids[0])
    assert r.status_code == 400
    assert "Reactivate" in r.text
    # Refused means nothing moved, the charge included.
    assert (await _item(client, auth_headers, plan_id, item_ids[0]))["status"] == "completed"
    assert len(await _earned(db_session, item["treatment_id"])) == 1


@pytest.mark.asyncio
async def test_unknown_item_is_404(client: AsyncClient, auth_headers: dict, setup: dict) -> None:
    plan_id, _ = await _confirmed_plan(client, auth_headers, setup, [16])
    r = await _reopen(client, auth_headers, plan_id, "00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_multi_session_reopens_only_the_last_session(
    client: AsyncClient,
    auth_headers: dict,
    setup_multi_session: dict,
    db_session: AsyncSession,
) -> None:
    """Ticking the last visit by mistake must not undo the ones that happened."""
    plan_id, item_id, sessions = await _add_multi_session_item(
        client, auth_headers, setup_multi_session
    )
    for s in sessions:
        r = await client.patch(
            f"{BASE}/{plan_id}/items/{item_id}/sessions/{s['id']}/complete",
            headers=auth_headers,
            json={},
        )
        assert r.status_code == 200, r.text
    treatment_id = r.json()["data"]["treatment_id"]
    assert sum(e.amount for e in await _earned(db_session, treatment_id)) == Decimal("800.00")

    r = await _reopen(client, auth_headers, plan_id, item_id)
    assert r.status_code == 200, r.text
    item = r.json()["data"]
    by_seq = {s["sequence"]: s["status"] for s in item["sessions"]}
    assert by_seq == {1: "completed", 2: "pending"}
    assert item["status"] == "pending"

    entries = await _earned(db_session, treatment_id)
    assert [e.amount for e in entries] == [Decimal("200.00")]
    assert entries[0].source_session_id == UUID(sessions[0]["id"])


@pytest.mark.asyncio
async def test_a_cancelled_last_session_is_undone_without_touching_money(
    client: AsyncClient,
    auth_headers: dict,
    setup_multi_session: dict,
    db_session: AsyncSession,
) -> None:
    """When a cancellation is what closed the item, that is what gets undone."""
    plan_id, item_id, sessions = await _add_multi_session_item(
        client, auth_headers, setup_multi_session
    )
    await client.patch(
        f"{BASE}/{plan_id}/items/{item_id}/sessions/{sessions[0]['id']}/complete",
        headers=auth_headers,
        json={},
    )
    r = await client.patch(
        f"{BASE}/{plan_id}/items/{item_id}/sessions/{sessions[1]['id']}/cancel",
        headers=auth_headers,
        json={},
    )
    assert r.json()["data"]["status"] == "completed"
    treatment_id = r.json()["data"]["treatment_id"]

    r = await _reopen(client, auth_headers, plan_id, item_id)
    assert r.status_code == 200, r.text
    by_seq = {s["sequence"]: s["status"] for s in r.json()["data"]["sessions"]}
    assert by_seq == {1: "completed", 2: "pending"}
    assert [e.amount for e in await _earned(db_session, treatment_id)] == [Decimal("200.00")]
