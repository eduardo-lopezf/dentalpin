"""The home page layout: which widgets show, in what order (ADR 0043)."""

import pytest
from httpx import AsyncClient

URL = "/api/v1/auth/clinic/settings/home"


@pytest.mark.asyncio
async def test_a_clinic_starts_with_every_widget_in_its_place(
    client: AsyncClient, auth_headers: dict, test_clinic
) -> None:
    response = await client.get(URL, headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["data"] == {"hidden": [], "order": []}


@pytest.mark.asyncio
async def test_the_layout_is_saved_and_read_back(
    client: AsyncClient, auth_headers: dict, test_clinic
) -> None:
    layout = {
        "hidden": ["reports.dashboard.weekGlance"],
        "order": ["agenda.dashboard.inClinicNow", "agenda.dashboard.todayAppointments"],
    }
    saved = await client.put(URL, json=layout, headers=auth_headers)
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"] == layout

    read = await client.get(URL, headers=auth_headers)
    assert read.json()["data"] == layout


@pytest.mark.asyncio
async def test_duplicates_are_dropped_and_other_settings_survive(
    client: AsyncClient, auth_headers: dict, test_clinic, db_session
) -> None:
    test_clinic.settings = {**(test_clinic.settings or {}), "slot_duration_min": 20}
    await db_session.commit()

    saved = await client.put(
        URL,
        json={"hidden": [], "order": ["agenda.dashboard.unconfirmed"] * 2},
        headers=auth_headers,
    )
    assert saved.json()["data"]["order"] == ["agenda.dashboard.unconfirmed"]

    await db_session.refresh(test_clinic)
    assert test_clinic.settings["slot_duration_min"] == 20


@pytest.mark.asyncio
async def test_a_malformed_widget_id_is_refused(
    client: AsyncClient, auth_headers: dict, test_clinic
) -> None:
    refused = await client.put(
        URL, json={"hidden": ["not a widget"], "order": []}, headers=auth_headers
    )
    assert refused.status_code == 422


@pytest.mark.asyncio
async def test_only_an_admin_changes_it_but_everyone_reads_it(
    client: AsyncClient, auth_headers: dict, test_clinic, db_session
) -> None:
    from sqlalchemy import update

    from app.core.auth.models import ClinicMembership

    await db_session.execute(
        update(ClinicMembership)
        .where(ClinicMembership.clinic_id == test_clinic.id)
        .values(role="hygienist")
    )
    await db_session.commit()

    assert (await client.get(URL, headers=auth_headers)).status_code == 200
    refused = await client.put(URL, json={"hidden": [], "order": []}, headers=auth_headers)
    assert refused.status_code == 403
