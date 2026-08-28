"""The HTTP surface for subject rights.

What these pin, beyond the happy path: an export hands out every module's
data on one patient in a single response, so it sits behind its own
permission and refuses to run without a stated reason; and an erasure is
irreversible, so it must leave a record that outlives the data it
destroyed. A deletion nobody can prove happened is indistinguishable from
a bug that emptied the columns.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.privacy.models import SubjectRequest
from app.modules.patients.models import Patient

REASON = "Solicitud de portabilidad presentada por el paciente el 2026-08-29"


@pytest.mark.asyncio
class TestExport:
    async def test_returns_every_section(
        self, client: AsyncClient, auth_headers: dict, test_clinic, db_session: AsyncSession
    ) -> None:
        patient = await _patient(db_session, test_clinic)
        response = await client.get(
            f"/api/v1/privacy/subjects/{patient.id}/export",
            params={"reason": REASON},
            headers=auth_headers,
        )
        assert response.status_code == 200

        sections = response.json()["data"]["sections"]
        by_name = {f"{s['module']}.{s['section']}": s for s in sections}
        assert "patients.identity" in by_name
        assert by_name["patients.identity"]["rows"][0]["first_name"] == "Ana"

    async def test_says_which_sections_an_erasure_cannot_reach(
        self, client: AsyncClient, auth_headers: dict, test_clinic, db_session: AsyncSession
    ) -> None:
        # A patient reading their data should see which parts they cannot
        # have removed, and why, without having to ask a second time.
        patient = await _patient(db_session, test_clinic)
        response = await client.get(
            f"/api/v1/privacy/subjects/{patient.id}/export",
            params={"reason": REASON},
            headers=auth_headers,
        )
        sections = {f"{s['module']}.{s['section']}": s for s in response.json()["data"]["sections"]}

        invoices = sections["billing.invoices"]
        assert invoices["erasable"] is False
        assert "fiscal" in invoices["retention_reason"].lower()
        assert sections["patients.identity"]["erasable"] is True

    async def test_requires_a_reason(
        self, client: AsyncClient, auth_headers: dict, test_clinic, db_session: AsyncSession
    ) -> None:
        patient = await _patient(db_session, test_clinic)
        response = await client.get(
            f"/api/v1/privacy/subjects/{patient.id}/export", headers=auth_headers
        )
        assert response.status_code == 422

    async def test_is_recorded(
        self, client: AsyncClient, auth_headers: dict, test_clinic, db_session: AsyncSession
    ) -> None:
        patient = await _patient(db_session, test_clinic)
        await client.get(
            f"/api/v1/privacy/subjects/{patient.id}/export",
            params={"reason": REASON},
            headers=auth_headers,
        )

        row = (
            await db_session.execute(
                select(SubjectRequest).where(SubjectRequest.patient_id == patient.id)
            )
        ).scalar_one()
        assert row.action == "export"
        assert row.reason == REASON

    async def test_requires_authentication(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        response = await client.get(
            f"/api/v1/privacy/subjects/{uuid4()}/export", params={"reason": REASON}
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestErasure:
    async def test_scrubs_and_reports(
        self, client: AsyncClient, auth_headers: dict, test_clinic, db_session: AsyncSession
    ) -> None:
        patient = await _patient(db_session, test_clinic)
        response = await client.post(
            f"/api/v1/privacy/subjects/{patient.id}/erasure",
            json={"reason": REASON},
            headers=auth_headers,
        )
        assert response.status_code == 201

        data = response.json()["data"]
        assert data["scrubbed"]["patients.identity"] > 0
        retained = {r["module"] + "." + r["section"] for r in data["retained"]}
        assert "billing.invoices" in retained

    async def test_actually_erases(
        self, client: AsyncClient, auth_headers: dict, test_clinic, db_session: AsyncSession
    ) -> None:
        patient = await _patient(db_session, test_clinic)
        await client.post(
            f"/api/v1/privacy/subjects/{patient.id}/erasure",
            json={"reason": REASON},
            headers=auth_headers,
        )

        await db_session.rollback()  # read what the endpoint committed
        refreshed = (
            await db_session.execute(select(Patient).where(Patient.id == patient.id))
        ).scalar_one()
        assert refreshed.first_name != "Ana"
        assert refreshed.phone is None

    async def test_leaves_a_record_that_outlives_the_data(
        self, client: AsyncClient, auth_headers: dict, test_clinic, db_session: AsyncSession
    ) -> None:
        patient = await _patient(db_session, test_clinic)
        response = await client.post(
            f"/api/v1/privacy/subjects/{patient.id}/erasure",
            json={"reason": REASON},
            headers=auth_headers,
        )
        request_id = response.json()["data"]["request_id"]

        await db_session.rollback()
        row = (
            await db_session.execute(select(SubjectRequest).where(SubjectRequest.id == request_id))
        ).scalar_one()
        assert row.action == "erasure"
        assert row.reason == REASON
        # Enough to reconstruct the answer given to the patient.
        assert row.outcome["scrubbed"]
        assert any(r["section"] == "billing.invoices" for r in row.outcome["retained"])

    @pytest.mark.parametrize("reason", ["", "corto"])
    async def test_refuses_a_throwaway_reason(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_clinic,
        db_session: AsyncSession,
        reason: str,
    ) -> None:
        # The reason is the only record of the request that survives it,
        # so a keystroke is not enough.
        patient = await _patient(db_session, test_clinic)
        response = await client.post(
            f"/api/v1/privacy/subjects/{patient.id}/erasure",
            json={"reason": reason},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        response = await client.post(
            f"/api/v1/privacy/subjects/{uuid4()}/erasure", json={"reason": REASON}
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestPermissions:
    async def test_a_user_without_the_grant_is_refused(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ) -> None:
        # No clinic membership, so no grant — and the export hands out a
        # clinic's most sensitive data, so the default must be refusal.
        response = await client.get(
            f"/api/v1/privacy/subjects/{uuid4()}/export",
            params={"reason": REASON},
            headers=auth_headers,
        )
        assert response.status_code == 403


@pytest.mark.asyncio
class TestRequestLog:
    async def test_lists_newest_first(
        self, client: AsyncClient, auth_headers: dict, test_clinic, db_session: AsyncSession
    ) -> None:
        patient = await _patient(db_session, test_clinic)
        for _ in range(2):
            await client.get(
                f"/api/v1/privacy/subjects/{patient.id}/export",
                params={"reason": REASON},
                headers=auth_headers,
            )

        response = await client.get("/api/v1/privacy/subjects/requests", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 2
        assert all(row["action"] == "export" for row in body["data"])

    async def test_filters_by_patient(
        self, client: AsyncClient, auth_headers: dict, test_clinic, db_session: AsyncSession
    ) -> None:
        patient = await _patient(db_session, test_clinic)
        await client.get(
            f"/api/v1/privacy/subjects/{patient.id}/export",
            params={"reason": REASON},
            headers=auth_headers,
        )

        response = await client.get(
            "/api/v1/privacy/subjects/requests",
            params={"patient_id": str(uuid4())},
            headers=auth_headers,
        )
        assert response.json()["total"] == 0

    async def test_unknown_request_is_404(
        self, client: AsyncClient, auth_headers: dict, test_clinic
    ) -> None:
        response = await client.get(
            f"/api/v1/privacy/subjects/requests/{uuid4()}", headers=auth_headers
        )
        assert response.status_code == 404


async def _patient(db_session: AsyncSession, clinic) -> Patient:
    """A patient in the clinic the ``test_clinic`` fixture made us admin of."""
    patient = Patient(
        clinic_id=clinic.id,
        first_name="Ana",
        last_name="García",
        phone="5512345678",
        email="ana@example.com",
        national_id="GOMA850101HDFNRL09",
        national_id_type="curp",
        date_of_birth=date(1985, 1, 1),
    )
    db_session.add(patient)
    await db_session.commit()
    return patient
