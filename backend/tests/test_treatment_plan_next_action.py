"""The one thing that has to happen next for a plan to move on.

A plan changes hands as it advances — dentist, patient, reception — and the
stepper only ever said *where* it was. Plans stalled there: confirmed, budget
never sent, nobody aware it was theirs to send. ``next_action`` is the answer
the detail screen puts under the stepper, and these tests pin the reading at
each stage.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_treatment_plan import (
    _create_plan_with_items,
    _ensure_clinic_and_patient,
    _seed_catalog_crown,
)

BASE = "/api/v1/treatment_plan/treatment-plans"
BUDGETS = "/api/v1/budget/budgets"


# Local fixture over the shared helpers: importing the other module's fixture
# would need an alias, and pytest does not register a fixture under an alias.
@pytest.fixture
async def setup(db_session: AsyncSession, auth_headers: dict, client: AsyncClient) -> dict:
    ctx = await _ensure_clinic_and_patient(db_session, client, auth_headers)
    ctx["crown_id"] = await _seed_catalog_crown(db_session, ctx["clinic_id"])
    return ctx


async def _next_action(client: AsyncClient, auth_headers: dict, plan_id: str) -> dict | None:
    r = await client.get(f"{BASE}/{plan_id}", headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]["next_action"]


@pytest.mark.asyncio
async def test_empty_draft_asks_for_treatments(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    r = await client.post(
        BASE, headers=auth_headers, json={"patient_id": setup["patient_id"], "title": "Vacío"}
    )
    plan_id = r.json()["data"]["id"]

    assert (await _next_action(client, auth_headers, plan_id))["key"] == "add_treatments"


@pytest.mark.asyncio
async def test_draft_with_treatments_asks_to_confirm(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])

    assert (await _next_action(client, auth_headers, plan_id))["key"] == "confirm_plan"


@pytest.mark.asyncio
async def test_confirmed_plan_asks_to_send_the_budget(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """The step nothing used to name: confirming mints a *draft* budget."""
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    confirm = await client.post(f"{BASE}/{plan_id}/confirm", headers=auth_headers)
    assert confirm.status_code == 200, confirm.text

    action = await _next_action(client, auth_headers, plan_id)
    assert action["key"] == "send_budget"
    assert action["budget_status"] == "draft"


@pytest.mark.asyncio
async def test_sent_budget_puts_the_ball_with_the_patient(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    await client.post(f"{BASE}/{plan_id}/confirm", headers=auth_headers)
    plan = (await client.get(f"{BASE}/{plan_id}", headers=auth_headers)).json()["data"]

    sent = await client.post(
        f"{BUDGETS}/{plan['budget_id']}/send", headers=auth_headers, json={"send_email": False}
    )
    assert sent.status_code == 200, sent.text

    assert (await _next_action(client, auth_headers, plan_id))["key"] == "awaiting_patient"


@pytest.mark.asyncio
async def test_accepted_budget_asks_for_the_first_appointment(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """Accepting moves the plan on; the chair is then what is missing."""
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    await client.post(f"{BASE}/{plan_id}/confirm", headers=auth_headers)
    plan = (await client.get(f"{BASE}/{plan_id}", headers=auth_headers)).json()["data"]

    accepted = await client.post(
        f"{BUDGETS}/{plan['budget_id']}/accept",
        headers=auth_headers,
        json={"signature": {"signed_by_name": "Luis Soto"}},
    )
    assert accepted.status_code == 200, accepted.text

    action = await _next_action(client, auth_headers, plan_id)
    assert action["key"] == "schedule_first"
    assert action["next_appointment_at"] is None


@pytest.mark.asyncio
async def test_a_finished_plan_asks_for_nothing(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, item_ids = await _create_plan_with_items(client, auth_headers, setup, [16])
    await client.post(f"{BASE}/{plan_id}/confirm", headers=auth_headers)
    done = await client.patch(
        f"{BASE}/{plan_id}/items/{item_ids[0]}/complete", headers=auth_headers, json={}
    )
    assert done.status_code == 200, done.text

    plan = (await client.get(f"{BASE}/{plan_id}", headers=auth_headers)).json()["data"]
    assert plan["status"] == "completed"
    assert plan["next_action"] is None
