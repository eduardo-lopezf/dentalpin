"""Prescriptions written from a plan treatment.

What matters: the doctor block is frozen when the prescription is issued,
the prescription outlives the plan line it came from, and the PDF carries
the clinic, the doctor and the text.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.catalog.models import TreatmentCatalogItem, TreatmentCategory, VatType
from app.modules.professionals.models import Professional
from app.modules.treatment_plan.models import TreatmentPrescription
from app.modules.treatment_plan.prescriptions import _render_html

BASE = "/api/v1/treatment_plan"


@pytest.fixture
async def setup(db_session: AsyncSession, client: AsyncClient, auth_headers: dict) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]

    clinic = Clinic(
        id=uuid4(),
        name="Clínica Sonrisa",
        tax_id="SON010101AAA",
        address={"street": "Av. Reforma 10", "city": "CDMX", "postal_code": "06600"},
        phone="5555555555",
        settings={},
        account_tier="clinic",
    )
    db_session.add(clinic)
    await db_session.flush()
    db_session.add(
        ClinicMembership(id=uuid4(), user_id=user_id, clinic_id=clinic.id, role="dentist")
    )
    doctor = Professional(
        clinic_id=clinic.id, first_name="Laura", last_name="Méndez", license_number="1234567"
    )
    other_clinic = Clinic(id=uuid4(), name="Otra", tax_id="X", settings={}, account_tier="clinic")
    db_session.add_all([doctor, other_clinic])
    await db_session.flush()
    foreign_doctor = Professional(clinic_id=other_clinic.id, first_name="No", last_name="Mío")

    vat = VatType(clinic_id=clinic.id, names={"es": "Exento"}, rate=0.0, is_default=True)
    category = TreatmentCategory(clinic_id=clinic.id, key="c", names={"es": "C"}, is_system=True)
    db_session.add_all([vat, category, foreign_doctor])
    await db_session.flush()
    cleaning = TreatmentCatalogItem(
        clinic_id=clinic.id,
        category_id=category.id,
        internal_code="T-CLEAN",
        names={"es": "Limpieza"},
        default_price=Decimal("100.00"),
        pricing_strategy="flat",
        treatment_scope="global_mouth",
        vat_type_id=vat.id,
    )
    db_session.add(cleaning)
    await db_session.commit()

    patient = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "Ana", "last_name": "Ruiz", "date_of_birth": "1990-01-01"},
    )
    patient_id = patient.json()["data"]["id"]
    plan = await client.post(
        f"{BASE}/treatment-plans",
        headers=auth_headers,
        json={"patient_id": patient_id, "title": "Plan"},
    )
    plan_id = plan.json()["data"]["id"]
    added = await client.post(
        f"{BASE}/treatment-plans/{plan_id}/catalog-items",
        headers=auth_headers,
        json={"lines": [{"catalog_item_id": str(cleaning.id)}]},
    )
    assert added.status_code == 201, added.text
    item_id = added.json()["data"]["items"][0]["id"]
    return {
        "plan_id": plan_id,
        "item_id": item_id,
        "patient_id": patient_id,
        "doctor": doctor,
        "foreign_doctor_id": str(foreign_doctor.id),
    }


async def _issue(client, auth_headers, setup, **overrides):
    payload = {
        "body": "Ibuprofeno 400 mg\nUna tableta cada 8 horas por 3 días",
        "professional_id": str(setup["doctor"].id),
    } | overrides
    return await client.post(
        f"{BASE}/treatment-plans/{setup['plan_id']}/items/{setup['item_id']}/prescriptions",
        headers=auth_headers,
        json=payload,
    )


@pytest.mark.asyncio
async def test_issue_snapshots_the_doctor(client, auth_headers, setup, db_session):
    r = await _issue(client, auth_headers, setup)
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["professional_name"] == "Laura Méndez"
    assert data["professional_license"] == "1234567"
    assert data["treatment_label"] == "Limpieza"
    assert data["patient_id"] == setup["patient_id"]

    # Re-licensing the doctor later does not rewrite what was printed.
    doctor = setup["doctor"]
    doctor.license_number = "9999999"
    await db_session.commit()
    listed = await client.get(
        f"{BASE}/treatment-plans/{setup['plan_id']}/items/{setup['item_id']}/prescriptions",
        headers=auth_headers,
    )
    assert listed.status_code == 200
    assert [p["professional_license"] for p in listed.json()["data"]] == ["1234567"]


@pytest.mark.asyncio
async def test_doctor_from_another_clinic_is_refused(client, auth_headers, setup):
    r = await _issue(client, auth_headers, setup, professional_id=setup["foreign_doctor_id"])
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_unknown_item_is_404(client, auth_headers, setup):
    r = await client.post(
        f"{BASE}/treatment-plans/{setup['plan_id']}/items/{uuid4()}/prescriptions",
        headers=auth_headers,
        json={"body": "x", "professional_id": str(setup["doctor"].id)},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_empty_text_is_rejected(client, auth_headers, setup):
    r = await _issue(client, auth_headers, setup, body="")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_prescription_outlives_the_plan_line(client, auth_headers, setup, db_session):
    issued = await _issue(client, auth_headers, setup)
    prescription_id = issued.json()["data"]["id"]

    removed = await client.delete(
        f"{BASE}/treatment-plans/{setup['plan_id']}/items/{setup['item_id']}",
        headers=auth_headers,
    )
    assert removed.status_code == 204, removed.text

    db_session.expire_all()
    row = (
        await db_session.execute(
            select(TreatmentPrescription).where(TreatmentPrescription.id == prescription_id)
        )
    ).scalar_one()
    assert row.plan_item_id is None
    assert row.treatment_label == "Limpieza"


@pytest.mark.asyncio
async def test_pdf_is_served_inline(client, auth_headers, setup):
    issued = await _issue(client, auth_headers, setup)
    prescription_id = issued.json()["data"]["id"]

    r = await client.get(f"{BASE}/prescriptions/{prescription_id}/pdf", headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith("inline")
    assert r.content.startswith(b"%PDF")

    missing = await client.get(f"{BASE}/prescriptions/{uuid4()}/pdf", headers=auth_headers)
    assert missing.status_code == 404


def test_html_carries_clinic_doctor_patient_and_escaped_text() -> None:
    from datetime import UTC, date, datetime

    clinic = Clinic(
        name="Clínica Sonrisa",
        legal_name="Sonrisa SA de CV",
        tax_id="SON010101AAA",
        address={"street": "Av. Reforma 10", "city": "CDMX"},
        phone="5555555555",
        email="hola@sonrisa.mx",
        timezone="America/Mexico_City",
    )
    patient = type(
        "P", (), {"first_name": "Ana", "last_name": "Ruiz", "date_of_birth": date(1990, 6, 1)}
    )()
    prescription = TreatmentPrescription(
        professional_name="Laura Méndez",
        professional_license="1234567",
        treatment_label="Limpieza",
        body="Amoxicilina <500 mg>",
        created_at=datetime(2026, 5, 31, 12, tzinfo=UTC),
    )

    html = _render_html(prescription, clinic, patient, "es")

    for expected in (
        "Clínica Sonrisa",
        "Sonrisa SA de CV",
        "Av. Reforma 10, CDMX",
        "hola@sonrisa.mx",
        "Laura Méndez",
        "Cédula profesional: 1234567",
        "Ana Ruiz",
        "35 años",
        "31/05/2026",
        "Amoxicilina &lt;500 mg&gt;",
    ):
        assert expected in html, expected
    assert "<500 mg>" not in html
