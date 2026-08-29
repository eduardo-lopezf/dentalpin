"""FastAPI dependency that resolves the tenant for a request.

This is the *read* half of ADR 0012 Fase 2a. It exposes the tenant — and
with it the tenant's :class:`~app.core.privacy.PrivacyPolicy` (ADR 0023) —
to endpoints that need to know under which custody and jurisdiction they
are running. It deliberately does **not** touch ``get_db``: routing the
session through a per-tenant engine pool is the invasive half and stays
unmerged until the whole suite is green against it.
"""

from __future__ import annotations

from starlette.requests import Request

from .context import TenantContext
from .resolver import TenantResolver
from .single import SingleTenantResolver


async def get_tenant(request: Request) -> TenantContext:
    """Resolve the tenant through ``app.state.tenant_resolver``.

    The lifespan installs the resolver once modules are mounted, so
    ``modules_enabled`` reflects the active set. Test harnesses mount the
    ASGI app directly and never run the lifespan, so a missing resolver
    is expected rather than an error: build the same one the lifespan
    would, which costs a frozenset over the registry. Deliberately not a
    friendlier stand-in — a test that saw a different custody mode from
    production would be testing something that never runs.

    The fallback is not cached onto ``app.state`` on purpose — doing so
    would freeze a registry snapshot taken before the modules mounted.
    """
    resolver: TenantResolver | None = getattr(request.app.state, "tenant_resolver", None)
    if resolver is None:
        resolver = SingleTenantResolver()
    return await resolver.resolve(request)
