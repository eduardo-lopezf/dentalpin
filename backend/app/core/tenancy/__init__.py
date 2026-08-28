"""Tenant context and resolution interfaces.

See ``docs/technical/multi-tenancy.md`` for the architectural overview.
"""

from .context import TenantContext
from .dependencies import get_tenant
from .resolver import TenantResolver
from .single import SingleTenantResolver

__all__ = ["TenantContext", "TenantResolver", "SingleTenantResolver", "get_tenant"]
