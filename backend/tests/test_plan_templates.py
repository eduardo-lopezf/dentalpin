"""Plan templates: the shape of a plan, applied to a patient.

The interesting behaviour is the apply rule, because it is the one thing a
dentist has to be able to predict: every per-tooth treatment is created once
per tooth supplied, and everything whole-mouth is created once.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.catalog.models import (
    TreatmentCatalogItem,
    TreatmentCategory,
    TreatmentOdontogramMapping,
    VatType,
)

BASE = "/api/v1/treatment_plan"


async def _clinic_and_patient(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict[str, str]
) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]

    clinic = Clinic(
        id=uuid4(),
        name="Template Clinic",
        tax_id="B22222222",
        address={"street": "a", "city": "b"},
        settings={"slot_duration_min": 15},
        account_tier="clinic",
    )
    db_session.add(clinic)
    await db_session.flush()
    db_session.add(
        ClinicMembership(id=uuid4(), user_id=user_id, clinic_id=clinic.id, role="dentist")
    )
    await db_session.commit()

    patient = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "Ana", "last_name": "Ruiz", "phone": "+34666111222"},
    )
    return {
        "clinic_id": clinic.id,
        "user_id": user_id,
        "patient_id": patient.json()["data"]["id"],
    }


async def _catalog(db_session: AsyncSession, clinic_id) -> dict[str, str]:
    """A per-tooth item with a chart mapping, and two without one.

    The unmapped pair is the realistic case, not an edge case: over half a
    seeded dental catalog (cleanings, radiographs, dentures) draws nothing on
    a tooth chart.
    """
    vat = VatType(clinic_id=clinic_id, names={"es": "Exento"}, rate=0.0, is_default=True)
    db_session.add(vat)
    await db_session.flush()
    category = TreatmentCategory(clinic_id=clinic_id, key="mix", names={"es": "M"}, is_system=True)
    db_session.add(category)
    await db_session.flush()

    def item(code: str, scope: str, phase: str) -> TreatmentCatalogItem:
        return TreatmentCatalogItem(
            clinic_id=clinic_id,
            category_id=category.id,
            internal_code=code,
            names={"es": code},
            default_price=Decimal("100.00"),
            pricing_strategy="flat",
            treatment_scope=scope,
            default_phase=phase,
            vat_type_id=vat.id,
        )

    crown = item("T-CROWN", "tooth", "rehabilitacion")
    cleaning = item("T-CLEAN", "global_mouth", "preventivo")
    retainer = item("T-RETAINER", "global_arch", "mantenimiento")
    db_session.add_all([crown, cleaning, retainer])
    await db_session.flush()

    db_session.add(
        TreatmentOdontogramMapping(
            clinic_id=clinic_id,
            catalog_item_id=crown.id,
            odontogram_treatment_type="crown",
            clinical_category="restauradora",
            visualization_rules=[],
            visualization_config={},
        )
    )
    await db_session.commit()
    return {
        "crown": str(crown.id),
        "cleaning": str(cleaning.id),
        "retainer": str(retainer.id),
    }


@pytest.fixture
async def setup(
    db_session: AsyncSession, auth_headers: dict[str, str], client: AsyncClient
) -> dict:
    ctx = await _clinic_and_patient(db_session, client, auth_headers)
    ctx["catalog"] = await _catalog(db_session, ctx["clinic_id"])
    return ctx


async def _plan(client: AsyncClient, auth_headers: dict, setup: dict) -> str:
    r = await client.post(
        f"{BASE}/treatment-plans",
        headers=auth_headers,
        json={"patient_id": setup["patient_id"], "title": "Plan"},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


async def _template(client: AsyncClient, auth_headers: dict, items: list[dict]) -> str:
    r = await client.post(
        f"{BASE}/plan-templates",
        headers=auth_headers,
        json={"name": "Shape", "items": items},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


@pytest.mark.asyncio
async def test_whole_mouth_template_needs_no_teeth(client, auth_headers, setup):
    plan_id = await _plan(client, auth_headers, setup)
    template_id = await _template(
        client, auth_headers, [{"catalog_item_id": setup["catalog"]["cleaning"]}]
    )

    r = await client.post(
        f"{BASE}/treatment-plans/{plan_id}/apply-template",
        headers=auth_headers,
        json={"template_id": template_id, "tooth_numbers": []},
    )
    assert r.status_code == 201, r.text
    items = r.json()["data"]
    assert len(items) == 1
    assert items[0]["treatment"]["scope"] == "global_mouth"
    # Seeded from the catalog item's default_phase.
    assert items[0]["phase"] == "preventivo"


@pytest.mark.asyncio
async def test_per_tooth_template_creates_one_item_per_tooth(client, auth_headers, setup):
    plan_id = await _plan(client, auth_headers, setup)
    template_id = await _template(
        client, auth_headers, [{"catalog_item_id": setup["catalog"]["crown"]}]
    )

    r = await client.post(
        f"{BASE}/treatment-plans/{plan_id}/apply-template",
        headers=auth_headers,
        json={"template_id": template_id, "tooth_numbers": [16, 26, 36]},
    )
    assert r.status_code == 201, r.text
    items = r.json()["data"]
    assert len(items) == 3
    teeth = sorted(i["treatment"]["teeth"][0]["tooth_number"] for i in items)
    assert teeth == [16, 26, 36]


@pytest.mark.asyncio
async def test_per_tooth_template_without_teeth_says_which_treatments(client, auth_headers, setup):
    plan_id = await _plan(client, auth_headers, setup)
    template_id = await _template(
        client, auth_headers, [{"catalog_item_id": setup["catalog"]["crown"]}]
    )

    r = await client.post(
        f"{BASE}/treatment-plans/{plan_id}/apply-template",
        headers=auth_headers,
        json={"template_id": template_id, "tooth_numbers": []},
    )
    assert r.status_code == 422
    # The blocked treatment is named, so the UI can ask for the right thing
    # instead of showing a bare validation error.
    assert "T-CROWN" in r.text


@pytest.mark.asyncio
async def test_arch_item_expands_to_both_arches_when_no_teeth(client, auth_headers, setup):
    plan_id = await _plan(client, auth_headers, setup)
    template_id = await _template(
        client, auth_headers, [{"catalog_item_id": setup["catalog"]["retainer"]}]
    )

    r = await client.post(
        f"{BASE}/treatment-plans/{plan_id}/apply-template",
        headers=auth_headers,
        json={"template_id": template_id, "tooth_numbers": []},
    )
    assert r.status_code == 201, r.text
    arches = sorted(i["treatment"]["arch"] for i in r.json()["data"])
    assert arches == ["lower", "upper"]


@pytest.mark.asyncio
async def test_unmapped_catalog_item_is_plannable(client, auth_headers, setup):
    """A cleaning has no chart mapping and must still reach a plan.

    Requiring one made over half a real catalog impossible to plan at all.
    """
    plan_id = await _plan(client, auth_headers, setup)
    template_id = await _template(
        client, auth_headers, [{"catalog_item_id": setup["catalog"]["cleaning"]}]
    )

    r = await client.post(
        f"{BASE}/treatment-plans/{plan_id}/apply-template",
        headers=auth_headers,
        json={"template_id": template_id, "tooth_numbers": []},
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"][0]["treatment"]["clinical_type"] == "procedure"


@pytest.mark.asyncio
async def test_template_phase_overrides_the_catalog_default(client, auth_headers, setup):
    plan_id = await _plan(client, auth_headers, setup)
    template_id = await _template(
        client,
        auth_headers,
        [{"catalog_item_id": setup["catalog"]["crown"], "phase": "urgencia"}],
    )

    r = await client.post(
        f"{BASE}/treatment-plans/{plan_id}/apply-template",
        headers=auth_headers,
        json={"template_id": template_id, "tooth_numbers": [16]},
    )
    assert r.status_code == 201, r.text
    # The catalog says rehabilitacion; this template says otherwise.
    assert r.json()["data"][0]["phase"] == "urgencia"


@pytest.mark.asyncio
async def test_save_plan_as_template_drops_teeth(client, auth_headers, setup):
    plan_id = await _plan(client, auth_headers, setup)
    source = await _template(client, auth_headers, [{"catalog_item_id": setup["catalog"]["crown"]}])
    await client.post(
        f"{BASE}/treatment-plans/{plan_id}/apply-template",
        headers=auth_headers,
        json={"template_id": source, "tooth_numbers": [16, 26]},
    )

    r = await client.post(
        f"{BASE}/plan-templates/from-plan/{plan_id}",
        headers=auth_headers,
        json={"name": "Saved shape"},
    )
    assert r.status_code == 201, r.text
    saved = r.json()["data"]
    # Two plan items on two teeth collapse to one template line: a template
    # carries the treatment, never the teeth.
    assert len(saved["items"]) == 1
    assert saved["items"][0]["catalog_item_id"] == setup["catalog"]["crown"]
    assert saved["key"] is None


@pytest.mark.asyncio
async def test_template_rejects_a_catalog_item_from_another_clinic(client, auth_headers, setup):
    r = await client.post(
        f"{BASE}/plan-templates",
        headers=auth_headers,
        json={"name": "Cross tenant", "items": [{"catalog_item_id": str(uuid4())}]},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_delete_hides_the_template_without_dropping_it(client, auth_headers, setup):
    template_id = await _template(
        client, auth_headers, [{"catalog_item_id": setup["catalog"]["cleaning"]}]
    )

    assert (
        await client.delete(f"{BASE}/plan-templates/{template_id}", headers=auth_headers)
    ).status_code == 204

    listed = await client.get(f"{BASE}/plan-templates", headers=auth_headers)
    assert all(t["id"] != template_id for t in listed.json()["data"])

    with_inactive = await client.get(
        f"{BASE}/plan-templates?include_inactive=true", headers=auth_headers
    )
    assert any(t["id"] == template_id for t in with_inactive.json()["data"])


# ---------------------------------------------------------------------------
# Proposals from the chart
# ---------------------------------------------------------------------------


async def _finding(
    client: AsyncClient, auth_headers: dict, setup: dict, clinical_type: str, tooth: int
) -> str:
    """Chart a finding the way diagnosis mode does: performed, no catalog link."""
    r = await client.post(
        f"/api/v1/odontogram/patients/{setup['patient_id']}/treatments",
        headers=auth_headers,
        json={
            "clinical_type": clinical_type,
            "tooth_numbers": [tooth],
            "status": "performed",
            "scope": "tooth",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


@pytest.mark.asyncio
async def test_findings_are_proposed_with_a_suggested_treatment(
    client, auth_headers, setup, db_session
):
    # The suggestion table resolves by internal_code, so the codes have to be
    # in this clinic's catalog for anything to be proposed.
    vat = (
        (await db_session.execute(select(VatType).where(VatType.clinic_id == setup["clinic_id"])))
        .scalars()
        .first()
    )
    category = (
        (
            await db_session.execute(
                select(TreatmentCategory).where(TreatmentCategory.clinic_id == setup["clinic_id"])
            )
        )
        .scalars()
        .first()
    )
    db_session.add(
        TreatmentCatalogItem(
            clinic_id=setup["clinic_id"],
            category_id=category.id,
            internal_code="REST-COMP",
            names={"es": "Obturación composite"},
            default_price=Decimal("60.00"),
            pricing_strategy="flat",
            treatment_scope="tooth",
            default_phase="estabilizacion",
            vat_type_id=vat.id,
        )
    )
    await db_session.commit()

    plan_id = await _plan(client, auth_headers, setup)
    await _finding(client, auth_headers, setup, "caries", 16)

    r = await client.get(f"{BASE}/treatment-plans/{plan_id}/proposals", headers=auth_headers)
    assert r.status_code == 200, r.text
    proposals = r.json()["data"]
    assert len(proposals) == 1
    assert proposals[0]["clinical_type"] == "caries"
    assert proposals[0]["tooth_number"] == 16
    assert proposals[0]["suggested_catalog_item"]["internal_code"] == "REST-COMP"

    accepted = await client.post(
        f"{BASE}/treatment-plans/{plan_id}/proposals",
        headers=auth_headers,
        json={"finding_ids": [proposals[0]["finding_id"]]},
    )
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["data"][0]["treatment"]["teeth"][0]["tooth_number"] == 16

    # The tooth now has planned work, so the finding stops being proposed —
    # and the finding itself is untouched, because the caries is still there.
    again = await client.get(f"{BASE}/treatment-plans/{plan_id}/proposals", headers=auth_headers)
    assert again.json()["data"] == []


@pytest.mark.asyncio
async def test_finding_without_a_catalog_match_is_listed_but_not_actionable(
    client, auth_headers, setup
):
    """The clinic has no REST-COMP, so nothing can be proposed for a caries.

    It is still listed: a dentist wants to know the finding is unaddressed
    even when the app has nothing to offer for it.
    """
    plan_id = await _plan(client, auth_headers, setup)
    await _finding(client, auth_headers, setup, "caries", 16)

    r = await client.get(f"{BASE}/treatment-plans/{plan_id}/proposals", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert len(r.json()["data"]) == 1
    assert r.json()["data"][0]["suggested_catalog_item"] is None


@pytest.mark.asyncio
async def test_planned_work_is_not_a_finding(client, auth_headers, setup):
    """A crown already planned on 16 is not a finding and must not be proposed."""
    plan_id = await _plan(client, auth_headers, setup)
    template_id = await _template(
        client, auth_headers, [{"catalog_item_id": setup["catalog"]["crown"]}]
    )
    await client.post(
        f"{BASE}/treatment-plans/{plan_id}/apply-template",
        headers=auth_headers,
        json={"template_id": template_id, "tooth_numbers": [16]},
    )

    r = await client.get(f"{BASE}/treatment-plans/{plan_id}/proposals", headers=auth_headers)
    assert r.json()["data"] == []
