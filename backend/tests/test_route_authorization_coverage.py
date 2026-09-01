"""No mounted route serves without a declared permission.

ADR 0029, invariant 1. ``require_permission`` has always been sound;
what was never checked is its **coverage** — whether some route, in some
module, is mounted with no gate at all. The audit of 2026-07-03 found a
route whose permission check was present and whose *object* check was
missing (``tests/test_auth_create_user_scope.py``); this is the coarser
question asked of every route at once.

Two allowlists rather than one, because "nobody has to log in" and
"anybody logged in may read this" are different claims and collapsing
them hides the first inside the second. Each entry carries its reason,
and each is verified against the route rather than merely trusted: an
entry parked in the wrong bucket fails just as loudly as a missing gate.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.routing import APIRoute

from app.core.auth.dependencies import PERMISSION_MARKER
from app.main import app

# Routes reachable with no credentials at all.
UNAUTHENTICATED: dict[str, str] = {
    "GET /api/v1": "API root; announces the version and nothing else",
    "GET /health": "liveness probe, read by the container runtime",
    "GET /health/ready": "readiness probe, read by the container runtime",
    "GET /api/v1/auth/setup/status": "first-run wizard asks this before an account exists",
    "POST /api/v1/auth/setup": "creates the first account; self-closing, 409s afterwards",
    "POST /api/v1/auth/login": "issues the credentials everything else requires",
    "POST /api/v1/auth/refresh": "authorized by the refresh token it carries",
    # ADR 0006: possession of the token plus a knowledge factor, with
    # per-token lockout and an access log. Authorization is the token,
    # not a role — the patient has no account.
    "GET /api/v1/budget/public/budgets/{token}": "ADR 0006 public budget link",
    "GET /api/v1/budget/public/budgets/{token}/meta": "ADR 0006 public budget link",
    "POST /api/v1/budget/public/budgets/{token}/verify": "ADR 0006 knowledge factor",
    "GET /api/v1/budget/public/budgets/{token}/pdf/signed": "ADR 0006 public budget link",
    "POST /api/v1/budget/public/budgets/{token}/accept": "ADR 0006 patient decision",
    "POST /api/v1/budget/public/budgets/{token}/reject": "ADR 0006 patient decision",
    # Authorized, just not by a role: the payload is rejected unless it
    # carries a valid per-clinic HMAC signature.
    "POST /api/v1/whatsapp_kapso/webhook": "inbound webhook, verified by HMAC signature",
}

# Routes that require a valid user but no particular permission: what
# they return is either the caller's own context or already filtered by
# the caller's permissions.
AUTHENTICATED_ONLY: dict[str, str] = {
    "GET /api/v1/auth/me": "the caller's own profile",
    "GET /api/v1/auth/clinics": "returns the caller's own clinic, taken from the context",
    "GET /api/v1/auth/clinics/{clinic_id}": "403s when the id is not the caller's clinic",
    "GET /api/v1/modules/-/active": "sidebar inventory; nav entries filtered by permission",
}

ALLOWLISTED = UNAUTHENTICATED | AUTHENTICATED_ONLY


def _iter_api_routes(routes: list[Any], prefix: str = "") -> Iterator[tuple[str, APIRoute]]:
    """Yield ``("METHOD /path", route)`` for every mounted API route.

    Since FastAPI 0.141 ``app.routes`` holds lazy ``_IncludedRouter``
    wrappers rather than flat routes, so the included router has to be
    walked through its include context, accumulating prefixes. The
    generated OpenAPI schema — the approach in
    ``test_module_state_gating.py`` — gives paths but not the
    dependency tree this test is actually asking about.
    """
    for route in routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                yield f"{method} {prefix}{route.path}", route
        elif type(route).__name__ == "_IncludedRouter":
            ctx = route.include_context
            yield from _iter_api_routes(ctx.included_router.routes, prefix + (ctx.prefix or ""))


def _dependency_calls(dependant: Any) -> Iterator[Any]:
    for sub in dependant.dependencies:
        yield sub.call
        yield from _dependency_calls(sub)


def _declared_permissions(route: APIRoute) -> tuple[str, ...]:
    """Permissions gating ``route``, from either enforcement style.

    The dependency (``require_permission``) is the normal one. The
    marker on the handler (``declares_permissions``) covers the routes
    that must decide in the body because the permission depends on the
    object — see that decorator's docstring.
    """
    found: list[str] = list(getattr(route.endpoint, PERMISSION_MARKER, ()))
    for call in _dependency_calls(route.dependant):
        found.extend(getattr(call, PERMISSION_MARKER, ()))
    return tuple(found)


def _requires_authentication(route: APIRoute) -> bool:
    names = {getattr(c, "__name__", "") for c in _dependency_calls(route.dependant)}
    return bool(names & {"get_current_user", "get_clinic_context"})


ROUTES = sorted(_iter_api_routes(app.routes))


def test_the_app_under_test_actually_has_routes() -> None:
    """Guard against a green run that walked an empty app.

    ``conftest`` mounts every module at import; if that ever stops
    happening this file would pass by inspecting nothing.
    """
    assert len(ROUTES) > 300


@pytest.mark.parametrize("key,route", ROUTES, ids=[k for k, _ in ROUTES])
def test_route_declares_a_permission_or_is_allowlisted(key: str, route: APIRoute) -> None:
    if key in ALLOWLISTED:
        pytest.skip(f"allowlisted: {ALLOWLISTED[key]}")

    assert _declared_permissions(route), (
        f"{key} is mounted with no permission. Gate it with "
        f"require_permission('module.resource.action'), or — if the permission "
        f"depends on the object — enforce it in the body and say so with "
        f"@declares_permissions(...). Adding it to the allowlist in this file "
        f"is the last resort and needs a reason that survives review."
    )


@pytest.mark.parametrize("key", sorted(UNAUTHENTICATED), ids=sorted(UNAUTHENTICATED))
def test_unauthenticated_allowlist_entries_really_are_unauthenticated(key: str) -> None:
    """A gated route parked in the public bucket must not pass silently."""
    route = dict(ROUTES)[key]

    assert not _requires_authentication(route), (
        f"{key} is listed as unauthenticated but depends on the current user. "
        f"Move it to AUTHENTICATED_ONLY."
    )


@pytest.mark.parametrize("key", sorted(AUTHENTICATED_ONLY), ids=sorted(AUTHENTICATED_ONLY))
def test_authenticated_allowlist_entries_really_require_a_user(key: str) -> None:
    """The weaker bucket must not quietly become the public one."""
    route = dict(ROUTES)[key]

    assert _requires_authentication(route), (
        f"{key} is listed as authenticated-only but resolves no user, so it is "
        f"public. Either gate it or move it to UNAUTHENTICATED with a reason."
    )


def test_allowlists_have_no_stale_entries() -> None:
    """An allowlist that outlives its routes is where exemptions hide."""
    mounted = {key for key, _ in ROUTES}
    stale = sorted(set(ALLOWLISTED) - mounted)

    assert not stale, f"Allowlisted routes that are no longer mounted: {stale}"


def test_no_route_is_in_both_allowlists() -> None:
    overlap = sorted(set(UNAUTHENTICATED) & set(AUTHENTICATED_ONLY))

    assert not overlap, f"Listed in both buckets: {overlap}"
