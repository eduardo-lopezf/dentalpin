"""Tests for ``SingleTenantResolver`` (multi-tenancy Fase 1)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request

from app.core.privacy import CustodyMode, KeyCustody
from app.core.tenancy import (
    SingleTenantResolver,
    TenantContext,
    TenantResolver,
    get_tenant,
)
from app.core.tenancy.single import DEFAULT_TENANT_SLUG, policy_from_settings


@pytest.fixture
def fake_request() -> Request:
    """Minimal ASGI scope; the resolver never actually inspects it."""
    return Request(scope={"type": "http", "headers": []})


@pytest.fixture
def resolver(monkeypatch: pytest.MonkeyPatch) -> SingleTenantResolver:
    """Build a resolver with the registry mocked to a known module set.

    Keeps the assertion stable regardless of how many modules conftest
    happens to load.
    """
    m1 = MagicMock()
    m1.name = "patients"
    m2 = MagicMock()
    m2.name = "agenda"
    fake_registry = MagicMock()
    fake_registry.list_modules.return_value = [m1, m2]
    monkeypatch.setattr("app.core.tenancy.single.module_registry", fake_registry)
    return SingleTenantResolver()


class TestResolve:
    @pytest.mark.asyncio
    async def test_returns_tenant_context(
        self, resolver: SingleTenantResolver, fake_request: Request
    ) -> None:
        ctx = await resolver.resolve(fake_request)
        assert isinstance(ctx, TenantContext)
        assert ctx.slug == DEFAULT_TENANT_SLUG

    @pytest.mark.asyncio
    async def test_returns_same_instance_each_call(
        self, resolver: SingleTenantResolver, fake_request: Request
    ) -> None:
        a = await resolver.resolve(fake_request)
        b = await resolver.resolve(fake_request)
        assert a is b

    @pytest.mark.asyncio
    async def test_modules_enabled_from_registry(
        self, resolver: SingleTenantResolver, fake_request: Request
    ) -> None:
        ctx = await resolver.resolve(fake_request)
        assert ctx.modules_enabled == frozenset({"patients", "agenda"})

    @pytest.mark.asyncio
    async def test_carries_the_configured_custody_policy(
        self, resolver: SingleTenantResolver, fake_request: Request
    ) -> None:
        # The resolver does not decide custody; it reads what the
        # deployment declared. ``managed`` is the default (ADR 0023).
        # Whether the mode's controls exist is a separate question —
        # see ``tests/test_custody_settings.py``.
        ctx = await resolver.resolve(fake_request)
        assert ctx.privacy.custody_mode is CustodyMode.MANAGED
        assert ctx.privacy.key_custody is KeyCustody.OPERATOR
        # Default-deny holds whatever the mode: nothing has declared an
        # external destination for this tenant.
        assert not ctx.privacy.allows_egress("openai")


class TestResolveBySlug:
    @pytest.mark.asyncio
    async def test_default_slug_works(self, resolver: SingleTenantResolver) -> None:
        ctx = await resolver.resolve_by_slug(DEFAULT_TENANT_SLUG)
        assert ctx.slug == DEFAULT_TENANT_SLUG

    @pytest.mark.asyncio
    async def test_unknown_slug_raises_lookuperror(self, resolver: SingleTenantResolver) -> None:
        with pytest.raises(LookupError, match="Unknown tenant slug"):
            await resolver.resolve_by_slug("other")

    @pytest.mark.asyncio
    async def test_default_and_resolve_return_same(
        self, resolver: SingleTenantResolver, fake_request: Request
    ) -> None:
        via_request = await resolver.resolve(fake_request)
        via_slug = await resolver.resolve_by_slug(DEFAULT_TENANT_SLUG)
        assert via_request is via_slug


class TestProtocolConformance:
    def test_satisfies_runtime_protocol(self, resolver: SingleTenantResolver) -> None:
        assert isinstance(resolver, TenantResolver)


class TestGetTenantDependency:
    """``get_tenant`` is how a request reaches the tenant's policy."""

    @pytest.mark.asyncio
    async def test_uses_the_resolver_installed_by_the_lifespan(self) -> None:
        sentinel = TenantContext(
            slug="default",
            db_url="postgresql+asyncpg://x/y",
            privacy=policy_from_settings(),
        )
        app = MagicMock()
        app.state.tenant_resolver = MagicMock()
        app.state.tenant_resolver.resolve = AsyncMock(return_value=sentinel)
        request = Request(scope={"type": "http", "headers": [], "app": app})

        assert await get_tenant(request) is sentinel

    @pytest.mark.asyncio
    async def test_falls_back_when_no_lifespan_ran(self) -> None:
        # Test harnesses mount the ASGI app directly, so a missing
        # resolver is expected. The fallback builds the same resolver the
        # lifespan would, so a test sees the deployment's real custody
        # rather than a friendlier stand-in.
        app = MagicMock()
        del app.state.tenant_resolver
        request = Request(scope={"type": "http", "headers": [], "app": app})

        ctx = await get_tenant(request)
        assert ctx.slug == DEFAULT_TENANT_SLUG
        assert ctx.privacy == policy_from_settings()

    @pytest.mark.asyncio
    async def test_fallback_is_not_cached_onto_app_state(self) -> None:
        # Caching it would freeze a registry snapshot taken before the
        # modules mounted.
        app = MagicMock()
        del app.state.tenant_resolver
        request = Request(scope={"type": "http", "headers": [], "app": app})

        await get_tenant(request)
        assert not hasattr(app.state, "tenant_resolver")
