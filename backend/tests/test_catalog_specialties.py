"""Tests for assigning catalog treatments to dental specialties."""

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic


async def _create_specialty(client: AsyncClient, auth_headers: dict, name: str) -> str:
    response = await client.post(
        "/api/v1/catalog/specialties",
        json={"names": {"es": name, "en": name}},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


async def _create_item(client: AsyncClient, auth_headers: dict, code: str) -> str:
    category_response = await client.post(
        "/api/v1/catalog/categories",
        json={"key": f"cat_{code.lower()}", "names": {"es": code, "en": code}},
        headers=auth_headers,
    )
    assert category_response.status_code == 201

    response = await client.post(
        "/api/v1/catalog/items",
        json={
            "internal_code": code,
            "category_id": category_response.json()["data"]["id"],
            "names": {"es": code, "en": code},
            "default_price": "100.00",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


@pytest.mark.asyncio
async def test_assign_items_to_specialty(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    """Assigned treatments come back on the specialty and on the items."""
    specialty_id = await _create_specialty(client, auth_headers, "Endodoncia")
    item_id = await _create_item(client, auth_headers, "ENDO-01")

    response = await client.put(
        f"/api/v1/catalog/specialties/{specialty_id}/items",
        json={"item_ids": [item_id]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert [i["id"] for i in response.json()["data"]] == [item_id]

    listed = await client.get(
        f"/api/v1/catalog/specialties/{specialty_id}/items", headers=auth_headers
    )
    assert listed.status_code == 200
    assert [i["id"] for i in listed.json()["data"]] == [item_id]

    item = await client.get(f"/api/v1/catalog/items/{item_id}", headers=auth_headers)
    assert [s["id"] for s in item.json()["data"]["specialties"]] == [specialty_id]


@pytest.mark.asyncio
async def test_assignment_payload_is_authoritative(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    """Treatments missing from the payload lose the assignment."""
    specialty_id = await _create_specialty(client, auth_headers, "Cirugía")
    first_id = await _create_item(client, auth_headers, "CIR-01")
    second_id = await _create_item(client, auth_headers, "CIR-02")

    await client.put(
        f"/api/v1/catalog/specialties/{specialty_id}/items",
        json={"item_ids": [first_id, second_id]},
        headers=auth_headers,
    )
    response = await client.put(
        f"/api/v1/catalog/specialties/{specialty_id}/items",
        json={"item_ids": [second_id]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert [i["id"] for i in response.json()["data"]] == [second_id]

    dropped = await client.get(f"/api/v1/catalog/items/{first_id}", headers=auth_headers)
    assert dropped.json()["data"]["specialties"] == []


@pytest.mark.asyncio
async def test_item_can_belong_to_several_specialties(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    """A treatment may be performed under more than one discipline."""
    surgery_id = await _create_specialty(client, auth_headers, "Cirugía Oral")
    general_id = await _create_specialty(client, auth_headers, "Odontología General")
    item_id = await _create_item(client, auth_headers, "EXO-01")

    for specialty_id in (surgery_id, general_id):
        response = await client.put(
            f"/api/v1/catalog/specialties/{specialty_id}/items",
            json={"item_ids": [item_id]},
            headers=auth_headers,
        )
        assert response.status_code == 200

    item = await client.get(f"/api/v1/catalog/items/{item_id}", headers=auth_headers)
    assert {s["id"] for s in item.json()["data"]["specialties"]} == {surgery_id, general_id}


@pytest.mark.asyncio
async def test_assign_unknown_item_is_rejected(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    """Ids outside this clinic's live catalog cannot be linked."""
    specialty_id = await _create_specialty(client, auth_headers, "Ortodoncia")

    response = await client.put(
        f"/api/v1/catalog/specialties/{specialty_id}/items",
        json={"item_ids": [str(uuid4())]},
        headers=auth_headers,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_assign_items_to_unknown_specialty_returns_404(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    response = await client.put(
        f"/api/v1/catalog/specialties/{uuid4()}/items",
        json={"item_ids": []},
        headers=auth_headers,
    )
    assert response.status_code == 404


async def _make_system(db_session: AsyncSession, item_id: str) -> None:
    """Flip an item to `is_system`, as the seeder marks its own."""
    from app.modules.catalog.models import TreatmentCatalogItem

    item = await db_session.get(TreatmentCatalogItem, UUID(item_id))
    item.is_system = True
    await db_session.commit()


@pytest.mark.asyncio
async def test_system_treatment_is_editable_by_admin(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_clinic: Clinic
):
    """Seeded treatments must be editable: a clinic sets its own prices.

    They used to be rejected outright, which froze the entire shipped
    catalog — all 129 seeded items — for admins too.
    """
    item_id = await _create_item(client, auth_headers, "SYS-EDIT")
    await _make_system(db_session, item_id)

    response = await client.put(
        f"/api/v1/catalog/items/{item_id}",
        json={"default_price": "250.00", "is_active": False},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["default_price"] == "250.00"
    # Deactivating a seeded treatment the clinic does not offer is an update
    # too — it was blocked by the same guard.
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_system_treatment_keeps_its_internal_code(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_clinic: Clinic
):
    """The seeder matches on `internal_code`; renaming it would duplicate."""
    item_id = await _create_item(client, auth_headers, "SYS-CODE")
    await _make_system(db_session, item_id)

    response = await client.put(
        f"/api/v1/catalog/items/{item_id}",
        json={"internal_code": "RENAMED"},
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_treatments_default_to_visible(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    """New treatments are listed until someone hides them.

    Defaulting to hidden would empty the clinical /treatments page on
    upgrade and force an admin through 129 checkboxes before it works.
    """
    item_id = await _create_item(client, auth_headers, "VIS-DEFAULT")

    response = await client.get(f"/api/v1/catalog/items/{item_id}", headers=auth_headers)
    assert response.json()["data"]["is_visible"] is True


@pytest.mark.asyncio
async def test_visibility_is_independent_of_active(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    """Hiding a treatment must not stop it being offered.

    `is_visible` only curates the clinical list; the treatment stays active
    so budgets, the odontogram and past invoices keep working.
    """
    item_id = await _create_item(client, auth_headers, "VIS-TOGGLE")

    response = await client.put(
        f"/api/v1/catalog/items/{item_id}",
        json={"is_visible": False},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["is_visible"] is False
    assert data["is_active"] is True

    restored = await client.put(
        f"/api/v1/catalog/items/{item_id}",
        json={"is_visible": True},
        headers=auth_headers,
    )
    assert restored.json()["data"]["is_visible"] is True
