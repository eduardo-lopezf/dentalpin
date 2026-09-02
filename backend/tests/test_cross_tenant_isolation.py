"""Clinic A must never read clinic B's data by guessing an id.

ADR 0029, invariant 2, first half. Function-level authorization is
covered by ``test_route_authorization_coverage.py``; this asks the
*object*-level question, which is the one the 2026-07-03 audit answered
badly — ``POST /auth/users`` had a correct permission check and no check
that the ``clinic_id`` in the body was the caller's
(``test_auth_create_user_scope.py``).

The sweep is driven by the routes that exist rather than by a list
someone maintains: 35 endpoints across 13 modules take a
``{patient_id}``, so one foreign patient exercises nearly every module
that holds patient data. The caller is an admin — the role with ``*`` —
so nothing here is a permission failure in disguise: if a response comes
back, authorization allowed it and only scoping could have stopped it.

The RLS half of the invariant is not here. Until it lands, this file is
what stands between a forgotten ``.where(clinic_id == ...)`` and a leak.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.budget.models import Budget
from app.modules.clinical_notes.models import ClinicalNote
from app.modules.media.models import Document
from app.modules.patients.models import Patient
from app.modules.patients_clinical.models import Allergy
from app.modules.professionals.models import Professional
from app.modules.recalls.models import Recall
from app.modules.treatment_plan.models import TreatmentPlan

# Distinctive enough that finding it anywhere in a response body is
# unambiguous evidence, and that a substring search cannot false-positive
# on ordinary fixture data.
MARKER = "Zzforeignleakmarker"

# Every mounted GET route taking a {patient_id}, from the route table
# itself (see the module docstring). Kept literal rather than generated
# so that a route disappearing is a visible diff rather than a silently
# smaller sweep.
PATIENT_ROUTES: tuple[str, ...] = (
    "/api/v1/billing/patients/{pid}/summary",
    "/api/v1/clinical_notes/patients/{pid}/by-plan",
    "/api/v1/clinical_notes/patients/{pid}/recent",
    "/api/v1/media/patients/{pid}/documents",
    "/api/v1/media/patients/{pid}/photos",
    "/api/v1/notifications/conversations/{pid}",
    "/api/v1/notifications/preferences/patient/{pid}",
    "/api/v1/odontogram/patients/{pid}/history",
    "/api/v1/odontogram/patients/{pid}/odontogram",
    "/api/v1/odontogram/patients/{pid}/odontogram/timeline",
    "/api/v1/odontogram/patients/{pid}/teeth/11",
    "/api/v1/odontogram/patients/{pid}/teeth/11/full",
    "/api/v1/odontogram/patients/{pid}/teeth/11/history",
    "/api/v1/odontogram/patients/{pid}/treatments",
    "/api/v1/patient_timeline/patients/{pid}",
    "/api/v1/patients/{pid}",
    "/api/v1/patients/{pid}/extended",
    "/api/v1/patients_clinical/patients/{pid}/alerts",
    "/api/v1/patients_clinical/patients/{pid}/allergies",
    "/api/v1/patients_clinical/patients/{pid}/emergency-contact",
    "/api/v1/patients_clinical/patients/{pid}/legal-guardian",
    "/api/v1/patients_clinical/patients/{pid}/medical-context",
    "/api/v1/patients_clinical/patients/{pid}/medical-history",
    "/api/v1/patients_clinical/patients/{pid}/medications",
    "/api/v1/patients_clinical/patients/{pid}/surgical-history",
    "/api/v1/patients_clinical/patients/{pid}/systemic-diseases",
    "/api/v1/payments/patients/{pid}/ledger",
    "/api/v1/payments/patients/{pid}/pending-charges",
    "/api/v1/periodontogram/patients/{pid}/draft",
    "/api/v1/periodontogram/patients/{pid}/snapshots",
    "/api/v1/periodontogram/patients/{pid}/timeline",
    "/api/v1/privacy/subjects/{pid}/export",
    "/api/v1/recalls/patients/{pid}",
    "/api/v1/treatment_plan/treatment-plans/patient/{pid}",
)

# Routes known to answer about a patient in another tenant. Empty, and
# meant to stay that way.
#
# The first sweep put three entries here and all three were fixed rather
# than left on a list. Two — billing's patient summary and payments'
# ledger — aggregated under a correct clinic_id filter and returned
# zeros, so they disclosed nothing but answered a question about a
# patient they should not have been able to name. The third,
# notifications' preferences, reached a get-or-create that WROTE a row
# carrying the caller's clinic_id and an unvalidated patient_id whose FK
# points at patients.id: a cross-tenant write performed by a read.
#
# ``strict=True`` is what keeps this honest in both directions. An entry
# added here to quiet a failure turns into a failure of its own the day
# the route is fixed, so nothing can rot quietly.
KNOWN_UNSCOPED: dict[str, str] = {}


def _patient_case(template: str) -> object:
    reason = KNOWN_UNSCOPED.get(template)
    marks = [pytest.mark.xfail(strict=True, reason=reason)] if reason else []
    return pytest.param(template, marks=marks, id=template)


PROFESSIONAL_ROUTES: tuple[str, ...] = (
    "/api/v1/professionals/{prid}",
    "/api/v1/professionals/{prid}/photo",
    "/api/v1/schedules/professionals/{prid}/hours",
    "/api/v1/schedules/professionals/{prid}/overrides",
)


@dataclass(frozen=True)
class Foreign:
    """Ids belonging to a clinic the caller is not a member of."""

    clinic_id: UUID
    patient_id: UUID
    professional_id: UUID
    allergy_id: UUID
    note_id: UUID
    recall_id: UUID
    document_id: UUID
    budget_id: UUID
    plan_id: UUID


@pytest_asyncio.fixture
async def foreign(db_session: AsyncSession) -> Foreign:
    """A second clinic, with a patient and a professional carrying MARKER.

    Deliberately built without a membership for the test user: the whole
    question is what happens when a caller who legitimately holds every
    permission addresses an object outside their tenant.
    """
    clinic = Clinic(
        id=uuid4(),
        name=f"{MARKER} Clinic",
        tax_id="B00000042",
        address={},
        settings={},
        account_tier="clinic",
    )
    db_session.add(clinic)
    await db_session.flush()

    patient = Patient(
        id=uuid4(),
        clinic_id=clinic.id,
        first_name=MARKER,
        last_name=f"{MARKER}son",
        email=f"{MARKER.lower()}@elsewhere.test",
        phone="+34600000999",
    )
    professional = Professional(
        id=uuid4(),
        clinic_id=clinic.id,
        first_name=MARKER,
        last_name=f"{MARKER}sen",
        professional_type="dentist",
    )
    user = User(
        email=f"{MARKER.lower()}@staff.test",
        password_hash="x" * 60,
        first_name=MARKER,
        last_name=f"{MARKER}sen",
    )
    db_session.add_all([patient, professional, user])
    await db_session.flush()

    # One row per destructive route below. Seeded directly rather than
    # through the business flow: the question is whether a foreign id is
    # honoured, not whether the row is realistic.
    allergy = Allergy(clinic_id=clinic.id, patient_id=patient.id, name=MARKER)
    note = ClinicalNote(
        clinic_id=clinic.id,
        note_type="diagnosis",
        owner_type="patient",
        owner_id=patient.id,
        body=MARKER,
        author_id=user.id,
    )
    recall = Recall(
        clinic_id=clinic.id,
        patient_id=patient.id,
        due_month=date(2027, 1, 1),
        reason="hygiene",
    )
    document = Document(
        clinic_id=clinic.id,
        patient_id=patient.id,
        document_type="other",
        title=MARKER,
        original_filename=f"{MARKER}.pdf",
        storage_path=f"foreign/{MARKER}.pdf",
        mime_type="application/pdf",
        file_size=1,
        uploaded_by=user.id,
    )
    budget = Budget(
        clinic_id=clinic.id,
        patient_id=patient.id,
        budget_number=f"{MARKER}-B1",
        valid_from=date(2026, 1, 1),
        created_by=user.id,
    )
    plan = TreatmentPlan(
        clinic_id=clinic.id,
        patient_id=patient.id,
        plan_number=f"{MARKER}-P1",
        created_by=user.id,
    )
    db_session.add_all([allergy, note, recall, document, budget, plan])
    await db_session.commit()

    return Foreign(
        clinic_id=clinic.id,
        patient_id=patient.id,
        professional_id=professional.id,
        allergy_id=allergy.id,
        note_id=note.id,
        recall_id=recall.id,
        document_id=document.id,
        budget_id=budget.id,
        plan_id=plan.id,
    )


def _assert_no_leak(response, url: str) -> None:
    """The response must carry nothing belonging to the foreign clinic.

    Three separate failures, because they mean different things:

    - a 5xx is a bug the sweep found, not a leak, but it hides whatever
      the route would have done and must not pass quietly;
    - the marker in the body is a disclosure;
    - a 200 carrying data for an id in another tenant is a disclosure
      even when no marker survived the serialisation, because the route
      answered a question it should not have understood.
    """
    assert response.status_code < 500, (
        f"{url} returned {response.status_code} on a foreign id: {response.text[:300]}"
    )

    assert MARKER.lower() not in response.text.lower(), (
        f"{url} disclosed clinic B's data to clinic A: {response.text[:300]}"
    )

    if response.status_code != 200:
        return

    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else payload

    assert not data, (
        f"{url} answered 200 with data for a patient in another clinic. "
        f"Scope the query by ctx.clinic_id (and verify the path object "
        f"belongs to it) instead of trusting the id: {response.text[:300]}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("template", [_patient_case(t) for t in PATIENT_ROUTES])
async def test_patient_routes_reject_a_foreign_patient(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    foreign: Foreign,
    template: str,
) -> None:
    url = template.format(pid=foreign.patient_id)

    _assert_no_leak(await client.get(url, headers=auth_headers), url)


@pytest.mark.asyncio
@pytest.mark.parametrize("template", PROFESSIONAL_ROUTES, ids=PROFESSIONAL_ROUTES)
async def test_professional_routes_reject_a_foreign_professional(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    foreign: Foreign,
    template: str,
) -> None:
    url = template.format(prid=foreign.professional_id)

    _assert_no_leak(await client.get(url, headers=auth_headers), url)


# --- Destructive routes ---------------------------------------------------
#
# The sweeps above walk GETs. A cross-tenant DELETE is the same defect with
# a worse ending — it does not disclose another clinic's data, it destroys
# it — and 32 mounted DELETE routes take an id in the path. These are the
# ones carrying patient data, one per module that has such a route.
#
# The assertion that matters is the second one: a 404 that deleted anyway
# would pass a status check and fail the clinic. Soft deletes are why the
# snapshot compares `status` and `deleted_at` rather than mere existence —
# `patients` is soft-deleted by convention, so "the row is still there" is
# not the same as "the row is untouched".
DELETE_ROUTES: tuple[tuple[str, type, str], ...] = (
    ("/api/v1/patients/{patient_id}", Patient, "patient_id"),
    (
        "/api/v1/patients_clinical/patients/{patient_id}/allergies/{allergy_id}",
        Allergy,
        "allergy_id",
    ),
    ("/api/v1/clinical_notes/notes/{note_id}", ClinicalNote, "note_id"),
    ("/api/v1/recalls/{recall_id}", Recall, "recall_id"),
    ("/api/v1/media/documents/{document_id}", Document, "document_id"),
    ("/api/v1/budget/budgets/{budget_id}", Budget, "budget_id"),
    ("/api/v1/treatment_plan/treatment-plans/{plan_id}", TreatmentPlan, "plan_id"),
)


async def _snapshot(db: AsyncSession, model: type, row_id: UUID) -> tuple:
    """What must not change: existence, and any soft-delete marker."""
    row = await db.get(model, row_id)
    if row is None:
        return (False, None, None)
    await db.refresh(row)
    return (True, getattr(row, "status", None), getattr(row, "deleted_at", None))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "template,model,attr",
    DELETE_ROUTES,
    ids=[t for t, _, _ in DELETE_ROUTES],
)
async def test_delete_routes_reject_a_foreign_object(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    foreign: Foreign,
    db_session: AsyncSession,
    template: str,
    model: type,
    attr: str,
) -> None:
    row_id = getattr(foreign, attr)
    # `patient_id` is both a path segment of the nested routes and the
    # target of the first one, so build the mapping before formatting.
    url = template.format(**{"patient_id": foreign.patient_id, attr: row_id})
    before = await _snapshot(db_session, model, row_id)
    assert before[0], "the fixture did not seed the row this case is about"

    response = await client.delete(url, headers=auth_headers)

    assert 400 <= response.status_code < 500, (
        f"{url} answered {response.status_code} deleting another clinic's row: "
        f"{response.text[:300]}"
    )
    assert await _snapshot(db_session, model, row_id) == before, (
        f"{url} refused the request and mutated the row anyway"
    )


@pytest.mark.asyncio
async def test_writing_preferences_for_a_foreign_patient_is_refused(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    foreign: Foreign,
    db_session: AsyncSession,
) -> None:
    """The sweep above only walks GETs; this is the matching write.

    Both notifications preference endpoints funnel into the same
    get-or-create, so the guard sits there rather than in either handler.
    The assertion that matters is the second one: a refusal that still
    left the row behind would be a fix in name only.
    """
    from app.modules.notifications.models import NotificationPreference

    url = f"/api/v1/notifications/preferences/patient/{foreign.patient_id}"

    response = await client.put(url, headers=auth_headers, json={"email_enabled": False})

    assert response.status_code == 404, response.text

    planted = await db_session.scalar(
        select(NotificationPreference.id).where(
            NotificationPreference.patient_id == foreign.patient_id
        )
    )
    assert planted is None, "the refused request still wrote a cross-tenant row"


@pytest.mark.asyncio
async def test_the_marker_is_actually_reachable_in_the_own_clinic(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    """Prove the sweep would notice a leak.

    Every assertion above is a negative, and a suite of negatives passes
    just as well against a broken fixture, a wrong URL or an endpoint
    that 404s for unrelated reasons. So: put the same marker on a patient
    of the caller's *own* clinic and confirm the same route hands it
    back. If this fails, the sweep above proves nothing.
    """
    mine = Patient(
        id=uuid4(),
        clinic_id=test_clinic.id,
        first_name=MARKER,
        last_name=f"{MARKER}son",
    )
    db_session.add(mine)
    await db_session.commit()

    response = await client.get(f"/api/v1/patients/{mine.id}", headers=auth_headers)

    assert response.status_code == 200
    assert MARKER.lower() in response.text.lower()


def test_the_known_unscoped_baseline_has_no_stale_entries() -> None:
    """A baseline that outlives its routes stops describing anything."""
    stale = sorted(set(KNOWN_UNSCOPED) - set(PATIENT_ROUTES))

    assert not stale, f"Baseline names routes the sweep no longer covers: {stale}"
