"""A plan's budget is deleted with the plan, and only then.

The budget list used to offer a trash can on every row, accepted budgets
included, and the endpoint behind it deleted a plan's budget out from under
the plan. Now `DELETE /budgets/{id}` refuses a budget a plan owns, and
deleting the plan takes every budget it produced with it.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_treatment_plan import (
    _create_plan_with_items,
    _ensure_clinic_and_patient,
    _seed_catalog_crown,
)

PLANS = "/api/v1/treatment_plan/treatment-plans"
BUDGETS = "/api/v1/budget/budgets"


@pytest.fixture
async def setup(db_session: AsyncSession, auth_headers: dict, client: AsyncClient) -> dict:
    ctx = await _ensure_clinic_and_patient(db_session, client, auth_headers)
    ctx["crown_id"] = await _seed_catalog_crown(db_session, ctx["clinic_id"])
    return ctx


async def _confirmed_plan(client: AsyncClient, auth_headers: dict, setup: dict) -> tuple[str, str]:
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    r = await client.post(f"{PLANS}/{plan_id}/confirm", headers=auth_headers)
    assert r.status_code == 200, r.text
    budget_id = r.json()["data"]["budget_id"]
    assert budget_id
    return plan_id, budget_id


@pytest.mark.asyncio
async def test_a_plans_budget_cannot_be_deleted_on_its_own(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, budget_id = await _confirmed_plan(client, auth_headers, setup)

    r = await client.delete(f"{BUDGETS}/{budget_id}", headers=auth_headers)
    assert r.status_code == 409, r.text

    # Refused means refused: the budget is still there and still linked.
    r = await client.get(f"{BUDGETS}/{budget_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["data"]["treatment_plan"]["id"] == plan_id


@pytest.mark.asyncio
async def test_deleting_the_plan_deletes_its_budget(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, budget_id = await _confirmed_plan(client, auth_headers, setup)

    r = await client.delete(f"{PLANS}/{plan_id}", headers=auth_headers)
    assert r.status_code == 204, r.text

    r = await client.get(f"{BUDGETS}/{budget_id}", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_deleting_the_plan_takes_every_budget_it_produced(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """Reopen + confirm leaves a cancelled budget beside the fresh one."""
    plan_id, first_budget = await _confirmed_plan(client, auth_headers, setup)
    r = await client.post(f"{PLANS}/{plan_id}/reopen", headers=auth_headers)
    assert r.status_code == 200, r.text
    r = await client.post(f"{PLANS}/{plan_id}/confirm", headers=auth_headers)
    second_budget = r.json()["data"]["budget_id"]
    assert second_budget != first_budget

    r = await client.delete(f"{PLANS}/{plan_id}", headers=auth_headers)
    assert r.status_code == 204, r.text

    for budget_id in (first_budget, second_budget):
        r = await client.get(f"{BUDGETS}/{budget_id}", headers=auth_headers)
        assert r.status_code == 404, budget_id


@pytest.mark.asyncio
async def test_deleting_a_plan_leaves_other_plans_budgets_alone(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_a, _ = await _confirmed_plan(client, auth_headers, setup)
    _, budget_b = await _confirmed_plan(client, auth_headers, setup)

    r = await client.delete(f"{PLANS}/{plan_a}", headers=auth_headers)
    assert r.status_code == 204, r.text

    r = await client.get(f"{BUDGETS}/{budget_b}", headers=auth_headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_a_plan_without_budget_still_deletes(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])

    r = await client.delete(f"{PLANS}/{plan_id}", headers=auth_headers)
    assert r.status_code == 204, r.text
