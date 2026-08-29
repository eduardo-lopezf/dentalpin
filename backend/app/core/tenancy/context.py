"""Immutable tenant context.

A ``TenantContext`` describes the DB-isolation unit for a request, job, or
CLI invocation. In self-hosted there is exactly one tenant (``"default"``);
in a future SaaS deployment there are N, one per subscription.

``clinic_id`` is intentionally NOT part of this context — that lives in
``ClinicContext`` (``app.core.auth.dependencies``). Tenant isolates DB,
clinic isolates rows within a DB.

The tenant is also where custody lives: ``privacy`` says whether an
operator of this deployment can reach the data at all, and under which
jurisdiction and regime it is held (ADR 0023). That is a property of the
deployment, not of a request or a clinic, which is why it sits here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any

from app.core.privacy import PrivacyPolicy

_EMPTY_METADATA: Mapping[str, Any] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Inmutable description of a tenant.

    ``metadata`` is opaque to core. SaaS modules can store arbitrary
    information (plan, cluster_id, etc.) and define their own TypedDict to
    cast at read time. ``privacy`` is the opposite: core enforces it, so
    it is a typed field rather than a metadata key.
    """

    slug: str
    db_url: str
    # Required, and deliberately without a default. A tenant that does not
    # state its custody would have to be assumed into one, and the only
    # assumption available (``self``) is the dangerous one: it claims no
    # operator can reach the data. Explicit, never implicit — the same
    # rule ADR 0012 applies to the tenant itself.
    privacy: PrivacyPolicy
    storage_prefix: str = ""
    modules_enabled: frozenset[str] = frozenset()
    metadata: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_METADATA, hash=False)

    def __post_init__(self) -> None:
        if not self.db_url:
            raise ValueError("TenantContext.db_url cannot be empty")
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def with_metadata(self, **kwargs: Any) -> TenantContext:
        """Return a copy with ``metadata`` extended by ``kwargs``."""
        merged: dict[str, Any] = {**self.metadata, **kwargs}
        return replace(self, metadata=MappingProxyType(merged))
