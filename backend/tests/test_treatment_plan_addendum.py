"""Work added to a plan the patient already signed.

Finding a second caries halfway through a plan is ordinary, and the old
answer was extraordinary: cancel the signed budget, rebuild the plan, make
the patient accept everything again. Adding is now allowed on a plan in
progress — it changes none of the lines the patient agreed to — and the new
work is priced by an **addendum**, a second draft beside the signed one.

Changing or removing an existing line is the opposite and still refuses.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_treatment_plan import (
    _create_plan_with_items,
    _create_treatment,
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


async def _detail(client: AsyncClient, auth_headers: dict, plan_id: str) -> dict:
    r = await client.get(f"{BASE}/{plan_id}", headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _add_treatment(
    client: AsyncClient, auth_headers: dict, setup: dict, plan_id: str, tooth: int
):
    treatment_id = await _create_treatment(client, auth_headers, setup, tooth_number=tooth)
    return await client.post(
        f"{BASE}/{plan_id}/items", headers=auth_headers, json={"treatment_id": treatment_id}
    )


async def _signed_plan(client: AsyncClient, auth_headers: dict, setup: dict) -> tuple[str, str]:
    """A plan in progress whose budget the patient has accepted."""
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    confirm = await client.post(f"{BASE}/{plan_id}/confirm", headers=auth_headers)
    assert confirm.status_code == 200, confirm.text

    budget_id = (await _detail(client, auth_headers, plan_id))["budget_id"]
    accepted = await client.post(
        f"{BUDGETS}/{budget_id}/accept",
        headers=auth_headers,
        json={"signature": {"signed_by_name": "Luis Soto"}},
    )
    assert accepted.status_code == 200, accepted.text
    return plan_id, budget_id


@pytest.mark.asyncio
async def test_a_signed_plan_accepts_a_new_treatment(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """The whole point: no reopening, and the signed figure does not move."""
    plan_id, budget_id = await _signed_plan(client, auth_headers, setup)
    before = (await client.get(f"{BUDGETS}/{budget_id}", headers=auth_headers)).json()["data"]

    added = await _add_treatment(client, auth_headers, setup, plan_id, tooth=26)
    assert added.status_code == 201, added.text

    plan = await _detail(client, auth_headers, plan_id)
    assert plan["status"] == "active"
    assert plan["budget"]["status"] == "accepted"

    after = (await client.get(f"{BUDGETS}/{budget_id}", headers=auth_headers)).json()["data"]
    assert after["total"] == before["total"], "the signed budget must not move"


@pytest.mark.asyncio
async def test_the_plan_says_the_new_work_has_no_price(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, _ = await _signed_plan(client, auth_headers, setup)
    await _add_treatment(client, auth_headers, setup, plan_id, tooth=26)

    plan = await _detail(client, auth_headers, plan_id)
    assert plan["unbudgeted_count"] == 1
    assert plan["next_action"]["key"] == "budget_addendum"
    assert plan["next_action"]["unbudgeted_count"] == 1


@pytest.mark.asyncio
async def test_the_addendum_is_a_second_draft_holding_only_the_new_work(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, budget_id = await _signed_plan(client, auth_headers, setup)
    await _add_treatment(client, auth_headers, setup, plan_id, tooth=26)

    made = await client.post(f"{BASE}/{plan_id}/budget-addendum", headers=auth_headers)
    assert made.status_code == 201, made.text
    result = made.json()["data"]
    assert result["created"] is True
    assert result["item_count"] == 1
    assert result["budget_id"] != budget_id

    addendum = (await client.get(f"{BUDGETS}/{result['budget_id']}", headers=auth_headers)).json()[
        "data"
    ]
    assert addendum["status"] == "draft"
    assert len(addendum["items"]) == 1

    plan = await _detail(client, auth_headers, plan_id)
    assert plan["unbudgeted_count"] == 0
    # The plan still points at what it was agreed on; the addendum is beside it.
    assert plan["budget_id"] == budget_id
    assert [b["id"] for b in plan["other_budgets"]] == [result["budget_id"]]


@pytest.mark.asyncio
async def test_an_addendum_with_nothing_to_price_is_refused(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, _ = await _signed_plan(client, auth_headers, setup)

    refused = await client.post(f"{BASE}/{plan_id}/budget-addendum", headers=auth_headers)
    assert refused.status_code == 400, refused.text


@pytest.mark.asyncio
async def test_editing_and_removing_still_refuse(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """Adding is safe; touching an agreed line is the contract moving."""
    plan_id, _ = await _signed_plan(client, auth_headers, setup)
    item_id = (await _detail(client, auth_headers, plan_id))["items"][0]["id"]

    removed = await client.delete(f"{BASE}/{plan_id}/items/{item_id}", headers=auth_headers)
    assert removed.status_code == 409, removed.text

    edited = await client.put(
        f"{BASE}/{plan_id}/items/{item_id}", headers=auth_headers, json={"notes": "nope"}
    )
    assert edited.status_code == 409, edited.text


@pytest.mark.asyncio
async def test_while_the_budget_is_a_draft_nothing_goes_unpriced(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """`budget` mirrors additions into a draft itself, so no addendum is due."""
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    await client.post(f"{BASE}/{plan_id}/confirm", headers=auth_headers)

    await _add_treatment(client, auth_headers, setup, plan_id, tooth=26)

    plan = await _detail(client, auth_headers, plan_id)
    assert plan["budget"]["status"] == "draft"
    assert plan["unbudgeted_count"] == 0
    assert plan["next_action"]["key"] == "send_budget"
