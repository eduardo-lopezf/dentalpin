"""The tier/custody pairing: which tiers a deployment may create.

``basic`` and ``medium`` are sold hosted and only hosted; every other
tier may be self, managed or byok. Both halves are mandatory at creation
and neither is defaulted — that is the property these tests pin, because
a default on either half decides a commercial offer by accident.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.privacy import (
    AccountTier,
    CustodyMode,
    TierCustodyError,
    allowed_custody_modes,
    incompatible_tiers,
    tiers_available_under,
    validate_tier_custody,
)


def test_entry_tiers_are_managed_only() -> None:
    for tier in (AccountTier.BASIC, AccountTier.MEDIUM):
        assert allowed_custody_modes(tier) == frozenset({CustodyMode.MANAGED})


def test_every_other_tier_takes_any_mode() -> None:
    for tier in (
        AccountTier.ADVANCED,
        AccountTier.CLINIC,
        AccountTier.CLINIC_PRO,
        AccountTier.HOSPITAL,
    ):
        assert allowed_custody_modes(tier) == frozenset(CustodyMode)


def test_every_tier_is_covered() -> None:
    """A tier added without deciding its custody rule fails here.

    The same guard ``test_privacy_policy`` puts on ``CustodyMode``: the
    taxonomy is not allowed to grow a member whose commercial rule nobody
    wrote down.
    """
    for tier in AccountTier:
        assert allowed_custody_modes(tier), f"{tier} is sold under no custody mode at all"


@pytest.mark.parametrize("mode", list(CustodyMode))
def test_available_tiers_are_the_inverse(mode: CustodyMode) -> None:
    available = tiers_available_under(mode)
    for tier in AccountTier:
        assert (tier in available) is (mode in allowed_custody_modes(tier))


def test_validate_accepts_a_sold_pairing() -> None:
    validate_tier_custody(AccountTier.BASIC, CustodyMode.MANAGED)
    validate_tier_custody(AccountTier.HOSPITAL, CustodyMode.SELF)


@pytest.mark.parametrize("mode", [CustodyMode.SELF, CustodyMode.BYOK])
def test_validate_rejects_entry_tier_outside_managed(mode: CustodyMode) -> None:
    with pytest.raises(TierCustodyError) as exc:
        validate_tier_custody(AccountTier.BASIC, mode)
    assert "basic" in str(exc.value)
    assert "managed" in str(exc.value)


def test_audit_reports_stranded_tiers_and_unknown_values() -> None:
    assert incompatible_tiers(["clinic", "hospital"], CustodyMode.SELF) == ()
    assert incompatible_tiers(["basic", "clinic"], CustodyMode.SELF) == ("basic",)
    # An unknown string cannot be shown to be allowed, so it is reported.
    assert incompatible_tiers(["enterprise"], CustodyMode.MANAGED) == ("enterprise",)
    # Duplicates collapse — the audit names each offending tier once.
    assert incompatible_tiers(["basic", "basic"], CustodyMode.BYOK) == ("basic",)


@pytest.mark.asyncio
async def test_column_rejects_a_tier_outside_the_taxonomy(db_session: AsyncSession) -> None:
    """The CHECK constraint is the database's half of the rule."""
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO clinics (id, name, tax_id, timezone, currency, account_tier, settings) "
                "VALUES (gen_random_uuid(), 'X', 'B9', 'UTC', 'MXN', 'enterprise', '{}'::jsonb)"
            )
        )
    await db_session.rollback()


@pytest.mark.asyncio
async def test_column_has_no_default(db_session: AsyncSession) -> None:
    """An INSERT that names no tier must fail rather than pick one."""
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO clinics (id, name, tax_id, timezone, currency, settings) "
                "VALUES (gen_random_uuid(), 'X', 'B8', 'UTC', 'MXN', '{}'::jsonb)"
            )
        )
    await db_session.rollback()


@pytest.mark.asyncio
async def test_setup_requires_an_account_tier(client: AsyncClient) -> None:
    """The tier is mandatory in the payload, not defaulted by the route."""
    response = await client.post(
        "/api/v1/auth/setup",
        json={
            "admin_first_name": "A",
            "admin_last_name": "B",
            "admin_email": "a@b.test",
            "admin_password": "Str0ng!passw0rd",
            "clinic_name": "C",
            "clinic_tax_id": "B7",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_setup_status_reports_what_this_deployment_may_create(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/setup/status")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["custody_mode"] == CustodyMode.MANAGED.value
    # The test harness runs managed, so every tier is on offer.
    assert set(data["available_account_tiers"]) == {tier.value for tier in AccountTier}
