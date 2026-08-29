"""``TENANT_CUSTODY_MODE`` and friends — how a deployment declares itself.

The default is ``managed``, because that is what this product is: we run
the deployment and hold its keys. The failure mode of that default is an
over-statement — a self-hoster who never sets the variable reports
operator access nobody actually has. That is the direction to err in; the
opposite default would have an operated deployment silently reporting
``self`` and claiming a privacy guarantee it cannot give.

None of these modes is an *enforced* control yet: ``managed`` names a
break-glass mechanism that does not exist, and ``byok`` is out of scope
for this stage. The tests below pin the declaration, not a guarantee.
"""

from __future__ import annotations

import logging

import pytest

import app.core.tenancy.single as single
from app.config import Settings
from app.core.privacy import CustodyMode, KeyCustody, OperatorAccess


@pytest.fixture
def configure(monkeypatch: pytest.MonkeyPatch):
    """Build a policy under an isolated Settings instance."""

    def _configure(**env: str):
        replacement = Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/test",
            SECRET_KEY="k" * 32,
            **env,
        )
        monkeypatch.setattr(single, "settings", replacement)
        return single.policy_from_settings()

    return _configure


class TestDefault:
    def test_unconfigured_deployment_is_managed(self, configure) -> None:
        policy = configure()
        assert policy.custody_mode is CustodyMode.MANAGED
        assert policy.operator_access is OperatorAccess.BREAK_GLASS
        assert policy.key_custody is KeyCustody.OPERATOR

    def test_default_boots_without_further_configuration(self, configure) -> None:
        # Requiring residency for the *default* mode would stop every
        # existing deployment from starting.
        assert configure().data_residency == "unspecified"

    def test_both_markets_by_default(self, configure) -> None:
        # verifactu files with the Spanish AEAT while the currency is MXN,
        # so the PHI boundary has to know both vocabularies.
        assert configure().jurisdictions == {"MX", "ES"}


class TestResidency:
    def test_self_hosted_is_on_prem_by_definition(self, configure) -> None:
        assert configure(TENANT_CUSTODY_MODE="self").data_residency == "on-prem"

    @pytest.mark.parametrize("mode", ["managed", "byok"])
    def test_operated_mode_says_unspecified_not_on_prem(self, configure, mode: str) -> None:
        # Reporting ``on-prem`` for a deployment we host would be a lie
        # rather than a gap.
        assert configure(TENANT_CUSTODY_MODE=mode).data_residency == "unspecified"

    def test_missing_residency_warns(self, configure, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="app.core.tenancy.single"):
            configure(TENANT_CUSTODY_MODE="managed")
        assert "TENANT_DATA_RESIDENCY" in caplog.text

    def test_explicit_residency_wins(self, configure) -> None:
        policy = configure(TENANT_CUSTODY_MODE="managed", TENANT_DATA_RESIDENCY="mx-central")
        assert policy.data_residency == "mx-central"


class TestUnenforcedModesAnnounceThemselves:
    @pytest.mark.parametrize(
        ("mode", "expected"),
        [("managed", "break-glass"), ("byok", "envelope encryption")],
    )
    def test_boot_says_the_mode_outruns_the_code(
        self, configure, caplog: pytest.LogCaptureFixture, mode: str, expected: str
    ) -> None:
        # A gap discovered during an audit is worse than one printed on
        # every boot.
        with caplog.at_level(logging.WARNING, logger="app.core.tenancy.single"):
            configure(TENANT_CUSTODY_MODE=mode, TENANT_DATA_RESIDENCY="mx-central")
        assert expected in caplog.text

    def test_self_hosted_has_nothing_to_warn_about(
        self, configure, caplog: pytest.LogCaptureFixture
    ) -> None:
        # The one mode that is a guarantee today, because it is an
        # absence rather than a control.
        with caplog.at_level(logging.WARNING, logger="app.core.tenancy.single"):
            configure(TENANT_CUSTODY_MODE="self")
        assert "declares more than the code enforces" not in caplog.text


class TestModes:
    def test_self_holds_nothing(self, configure) -> None:
        policy = configure(TENANT_CUSTODY_MODE="self")
        assert policy.operator_access is OperatorAccess.NONE
        assert policy.key_custody is KeyCustody.CUSTOMER
        assert policy.break_glass is None

    def test_byok_leaves_the_keys_with_the_customer(self, configure) -> None:
        policy = configure(TENANT_CUSTODY_MODE="byok", TENANT_DATA_RESIDENCY="eu-west")
        assert policy.custody_mode is CustodyMode.BYOK
        assert policy.key_custody is KeyCustody.CUSTOMER

    def test_case_and_whitespace_tolerated(self, configure) -> None:
        policy = configure(TENANT_CUSTODY_MODE="  SELF  ")
        assert policy.custody_mode is CustodyMode.SELF


class TestRejections:
    def test_unknown_mode_refuses_to_start(self, configure) -> None:
        # Falling back to a default here would pick a custody claim on
        # the operator's behalf.
        with pytest.raises(single.CustodyConfigError, match="TENANT_CUSTODY_MODE must be one of"):
            configure(TENANT_CUSTODY_MODE="hosted")

    def test_empty_jurisdictions_refused(self, configure) -> None:
        with pytest.raises(single.CustodyConfigError, match="TENANT_JURISDICTIONS cannot be empty"):
            configure(TENANT_JURISDICTIONS=" , ")

    def test_malformed_jurisdiction_refused(self, configure) -> None:
        with pytest.raises(ValueError, match="ISO 3166-1 alpha-2"):
            configure(TENANT_JURISDICTIONS="MEX")


class TestRegulations:
    def test_derived_from_jurisdictions(self, configure) -> None:
        assert configure(TENANT_JURISDICTIONS="MX").regulations == {"lfpdppp"}

    def test_one_jurisdiction_can_imply_two_regimes(self, configure) -> None:
        assert configure(TENANT_JURISDICTIONS="ES").regulations == {"gdpr", "lopdgdd"}

    def test_unmapped_jurisdiction_implies_nothing(self, configure) -> None:
        # Not an error: a country we have not mapped yet still selects its
        # document vocabulary, it just claims no regime.
        policy = configure(TENANT_JURISDICTIONS="MX,BR")
        assert policy.jurisdictions == {"MX", "BR"}
        assert policy.regulations == {"lfpdppp"}


class TestRedactionFollowsTheSetting:
    def test_jurisdictions_reach_the_phi_boundary(self, configure) -> None:
        from app.core.agents.redaction import Redactor

        redactor = Redactor.for_policy(configure(TENANT_JURISDICTIONS="ES"))
        assert redactor._kind_for_key.get("nie") == "NATID"
        assert redactor._kind_for_key.get("curp") is None
