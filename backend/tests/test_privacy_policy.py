"""Tests for ``PrivacyPolicy`` — the custody and regime model (ADR 0023)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.core.privacy import (
    SELF_HOSTED_POLICY,
    BreakGlassPolicy,
    CustodyMode,
    KeyCustody,
    OperatorAccess,
    PrivacyPolicy,
)


def _regime() -> dict[str, object]:
    return {
        "jurisdictions": frozenset({"MX"}),
        "regulations": frozenset({"lfpdppp"}),
        "data_residency": "mx-central",
    }


class TestCustodyModes:
    def test_self_hosted_has_no_operator_and_customer_keys(self) -> None:
        p = PrivacyPolicy.self_hosted()
        assert p.custody_mode is CustodyMode.SELF
        assert p.operator_access is OperatorAccess.NONE
        assert p.key_custody is KeyCustody.CUSTOMER
        assert p.break_glass is None

    def test_managed_is_break_glass_over_operator_keys(self) -> None:
        p = PrivacyPolicy.managed(**_regime())  # type: ignore[arg-type]
        assert p.custody_mode is CustodyMode.MANAGED
        assert p.operator_access is OperatorAccess.BREAK_GLASS
        assert p.key_custody is KeyCustody.OPERATOR

    def test_byok_is_break_glass_over_customer_keys(self) -> None:
        p = PrivacyPolicy.byok(**_regime())  # type: ignore[arg-type]
        assert p.custody_mode is CustodyMode.BYOK
        assert p.operator_access is OperatorAccess.BREAK_GLASS
        # The difference that makes BYOK worth having: we operate the
        # deployment without holding what decrypts it.
        assert p.key_custody is KeyCustody.CUSTOMER

    def test_every_mode_is_covered(self) -> None:
        # A new mode must decide its access and custody, not inherit them.
        built = {
            PrivacyPolicy.self_hosted().custody_mode,
            PrivacyPolicy.managed(**_regime()).custody_mode,  # type: ignore[arg-type]
            PrivacyPolicy.byok(**_regime()).custody_mode,  # type: ignore[arg-type]
        }
        assert built == set(CustodyMode)


class TestBreakGlass:
    def test_filled_with_defaults_when_omitted(self) -> None:
        p = PrivacyPolicy.managed(**_regime())  # type: ignore[arg-type]
        assert p.break_glass == BreakGlassPolicy()
        assert p.break_glass is not None
        assert p.break_glass.max_duration_minutes == 60
        assert p.break_glass.requires_reason
        assert p.break_glass.notifies_customer

    def test_custom_terms_survive(self) -> None:
        terms = BreakGlassPolicy(max_duration_minutes=15, notifies_customer=False)
        p = PrivacyPolicy.byok(**_regime(), break_glass=terms)  # type: ignore[arg-type]
        assert p.break_glass == terms

    def test_self_hosted_cannot_declare_operator_access(self) -> None:
        # Bounding an access path that does not exist would describe a
        # control we cannot provide.
        with pytest.raises(ValueError, match="cannot carry a break_glass"):
            PrivacyPolicy(
                custody_mode=CustodyMode.SELF,
                break_glass=BreakGlassPolicy(),
                **_regime(),  # type: ignore[arg-type]
            )

    def test_zero_duration_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_duration_minutes must be positive"):
            BreakGlassPolicy(max_duration_minutes=0)


class TestRegime:
    def test_jurisdictions_must_be_iso_alpha2(self) -> None:
        with pytest.raises(ValueError, match="ISO 3166-1 alpha-2"):
            PrivacyPolicy.self_hosted(jurisdictions=frozenset({"mex"}))

    def test_jurisdictions_cannot_be_empty(self) -> None:
        with pytest.raises(ValueError, match="jurisdictions cannot be empty"):
            PrivacyPolicy.self_hosted(jurisdictions=frozenset())

    def test_residency_cannot_be_empty(self) -> None:
        with pytest.raises(ValueError, match="data_residency cannot be empty"):
            PrivacyPolicy.self_hosted(data_residency="")

    def test_jurisdiction_and_regulation_are_independent(self) -> None:
        # A Spanish clinic answers to two regimes over one jurisdiction.
        p = PrivacyPolicy.managed(
            jurisdictions=frozenset({"ES"}),
            regulations=frozenset({"gdpr", "lopdgdd"}),
            data_residency="eu-west",
        )
        assert p.jurisdictions == {"ES"}
        assert p.regulations == {"gdpr", "lopdgdd"}


class TestEgress:
    def test_default_denies_everything(self) -> None:
        assert not PrivacyPolicy.self_hosted().allows_egress("openai")

    def test_allows_only_declared_targets(self) -> None:
        p = PrivacyPolicy.managed(**_regime(), egress_allowed=frozenset({"openai"}))  # type: ignore[arg-type]
        assert p.allows_egress("openai")
        assert not p.allows_egress("kapso")


class TestValueSemantics:
    def test_frozen(self) -> None:
        with pytest.raises(FrozenInstanceError):
            SELF_HOSTED_POLICY.data_residency = "eu-west"  # type: ignore[misc]

    def test_hashable_so_it_can_ride_on_tenant_context(self) -> None:
        a = PrivacyPolicy.managed(**_regime())  # type: ignore[arg-type]
        b = PrivacyPolicy.managed(**_regime())  # type: ignore[arg-type]
        assert a == b
        assert {a, b} == {a}

    def test_shared_default_is_self_hosted(self) -> None:
        assert SELF_HOSTED_POLICY.custody_mode is CustodyMode.SELF
        assert SELF_HOSTED_POLICY == PrivacyPolicy.self_hosted()
