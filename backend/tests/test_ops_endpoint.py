"""The operator's window into a deployment (ADR 0049 rule 4).

``/api/v1/ops`` is read by the control plane, never by a clinic's users.
What is pinned here:

- it does not exist until ``CONTROL_PLANE_SECRET`` is set, and never
  under ``self`` custody;
- only a token signed with that secret, for that audience, opens it — a
  staff session does not;
- what it returns is sizes, counts and identifiers: a patient's name
  never crosses it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth.models import Clinic, User
from app.core.ops.router import OPS_AUDIENCE
from app.modules.catalog.models import Specialty

SECRET = "control-plane-secret-for-tests-0123456789"


def _token(secret: str = SECRET, audience: str = OPS_AUDIENCE, minutes: int = 1) -> dict[str, str]:
    payload = {"aud": audience, "exp": datetime.now(UTC) + timedelta(minutes=minutes)}
    return {"Authorization": f"Bearer {jwt.encode(payload, secret, algorithm='HS256')}"}


@pytest.fixture
def ops_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "CONTROL_PLANE_SECRET", SECRET)


async def test_absent_without_a_secret(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Set explicitly: a developer's own backend may well have one.
    monkeypatch.setattr(settings, "CONTROL_PLANE_SECRET", "")
    response = await client.get("/api/v1/ops/usage", headers=_token())
    assert response.status_code == 404


async def test_absent_under_self_custody(
    client: AsyncClient, ops_enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "TENANT_CUSTODY_MODE", "self")
    response = await client.get("/api/v1/ops/usage", headers=_token())
    assert response.status_code == 404


@pytest.mark.parametrize(
    "headers",
    [
        {},
        _token(secret="another-secret-entirely-0123456789abcdef"),
        _token(audience="something-else"),
        _token(minutes=-5),
    ],
    ids=["no token", "wrong secret", "wrong audience", "expired"],
)
async def test_refuses_anything_but_its_own_token(
    client: AsyncClient, ops_enabled: None, headers: dict[str, str]
) -> None:
    response = await client.get("/api/v1/ops/usage", headers=headers)
    assert response.status_code == 401


async def test_refuses_a_staff_session(
    client: AsyncClient, ops_enabled: None, auth_headers: dict[str, str]
) -> None:
    response = await client.get("/api/v1/ops/usage", headers=auth_headers)
    assert response.status_code == 401


async def test_usage_lists_each_clinic_with_its_share(
    client: AsyncClient, ops_enabled: None, test_clinic: Clinic, auth_headers: dict[str, str]
) -> None:
    created = await client.post(
        "/api/v1/patients",
        json={"first_name": "Aurelia", "last_name": "Zamarripa"},
        headers=auth_headers,
    )
    assert created.status_code == 201

    response = await client.get("/api/v1/ops/usage?refresh=true", headers=_token())
    assert response.status_code == 200
    usage = response.json()["data"]

    [clinic] = usage["clinics"]
    assert clinic["id"] == str(test_clinic.id)
    assert clinic["users"] == 1
    assert clinic["database_rows"] >= 1
    assert 0 < clinic["database_bytes"] <= usage["database_bytes"]
    assert usage["shared_database_bytes"] + clinic["database_bytes"] == usage["database_bytes"]
    assert clinic["storage_bytes"] == 0


async def test_log_says_where_and_when_never_what(
    client: AsyncClient, ops_enabled: None, test_clinic: Clinic, auth_headers: dict[str, str]
) -> None:
    await client.post(
        "/api/v1/patients",
        json={"first_name": "Aurelia", "last_name": "Zamarripa"},
        headers=auth_headers,
    )
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "test@example.com", "password": "TestPass1234"},
    )
    assert login.status_code == 200

    response = await client.get(f"/api/v1/ops/clinics/{test_clinic.id}/log", headers=_token())
    assert response.status_code == 200
    entries = response.json()["data"]

    assert any(e["kind"] == "record_created" and e["area"] == "patients" for e in entries)
    [access] = [e for e in entries if e["kind"] == "login"]
    assert access["role"] == "admin"
    assert access["user_id"]
    assert [e["at"] for e in entries] == sorted((e["at"] for e in entries), reverse=True)
    assert "Zamarripa" not in response.text
    assert "test@example.com" not in response.text


async def test_log_of_an_unknown_clinic(client: AsyncClient, ops_enabled: None) -> None:
    response = await client.get(
        "/api/v1/ops/clinics/00000000-0000-0000-0000-000000000000/log", headers=_token()
    )
    assert response.status_code == 404


HOLDER = {
    "timezone": "America/Tijuana",
    "tax_id": "ZAAU800101AB1",
    "holder_first_name": "Aurelia",
    "holder_last_name": "Zamarripa",
    "holder_email": "aurelia@example.com",
    "holder_professional_id": "1234567",
    "holder_password": "Temporal1234",
    "apps": ["workspace", "agenda", "patients", "treatments"],
}
CLINIC = HOLDER | {
    "account_tier": "clinic",
    "tax_id": "CDS200101XY9",
    "clinic_name": "Clínica Dental del Sur",
    "apps": [*HOLDER["apps"], "professionals"],
}


async def test_creating_a_clinic_needs_the_control_planes_token(
    client: AsyncClient, ops_enabled: None, auth_headers: dict[str, str]
) -> None:
    payload = HOLDER | {"account_tier": "basic"}
    response = await client.post("/api/v1/ops/clinics", json=payload, headers=auth_headers)
    assert response.status_code == 401


async def test_an_individual_tier_makes_the_holders_own_practice(
    client: AsyncClient, ops_enabled: None, db_session: AsyncSession
) -> None:
    response = await client.post(
        "/api/v1/ops/clinics", json=HOLDER | {"account_tier": "basic"}, headers=_token()
    )
    assert response.status_code == 201, response.text
    created = response.json()["data"]
    assert created["name"] == "Aurelia Zamarripa"

    clinic = await db_session.get(Clinic, UUID(created["clinic_id"]))
    assert (clinic.account_tier, clinic.timezone, clinic.tax_id) == (
        "basic",
        "America/Tijuana",
        "ZAAU800101AB1",
    )
    holder = await db_session.get(User, UUID(created["holder_user_id"]))
    assert holder.professional_id == "1234567"
    assert holder.password_hash != HOLDER["holder_password"]

    # The holder can sign in, and is the administrator of that clinic.
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": HOLDER["holder_email"], "password": HOLDER["holder_password"]},
    )
    assert login.status_code == 200
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"}
    )
    [membership] = me.json()["data"]["clinics"]
    assert (membership["id"], membership["role"]) == (created["clinic_id"], "admin")


async def test_the_clinic_tier_takes_the_clinics_own_details(
    client: AsyncClient, ops_enabled: None, db_session: AsyncSession
) -> None:
    payload = CLINIC | {
        "clinic_legal_name": "Clínica Dental del Sur, S.C.",
        "clinic_phone": "6641234567",
    }
    response = await client.post("/api/v1/ops/clinics", json=payload, headers=_token())
    assert response.status_code == 201, response.text
    clinic = await db_session.get(Clinic, UUID(response.json()["data"]["clinic_id"]))
    assert (clinic.name, clinic.legal_name, clinic.phone) == (
        "Clínica Dental del Sur",
        "Clínica Dental del Sur, S.C.",
        "6641234567",
    )


async def test_the_clinic_tier_without_a_clinic_name_is_refused(
    client: AsyncClient, ops_enabled: None
) -> None:
    response = await client.post(
        "/api/v1/ops/clinics", json=CLINIC | {"clinic_name": None}, headers=_token()
    )
    assert response.status_code == 422


async def test_an_email_already_in_use_is_refused(client: AsyncClient, ops_enabled: None) -> None:
    payload = HOLDER | {"account_tier": "medium"}
    assert (
        await client.post("/api/v1/ops/clinics", json=payload, headers=_token())
    ).status_code == 201
    again = await client.post("/api/v1/ops/clinics", json=payload, headers=_token())
    assert again.status_code == 409


async def test_a_timezone_that_does_not_exist_is_refused(
    client: AsyncClient, ops_enabled: None
) -> None:
    payload = HOLDER | {"account_tier": "basic", "timezone": "America/Atlantida"}
    response = await client.post("/api/v1/ops/clinics", json=payload, headers=_token())
    assert response.status_code == 422


async def test_apps_say_for_whom_each_is_mandatory(client: AsyncClient, ops_enabled: None) -> None:
    response = await client.get("/api/v1/ops/apps", headers=_token())
    assert response.status_code == 200
    apps = {app["name"]: app for app in response.json()["data"]}

    everyone = {"basic", "medium", "advanced", "clinic", "clinic_pro", "hospital"}
    for name in ("workspace", "agenda", "patients", "treatments"):
        assert set(apps[name]["mandatory_for"]) == everyone, name
    # A clinic has professionals; one professional's practice need not.
    assert set(apps["professionals"]["mandatory_for"]) == {"clinic", "clinic_pro", "hospital"}
    assert apps["recalls"]["mandatory_for"] == []
    assert set(apps["cash"]["requires"]) == {"budgets_payments", "professionals"} | set(
        apps["budgets_payments"]["requires"]
    )


async def test_the_chosen_apps_are_kept_in_catalog_order(
    client: AsyncClient, ops_enabled: None, db_session: AsyncSession
) -> None:
    payload = HOLDER | {
        "account_tier": "basic",
        "apps": ["recalls", "treatments", "patients", "agenda", "workspace", "agenda"],
    }
    response = await client.post("/api/v1/ops/clinics", json=payload, headers=_token())
    assert response.status_code == 201, response.text

    clinic = await db_session.get(Clinic, UUID(response.json()["data"]["clinic_id"]))
    assert clinic.apps == ["workspace", "agenda", "patients", "recalls", "treatments"]

    usage = await client.get("/api/v1/ops/usage?refresh=true", headers=_token())
    [listed] = usage.json()["data"]["clinics"]
    assert listed["apps"] == clinic.apps


@pytest.mark.parametrize(
    "tier,apps",
    [
        ("basic", ["workspace", "agenda", "patients"]),
        ("clinic", ["workspace", "agenda", "patients", "treatments"]),
        ("basic", [*HOLDER["apps"], "cash"]),
        ("basic", [*HOLDER["apps"], "ai"]),
        ("basic", [*HOLDER["apps"], "no_such_app"]),
    ],
    ids=[
        "a mandatory App left out",
        "a clinic without Professionals",
        "an App without the ones it requires",
        "an App the deployment has switched off",
        "an App that does not exist",
    ],
)
async def test_a_set_of_apps_a_clinic_cannot_have_is_refused(
    client: AsyncClient, ops_enabled: None, tier: str, apps: list[str]
) -> None:
    payload = CLINIC | {"account_tier": tier, "apps": apps}
    response = await client.post("/api/v1/ops/clinics", json=payload, headers=_token())
    assert response.status_code == 422, response.text


async def _login(client: AsyncClient, password: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", data={"username": HOLDER["holder_email"], "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_the_holder_must_replace_the_password_before_anything_else(
    client: AsyncClient, ops_enabled: None
) -> None:
    created = await client.post(
        "/api/v1/ops/clinics", json=HOLDER | {"account_tier": "basic"}, headers=_token()
    )
    assert created.status_code == 201, created.text
    first = HOLDER["holder_password"]
    session = await _login(client, first)

    # Signed in, told so, and held at the door of everything else.
    me = await client.get("/api/v1/auth/me", headers=session)
    assert me.json()["data"]["user"]["must_change_password"] is True
    assert (await client.get("/api/v1/patients", headers=session)).status_code == 403

    async def change(current: str, new: str) -> int:
        body = {"current_password": current, "new_password": new}
        return (await client.post("/api/v1/auth/password", json=body, headers=session)).status_code

    assert await change("not-the-password1", "Propia5678") == 400
    assert await change(first, first) == 422  # "changing" it to itself
    assert await change(first, "sinnumeros") == 422
    assert (await client.get("/api/v1/patients", headers=session)).status_code == 403

    assert await change(first, "Propia5678") == 204
    assert (await client.get("/api/v1/patients", headers=session)).status_code == 200
    me = await client.get("/api/v1/auth/me", headers=session)
    assert me.json()["data"]["user"]["must_change_password"] is False
    await _login(client, "Propia5678")


async def test_an_account_with_its_own_password_is_not_held(
    client: AsyncClient, test_clinic: Clinic, auth_headers: dict[str, str]
) -> None:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.json()["data"]["user"]["must_change_password"] is False
    assert (await client.get("/api/v1/patients", headers=auth_headers)).status_code == 200


async def _active_specialties(db: AsyncSession, clinic_id: str) -> set[str]:
    rows = await db.execute(
        select(Specialty.key).where(
            Specialty.clinic_id == UUID(clinic_id), Specialty.is_active.is_(True)
        )
    )
    return set(rows.scalars())


async def test_specialties_on_offer_and_the_one_every_clinic_has(
    client: AsyncClient, ops_enabled: None
) -> None:
    response = await client.get("/api/v1/ops/specialties", headers=_token())
    assert response.status_code == 200
    specialties = {s["key"]: s for s in response.json()["data"]}
    assert len(specialties) == 17
    assert [key for key, s in specialties.items() if s["required"]] == ["general"]
    assert specialties["general"]["names"]["es"] == "Odontología General"


async def test_a_clinic_starts_with_exactly_the_specialties_chosen(
    client: AsyncClient, ops_enabled: None, db_session: AsyncSession
) -> None:
    payload = HOLDER | {"account_tier": "basic", "specialties": ["radiologia", "general"]}
    response = await client.post("/api/v1/ops/clinics", json=payload, headers=_token())
    assert response.status_code == 201, response.text

    clinic_id = response.json()["data"]["clinic_id"]
    # ``radiologia`` is not a baseline discipline; ``endodoncia`` is, and
    # was not chosen.
    assert await _active_specialties(db_session, clinic_id) == {"general", "radiologia"}


async def test_without_a_choice_a_clinic_gets_the_baseline_specialties(
    client: AsyncClient, ops_enabled: None, db_session: AsyncSession
) -> None:
    response = await client.post(
        "/api/v1/ops/clinics", json=HOLDER | {"account_tier": "basic"}, headers=_token()
    )
    active = await _active_specialties(db_session, response.json()["data"]["clinic_id"])
    assert {"general", "endodoncia", "ortodoncia"} <= active and "radiologia" not in active


@pytest.mark.parametrize(
    "specialties", [["endodoncia"], ["general", "astrologia"]], ids=["without general", "unknown"]
)
async def test_a_set_of_specialties_a_clinic_cannot_have_is_refused(
    client: AsyncClient, ops_enabled: None, specialties: list[str]
) -> None:
    payload = HOLDER | {"account_tier": "basic", "specialties": specialties}
    response = await client.post("/api/v1/ops/clinics", json=payload, headers=_token())
    assert response.status_code == 422, response.text


async def _status(client: AsyncClient) -> dict:
    response = await client.get("/api/v1/ops/usage?refresh=true", headers=_token())
    [clinic] = response.json()["data"]["clinics"]
    return clinic


async def test_a_clinic_nobody_signed_in_to_has_no_recent_activity(
    client: AsyncClient, ops_enabled: None, test_clinic: Clinic
) -> None:
    clinic = await _status(client)
    assert (clinic["status"], clinic["last_access_at"]) == ("inactive", None)


async def test_a_clinic_is_active_while_someone_is_signed_in_and_offline_after(
    client: AsyncClient, ops_enabled: None, test_clinic: Clinic
) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "test@example.com", "password": "TestPass1234"},
    )
    assert (await _status(client))["status"] == "active"

    await client.post("/api/v1/auth/logout", json={"refresh_token": login.json()["refresh_token"]})
    clinic = await _status(client)
    assert clinic["status"] == "offline" and clinic["last_access_at"]


async def test_a_deactivated_clinic_is_closed_to_its_members_until_reactivated(
    client: AsyncClient, ops_enabled: None, test_clinic: Clinic, auth_headers: dict[str, str]
) -> None:
    assert (await client.get("/api/v1/patients", headers=auth_headers)).status_code == 200

    response = await client.post(
        f"/api/v1/ops/clinics/{test_clinic.id}/deactivate", headers=_token()
    )
    assert response.status_code == 200
    state = response.json()["data"]
    assert state["status"] == "deactivated"
    # Ten days from the deactivation, to the second.
    waited = datetime.fromisoformat(state["deletable_from"]) - datetime.fromisoformat(
        state["deactivated_at"]
    )
    assert waited == timedelta(days=10)

    assert (await client.get("/api/v1/patients", headers=auth_headers)).status_code == 403
    assert (await _status(client))["status"] == "deactivated"

    # Deactivating again does not restart the wait.
    again = await client.post(f"/api/v1/ops/clinics/{test_clinic.id}/deactivate", headers=_token())
    assert again.json()["data"]["deactivated_at"] == state["deactivated_at"]

    response = await client.post(
        f"/api/v1/ops/clinics/{test_clinic.id}/reactivate", headers=_token()
    )
    assert response.json()["data"]["deactivated_at"] is None
    assert (await client.get("/api/v1/patients", headers=auth_headers)).status_code == 200


async def test_deactivating_needs_the_control_planes_token(
    client: AsyncClient, ops_enabled: None, test_clinic: Clinic, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        f"/api/v1/ops/clinics/{test_clinic.id}/deactivate", headers=auth_headers
    )
    assert response.status_code == 401
