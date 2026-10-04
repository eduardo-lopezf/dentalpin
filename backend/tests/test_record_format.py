"""How a clinic lays its record out: sections shown, their order, and the
points the coverage check reviews.

What these pin: the default is the paper order with everything checked; a
hidden section leaves the record and cannot be handed over, and nothing is
deleted by hiding it; the order applies; and only an admin configures.
"""

import pytest
from httpx import AsyncClient

from app.modules.patients.models import Patient

FORMAT = "/api/v1/record/format"


def _names(record: dict) -> list[str]:
    return [f"{s['module']}.{s['name']}" for s in record["sections"]]


async def _record(client: AsyncClient, headers: dict, patient: Patient) -> dict:
    response = await client.get(f"/api/v1/record/patients/{patient.id}", headers=headers)
    return response.json()["data"]


@pytest.mark.asyncio
async def test_the_default_is_every_section_and_every_point(
    client: AsyncClient, auth_headers: dict, test_patient: Patient
) -> None:
    fmt = (await client.get(FORMAT, headers=auth_headers)).json()["data"]
    assert fmt["hidden_sections"] == [] and fmt["section_order"] == []
    available = [s["qualified_name"] for s in fmt["available_sections"]]
    assert available[0] == "patients.identification"
    assert "informed_consent" in fmt["requirements"]

    record = await _record(client, auth_headers, test_patient)
    assert _names(record) == available
    assert [item["key"] for item in record["coverage"]] == fmt["requirements"]


@pytest.mark.asyncio
async def test_the_clinic_hides_reorders_and_skips(
    client: AsyncClient, auth_headers: dict, test_patient: Patient
) -> None:
    saved = await client.put(
        FORMAT,
        headers=auth_headers,
        json={
            "hidden_sections": ["periodontogram.chartings"],
            "section_order": ["consents.consents", "patients.identification"],
            "disabled_requirements": ["family_history", "prognosis"],
        },
    )
    assert saved.status_code == 200, saved.text

    record = await _record(client, auth_headers, test_patient)
    names = _names(record)
    assert names[:2] == ["consents.consents", "patients.identification"]
    assert "periodontogram.chartings" not in names
    # What the order does not mention keeps its default sequence.
    assert names.index("patients_clinical.allergies") < names.index("odontogram.chart")
    keys = {item["key"] for item in record["coverage"]}
    assert not keys & {"family_history", "prognosis"} and "diagnosis" in keys

    # A hidden section cannot be handed over either.
    refused = await client.post(
        f"/api/v1/record/patients/{test_patient.id}/disclosures",
        headers=auth_headers,
        json={
            "purpose": "continuity_of_care",
            "recipient_name": "Dra. Méndez",
            "evidence": "Referencia",
            "scope": ["patients.identification", "periodontogram.chartings"],
        },
    )
    assert refused.status_code == 400, refused.text

    # An empty format is the default again; hiding deleted nothing.
    await client.put(FORMAT, headers=auth_headers, json={})
    assert "periodontogram.chartings" in _names(await _record(client, auth_headers, test_patient))


@pytest.mark.asyncio
async def test_a_name_that_is_not_a_section_is_refused(
    client: AsyncClient, auth_headers: dict, test_patient: Patient
) -> None:
    refused = await client.put(
        FORMAT, headers=auth_headers, json={"hidden_sections": ["DROP TABLE patients;"]}
    )
    assert refused.status_code == 422, refused.text


def test_only_an_admin_lays_the_record_out() -> None:
    from app.core.auth.permissions import get_role_permissions
    from app.core.plugins.loader import discover_and_register

    discover_and_register()
    for role in ("dentist", "hygienist", "assistant", "receptionist"):
        assert "record.configure" not in get_role_permissions(role), role
