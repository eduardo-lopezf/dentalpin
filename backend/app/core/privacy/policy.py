"""Who can reach a tenant's data, and under what rules.

``PrivacyPolicy`` is the declarative answer to two questions that the rest
of the codebase keeps answering ad-hoc:

1. **Custody** — can the people who operate the deployment read the
   clinical data? The answer is not a permission (an operator with a
   database shell bypasses RBAC entirely); it follows from who runs the
   deployment and who holds the encryption keys.
2. **Regime** — which jurisdiction's documents and which regulator's
   obligations apply? Today this is hardcoded field by field: the ID keys
   the copilot redactor tokenizes, the document types
   ``Patient.national_id_type`` accepts, the tax-id labels in the Spanish
   locale. Each of those should read one policy instead of carrying its
   own opinion.

The policy is **data, not behaviour**. It declares; enforcement lives in
whatever component the declaration constrains. Only ``jurisdictions`` has
an enforcer today (the copilot's PHI boundary); the custody fields are
introduced ahead of theirs so that the seam exists before the first SaaS
tenant does (see ADR 0023, and ADR 0012 for the tenancy model it hangs
off).

Deliberately *not* modelled here: retention windows, consent purposes and
erasure semantics. They vary per regulation rather than per custody mode,
and adding fields no component reads would be guessing at the shape of an
enforcer that does not exist. They join the policy with the module that
enforces them.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

_JURISDICTION_RE = re.compile(r"^[A-Z]{2}$")


class CustodyMode(StrEnum):
    """Who runs the deployment and who holds its keys.

    The three modes are the three combinations of operator access and key
    custody that DentalPin supports. A fourth combination is a new mode,
    not a new flag — which is why :class:`PrivacyPolicy` stores the mode
    and derives the other two.
    """

    SELF = "self"
    """The customer runs the deployment. There is no operator to grant
    access to: whoever holds the server holds the data. We supply
    software and nothing else — no data processing agreement, because no
    processing happens on our side.

    The only mode whose guarantee holds today, because it is an absence
    rather than a control. Commercially it is the *most* expensive option
    for the clinic — they carry the infrastructure, the backups and the
    upgrades — and how it is offered is pending the business model."""

    MANAGED = "managed"
    """We run the deployment and hold its keys — the default, and what
    this product is. We are a data processor, and operator access to
    clinical data is meant to be break-glass only: bounded, justified,
    recorded and disclosed.

    **Not implemented.** There is no break-glass mechanism; an operator's
    access is standing. The mode states who holds what, which is true;
    it does not yet state an enforced control."""

    BYOK = "byok"
    """We run the deployment; the customer holds the keys in their own
    KMS. We operate the system — backups, migrations, support — without
    being able to read what the encrypted fields contain.

    **Out of scope for this stage.** It needs envelope encryption and
    per-field key metadata, neither of which exists. The mode is
    vocabulary, kept so the model is complete and so the day it is built
    is a wiring job rather than a redesign."""


class OperatorAccess(StrEnum):
    """Whether an operator of the deployment can reach clinical data."""

    NONE = "none"
    """No operator exists on our side. Not a promise not to look — an
    absence of any path to look through."""

    BREAK_GLASS = "break_glass"
    """Access exists but is not standing: it is opened per incident,
    expires, and leaves a record."""


class KeyCustody(StrEnum):
    """Who holds the key material that protects encrypted fields."""

    OPERATOR = "operator"
    """Keys live in the deployment we run."""

    CUSTOMER = "customer"
    """Keys live with the customer — their own deployment in ``SELF``,
    their own KMS in ``BYOK``."""


@dataclass(frozen=True, slots=True)
class BreakGlassPolicy:
    """Bounds on an operator access session.

    Only meaningful where :class:`OperatorAccess` is ``BREAK_GLASS``.
    These are the terms a clinic is asked to accept in the processing
    agreement, so they belong in the policy rather than in an operator
    runbook nobody outside the company reads.
    """

    max_duration_minutes: int = 60
    """A session expires on its own. An access grant that has to be
    revoked by hand is a standing grant with extra steps."""

    requires_reason: bool = True
    """The operator states why before the session opens, so the record
    says what the access was for and not merely that it happened."""

    notifies_customer: bool = True
    """The clinic is told the session opened. Access the customer only
    learns about by asking is not meaningfully bounded."""

    def __post_init__(self) -> None:
        if self.max_duration_minutes <= 0:
            raise ValueError("BreakGlassPolicy.max_duration_minutes must be positive")


@dataclass(frozen=True, slots=True)
class PrivacyPolicy:
    """The custody and regime rules that apply to one tenant.

    Immutable and hashable, like the :class:`~app.core.tenancy.TenantContext`
    it hangs off. Build one through :meth:`self_hosted`, :meth:`managed`
    or :meth:`byok` rather than by hand — the constructors carry the
    defaults each mode implies.
    """

    custody_mode: CustodyMode
    jurisdictions: frozenset[str]
    """ISO 3166-1 alpha-2 codes of the countries whose documents and tax
    identifiers apply. Drives vocabulary (a CURP in ``MX``, a DNI in
    ``ES``), not obligations."""

    regulations: frozenset[str]
    """Lower-case identifiers of the regimes the tenant answers to
    (``"lfpdppp"``, ``"gdpr"``, ``"lopdgdd"``, ``"hipaa"``). Drives
    obligations. Kept separate from ``jurisdictions`` because the two do
    not map one-to-one: a Spanish clinic answers to both GDPR and
    LOPDGDD, and a regime can follow the data across borders."""

    data_residency: str
    """Where the data may physically live — a region identifier
    (``"mx-central"``, ``"eu-west"``) or ``"on-prem"``."""

    egress_allowed: frozenset[str] = frozenset()
    """Named external destinations this tenant's data may reach
    (``"openai"``, ``"kapso"``, ``"aeat"``). Default-deny: a destination
    absent from the set is not permitted. Every module that sends data
    off-premises is one of these names."""

    break_glass: BreakGlassPolicy | None = None
    """Terms of operator access. Always ``None`` under ``SELF`` (there is
    nothing to bound) and always set otherwise — filled with the default
    terms when a caller omits it."""

    def __post_init__(self) -> None:
        for code in self.jurisdictions:
            if not _JURISDICTION_RE.match(code):
                raise ValueError(
                    f"PrivacyPolicy.jurisdictions expects ISO 3166-1 alpha-2 codes, got {code!r}"
                )
        if not self.jurisdictions:
            raise ValueError("PrivacyPolicy.jurisdictions cannot be empty")
        if not self.data_residency:
            raise ValueError("PrivacyPolicy.data_residency cannot be empty")

        if self.custody_mode is CustodyMode.SELF:
            if self.break_glass is not None:
                # Declaring bounded operator access on a deployment we do
                # not run would describe a control that cannot exist.
                raise ValueError("PrivacyPolicy: custody_mode 'self' cannot carry a break_glass")
        elif self.break_glass is None:
            object.__setattr__(self, "break_glass", BreakGlassPolicy())

    # --- derived ---------------------------------------------------------

    @property
    def operator_access(self) -> OperatorAccess:
        if self.custody_mode is CustodyMode.SELF:
            return OperatorAccess.NONE
        return OperatorAccess.BREAK_GLASS

    @property
    def key_custody(self) -> KeyCustody:
        if self.custody_mode is CustodyMode.MANAGED:
            return KeyCustody.OPERATOR
        return KeyCustody.CUSTOMER

    def allows_egress(self, target: str) -> bool:
        """Whether this tenant's data may reach ``target``."""
        return target in self.egress_allowed

    # --- constructors ----------------------------------------------------

    @classmethod
    def self_hosted(
        cls,
        *,
        jurisdictions: frozenset[str] = frozenset({"MX"}),
        regulations: frozenset[str] = frozenset({"lfpdppp"}),
        data_residency: str = "on-prem",
        egress_allowed: frozenset[str] = frozenset(),
    ) -> PrivacyPolicy:
        """The default for a deployment the customer runs themselves."""
        return cls(
            custody_mode=CustodyMode.SELF,
            jurisdictions=jurisdictions,
            regulations=regulations,
            data_residency=data_residency,
            egress_allowed=egress_allowed,
        )

    @classmethod
    def managed(
        cls,
        *,
        jurisdictions: frozenset[str],
        regulations: frozenset[str],
        data_residency: str,
        egress_allowed: frozenset[str] = frozenset(),
        break_glass: BreakGlassPolicy | None = None,
    ) -> PrivacyPolicy:
        """A deployment we run and hold the keys for."""
        return cls(
            custody_mode=CustodyMode.MANAGED,
            jurisdictions=jurisdictions,
            regulations=regulations,
            data_residency=data_residency,
            egress_allowed=egress_allowed,
            break_glass=break_glass,
        )

    @classmethod
    def byok(
        cls,
        *,
        jurisdictions: frozenset[str],
        regulations: frozenset[str],
        data_residency: str,
        egress_allowed: frozenset[str] = frozenset(),
        break_glass: BreakGlassPolicy | None = None,
    ) -> PrivacyPolicy:
        """A deployment we run against keys the customer holds."""
        return cls(
            custody_mode=CustodyMode.BYOK,
            jurisdictions=jurisdictions,
            regulations=regulations,
            data_residency=data_residency,
            egress_allowed=egress_allowed,
            break_glass=break_glass,
        )


REGULATIONS_BY_JURISDICTION: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "MX": ("lfpdppp",),
        "ES": ("gdpr", "lopdgdd"),
    }
)
"""Default regimes a clinic operating in a country answers to.

A *default*, not an identity: the two axes stay separate fields because
they do not map one-to-one — Spain yields two regimes from one
jurisdiction, and a regime can follow the data across a border. This map
saves a deployment from restating the obvious; a control plane that knows
better sets ``regulations`` directly.
"""


def regulations_for(jurisdictions: frozenset[str]) -> frozenset[str]:
    """Regimes implied by a set of jurisdictions, per the map above."""
    implied: set[str] = set()
    for code in jurisdictions:
        implied.update(REGULATIONS_BY_JURISDICTION.get(code, ()))
    return frozenset(implied)


SELF_HOSTED_POLICY: Final = PrivacyPolicy.self_hosted()
"""Precomputed default for single-tenant deployments.

Safe to share: the policy is frozen and hashable, so this is a value, not
shared mutable state.
"""
