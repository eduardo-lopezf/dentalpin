"""Production refuses to boot on a secret that cannot protect anything.

ADR 0029, invariant 6. ``Settings`` is constructed at import time in
``app.config``, so every case here builds its own instance rather than
touching the process-wide one.
"""

from __future__ import annotations

import pytest

from app.config import InsecureSecretError, Settings

GOOD = "9f3c1a7de20b48f6a5c8e1d47b2039ac6e5f81d3b70a4c29e6f1587d3ab0c942"
OTHER_GOOD = "1b74e0d9c6a2385f47ed109b3c8fa562d40e7b19f38c26ade5041b7cf6923d85"

DB = "postgresql+asyncpg://u:p@db:5432/dental_clinic"


def _settings(**overrides) -> Settings:
    base = {
        "DATABASE_URL": DB,
        "SECRET_KEY": GOOD,
        "BUDGET_PUBLIC_SECRET_KEY": OTHER_GOOD,
        "ENVIRONMENT": "production",
    }
    return Settings(**{**base, **overrides})


class TestProductionRefusals:
    def test_two_good_independent_secrets_boot(self) -> None:
        assert _settings().ENVIRONMENT == "production"

    def test_short_secret_key_is_refused(self) -> None:
        with pytest.raises(InsecureSecretError, match="at least 32"):
            _settings(SECRET_KEY="tooshort")

    def test_env_example_placeholder_is_refused(self) -> None:
        """The literal value shipped in ``.env.example``.

        It is 44 characters, so length alone lets it through — which is
        why the placeholder list exists.
        """
        with pytest.raises(InsecureSecretError, match="placeholder"):
            _settings(SECRET_KEY="your_secret_key_here_use_openssl_rand_hex_32")

    def test_repeated_character_secret_is_refused(self) -> None:
        with pytest.raises(InsecureSecretError, match="distinct characters"):
            _settings(SECRET_KEY="a" * 64)

    def test_unset_budget_secret_is_refused(self) -> None:
        """Empty means it silently falls back to SECRET_KEY (ADR 0006)."""
        with pytest.raises(InsecureSecretError, match="BUDGET_PUBLIC_SECRET_KEY is unset"):
            _settings(BUDGET_PUBLIC_SECRET_KEY="")

    def test_budget_secret_equal_to_secret_key_is_refused(self) -> None:
        with pytest.raises(InsecureSecretError, match="identical"):
            _settings(BUDGET_PUBLIC_SECRET_KEY=GOOD)

    def test_weak_budget_secret_is_refused(self) -> None:
        with pytest.raises(InsecureSecretError, match="BUDGET_PUBLIC_SECRET_KEY"):
            _settings(BUDGET_PUBLIC_SECRET_KEY="changeme_changeme_changeme_changeme")


class TestNonProductionIsUnaffected:
    """Development and the test suite run on throwaway keys by design."""

    @pytest.mark.parametrize("environment", ["development", "test"])
    def test_weak_secrets_are_allowed_outside_production(self, environment: str) -> None:
        settings = _settings(
            ENVIRONMENT=environment,
            SECRET_KEY="dev",
            BUDGET_PUBLIC_SECRET_KEY="",
        )
        assert settings.SECRET_KEY == "dev"
