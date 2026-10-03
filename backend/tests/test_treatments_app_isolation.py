"""The Treatments App does not need Budgets or Payments.

A plan never calls into either (ADR 0042): it announces what happened to
it and ``budget`` reacts; it asks questions through read-only contracts.
With those Apps off a plan is confirmed, worked and deleted all the
same, and when Budgets returns the plan can be priced then.

What the App may import and require is pinned for every App at once in
``test_app_isolation.py``; this file holds how it behaves.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus
from app.core.plugins.registry import module_registry
from tests.test_treatment_plan import (
    _create_plan_with_items,
    _ensure_clinic_and_patient,
    _seed_catalog_crown,
)

PLANS = "/api/v1/treatment_plan/treatment-plans"


@pytest.fixture
async def setup(db_session: AsyncSession, auth_headers: dict, client: AsyncClient) -> dict:
    ctx = await _ensure_clinic_and_patient(db_session, client, auth_headers)
    ctx["crown_id"] = await _seed_catalog_crown(db_session, ctx["clinic_id"])
    return ctx


@pytest.fixture
def budgets_and_payments_off():
    """What ``apps.json`` does to an App that is off: its modules are not
    mounted, so they supply no contract and hear no event."""
    names = ("budget", "payments")
    saved = {event: list(handlers) for event, handlers in event_bus._handlers.items()}
    event_bus._handlers = {
        event: [
            h
            for h in handlers
            if not getattr(h, "__module__", "").startswith(
                tuple(f"app.modules.{name}" for name in names)
            )
        ]
        for event, handlers in saved.items()
    }
    for name in names:
        module_registry.deactivate(name)
    yield
    for name in names:
        module_registry.activate(name)
    event_bus._handlers = saved


async def _plan(client: AsyncClient, headers: dict, plan_id: str) -> dict:
    r = await client.get(f"{PLANS}/{plan_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.asyncio
async def test_a_plan_is_confirmed_and_deleted_without_budgets(
    client: AsyncClient, auth_headers: dict, setup: dict, budgets_and_payments_off
) -> None:
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])

    r = await client.post(f"{PLANS}/{plan_id}/confirm", headers=auth_headers)
    assert r.status_code == 200, r.text

    plan = await _plan(client, auth_headers, plan_id)
    # Nobody will accept a budget, so the plan does not wait for one.
    assert plan["status"] == "active"
    assert plan["budget_id"] is None and plan["budget"] is None
    assert plan["unbudgeted_count"] == 0
    assert plan["next_action"]["key"] not in ("generate_budget", "send_budget")

    # Not locked by a budget: its treatments can still be changed.
    r = await client.post(f"{PLANS}/{plan_id}/reopen", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert (await _plan(client, auth_headers, plan_id))["status"] == "draft"

    # No ledger to ask: the plan may go.
    r = await client.delete(f"{PLANS}/{plan_id}", headers=auth_headers)
    assert r.status_code == 204, r.text


@pytest.mark.asyncio
async def test_a_plan_confirmed_without_budgets_is_priced_when_they_return(
    client: AsyncClient, auth_headers: dict, setup: dict, db_session: AsyncSession
) -> None:
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])

    # Confirmed while Budgets is off…
    saved = {event: list(handlers) for event, handlers in event_bus._handlers.items()}
    event_bus._handlers = {
        event: [h for h in hs if not getattr(h, "__module__", "").startswith("app.modules.budget")]
        for event, hs in saved.items()
    }
    module_registry.deactivate("budget")
    try:
        r = await client.post(f"{PLANS}/{plan_id}/confirm", headers=auth_headers)
        assert r.status_code == 200, r.text
        refused = await client.post(
            f"/api/v1/treatment_plan/treatment-plans/{plan_id}/link-budget",
            headers=auth_headers,
            json={"budget_id": plan_id},
        )
        assert refused.status_code == 400 and "not available" in refused.text
    finally:
        module_registry.activate("budget")
        event_bus._handlers = saved

    # …and back on: the plan says it wants a budget, and gets one on request.
    plan = await _plan(client, auth_headers, plan_id)
    assert plan["status"] == "active" and plan["budget_id"] is None
    assert plan["next_action"]["key"] == "generate_budget"

    made = await client.post(f"/api/v1/budget/plans/{plan_id}/budget", headers=auth_headers)
    assert made.status_code == 201, made.text

    plan = await _plan(client, auth_headers, plan_id)
    assert plan["budget_id"] == made.json()["data"]["budget_id"]
    assert plan["budget"]["status"] == "draft"

    # Asking twice does not mint a second one.
    again = await client.post(f"/api/v1/budget/plans/{plan_id}/budget", headers=auth_headers)
    assert again.status_code == 400, again.text


@pytest.mark.asyncio
async def test_confirming_mints_the_budget_through_the_event(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """With Budgets on, the plan ends up linked without having called it."""
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    r = await client.post(f"{PLANS}/{plan_id}/confirm", headers=auth_headers)
    assert r.status_code == 200, r.text

    plan = await _plan(client, auth_headers, plan_id)
    assert plan["status"] == "pending"
    assert plan["budget"]["status"] == "draft"

    history = await client.get(f"{PLANS}/{plan_id}/history", headers=auth_headers)
    actions = [e["action"] for e in history.json()["data"]["entries"]]
    assert "confirmed" in actions and "budget_created" in actions


@pytest.mark.asyncio
async def test_a_plan_is_worked_without_the_professionals_app(
    client: AsyncClient, auth_headers: dict, setup: dict, db_session: AsyncSession
) -> None:
    """The directory is an integration (ADR 0037): with it off a plan is
    created and confirmed with nobody assigned, and assigning is refused."""
    from uuid import uuid4

    from app.modules.professionals.models import Professional

    dentist = Professional(
        id=uuid4(),
        clinic_id=setup["clinic_id"],
        first_name="Dra",
        last_name="Soto",
        professional_type="dentist",
        is_active=True,
    )
    db_session.add(dentist)
    await db_session.commit()
    assigned = {
        "patient_id": setup["patient_id"],
        "title": "Con profesional",
        "assigned_professional_id": str(dentist.id),
    }

    module_registry.deactivate("professionals")
    try:
        refused = await client.post(PLANS, headers=auth_headers, json=assigned)
        plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
        confirmed = await client.post(f"{PLANS}/{plan_id}/confirm", headers=auth_headers)
    finally:
        module_registry.activate("professionals")

    assert refused.status_code == 400, refused.text
    assert "not available" in refused.text
    assert confirmed.status_code == 200, confirmed.text
    assert (await _plan(client, auth_headers, plan_id))["assigned_professional_id"] is None

    # Back on: the same assignment goes through.
    again = await client.post(PLANS, headers=auth_headers, json=assigned)
    assert again.status_code == 201, again.text
    assert again.json()["data"]["assigned_professional_id"] == str(dentist.id)
