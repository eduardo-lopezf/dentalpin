"""Single-tenant resolver for self-hosted deployments.

Reads ``DATABASE_URL`` and the ``ModuleRegistry`` exactly once at
construction time and returns the same ``TenantContext`` on every call.
O(1), no network, no cache (precomputed).
"""

from __future__ import annotations

import logging
from typing import Final

from starlette.requests import Request

from app.config import settings
from app.core.plugins.registry import module_registry
from app.core.privacy import CustodyMode, PrivacyPolicy
from app.core.privacy.policy import regulations_for

from .context import TenantContext

logger = logging.getLogger(__name__)

DEFAULT_TENANT_SLUG = "default"

_SELF_HOSTED_RESIDENCY = "on-prem"
_UNSPECIFIED_RESIDENCY = "unspecified"

# Modes whose controls the codebase does not implement yet (ADR 0023).
# The mode still describes who holds what accurately; it does not yet
# describe an enforced control, and a deployment should be reminded of
# that on every boot rather than discovering it during an audit.
_UNENFORCED_MODES: Final[dict[CustodyMode, str]] = {
    CustodyMode.MANAGED: (
        "break-glass operator access is not implemented; operator access is currently standing"
    ),
    CustodyMode.BYOK: (
        "customer-held keys are not implemented; this stage has no envelope encryption"
    ),
}


class CustodyConfigError(RuntimeError):
    """The deployment's custody settings do not describe a real situation."""


def policy_from_settings() -> PrivacyPolicy:
    """Build this deployment's :class:`PrivacyPolicy` from configuration.

    ``managed`` is the default because that is what this product is: we
    run the deployment and hold its keys. The failure mode of that default
    is an over-statement — a self-hoster who never sets the variable
    reports operator access that nobody actually has — which is the
    direction to err in. The opposite default would have an operated
    deployment silently reporting ``self``, claiming a privacy guarantee
    it cannot give.

    An unrecognised mode is refused rather than defaulted: picking a
    custody claim on the operator's behalf is exactly what this function
    must not do.
    """
    raw_mode = settings.TENANT_CUSTODY_MODE.strip().lower()
    try:
        mode = CustodyMode(raw_mode)
    except ValueError:
        accepted = ", ".join(m.value for m in CustodyMode)
        raise CustodyConfigError(
            f"TENANT_CUSTODY_MODE must be one of: {accepted} (got {raw_mode!r})"
        ) from None

    jurisdictions = frozenset(
        code.strip().upper() for code in settings.TENANT_JURISDICTIONS.split(",") if code.strip()
    )
    if not jurisdictions:
        raise CustodyConfigError("TENANT_JURISDICTIONS cannot be empty")

    residency = settings.TENANT_DATA_RESIDENCY.strip()
    if not residency:
        if mode is CustodyMode.SELF:
            # True by definition: under ``self`` the customer's premises
            # are wherever they chose to run it.
            residency = _SELF_HOSTED_RESIDENCY
        else:
            residency = _UNSPECIFIED_RESIDENCY
            logger.warning(
                "TENANT_DATA_RESIDENCY is unset under custody mode %r; "
                "reporting %r rather than guessing a location",
                mode.value,
                _UNSPECIFIED_RESIDENCY,
            )

    gap = _UNENFORCED_MODES.get(mode)
    if gap is not None:
        logger.warning("Custody mode %r declares more than the code enforces: %s", mode.value, gap)

    egress_allowed = frozenset(
        target.strip().lower()
        for target in settings.TENANT_EGRESS_ALLOWED.split(",")
        if target.strip()
    )

    builder = {
        CustodyMode.SELF: PrivacyPolicy.self_hosted,
        CustodyMode.MANAGED: PrivacyPolicy.managed,
        CustodyMode.BYOK: PrivacyPolicy.byok,
    }[mode]
    return builder(
        jurisdictions=jurisdictions,
        regulations=regulations_for(jurisdictions),
        data_residency=residency,
        egress_allowed=egress_allowed,
    )


class SingleTenantResolver:
    """Resolver that always returns the same tenant.

    The tenant is built once from ``settings.DATABASE_URL`` and the set of
    modules currently loaded in the ``ModuleRegistry``. Subsequent
    ``resolve()`` / ``resolve_by_slug()`` calls return the cached instance.
    """

    def __init__(self) -> None:
        self._context = TenantContext(
            slug=DEFAULT_TENANT_SLUG,
            db_url=settings.DATABASE_URL,
            storage_prefix="",
            modules_enabled=frozenset(module.name for module in module_registry.list_modules()),
            privacy=policy_from_settings(),
        )

    async def resolve(self, request: Request) -> TenantContext:
        logger.debug("SingleTenantResolver.resolve ignoring request")
        return self._context

    async def resolve_by_slug(self, slug: str) -> TenantContext:
        if slug != DEFAULT_TENANT_SLUG:
            raise LookupError(f"Unknown tenant slug: {slug!r}")
        return self._context
