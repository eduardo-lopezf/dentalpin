"""Where a module sends data, declared in its manifest.

``PrivacyPolicy.egress_allowed`` has been default-deny since ADR 0023 and
has had nothing to compare against: the policy could say a tenant may
reach OpenAI, but nothing in the codebase said which modules reach
anything at all. That answer lived in three places — the provider factory
in `copilot`, an adapter in `whatsapp_kapso`, a submission queue in
`verifactu` — and in a clinic's data-processing agreement, maintained by
hand and out of date the moment a module was added.

So a module declares it, next to everything else it declares:

    manifest = {
        "egress": [
            {
                "target": "openai",
                "subprocessor": "OpenAI, L.L.C.",
                "residency": "us",
                "data_classes": ["identifier", "clinical"],
                "purpose": "Copilot conversational responses.",
            }
        ],
    }

Two things fall out of that. A boot-time audit can name every module
whose destination the tenant has not permitted, and the subprocessor
register a clinic needs for its DPA can be **generated** rather than
remembered.

What this does *not* do yet is block the call — see ADR 0027.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .classification import DataClass
from .policy import PrivacyPolicy


@dataclass(frozen=True, slots=True)
class EgressDeclaration:
    """One external destination a module sends data to."""

    target: str
    """Short stable id matched against ``PrivacyPolicy.egress_allowed``:
    ``"openai"``, ``"kapso"``, ``"aeat"``. Lower-case, no spaces."""

    subprocessor: str
    """Legal name of whoever receives the data, as it must appear in a
    processing agreement. ``"OpenAI, L.L.C."``, not ``"OpenAI"``."""

    purpose: str
    """Why the data leaves, in a sentence a clinic can show a patient."""

    data_classes: frozenset[DataClass] = frozenset()
    """What kinds of data reach this destination. Empty means the module
    calls out without sending anything personal — a licence check, a
    health probe."""

    residency: str = "unspecified"
    """Where the receiving party processes it — a region id, or
    ``"unspecified"`` when the vendor does not commit to one."""

    required: bool = True
    """``False`` when the module works without this destination, so a
    tenant that forbids it loses a feature rather than the module."""

    def __post_init__(self) -> None:
        for field_name in ("target", "subprocessor", "purpose"):
            if not getattr(self, field_name).strip():
                raise EgressError(f"EgressDeclaration.{field_name} cannot be empty")
        if self.target != self.target.strip().lower() or " " in self.target:
            raise EgressError(
                f"EgressDeclaration.target must be a lower-case id with no spaces, "
                f"got {self.target!r}"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, module: str) -> EgressDeclaration:
        if not isinstance(data, dict):
            raise EgressError(f"egress entries must be dicts in module '{module}'")

        missing = [k for k in ("target", "subprocessor", "purpose") if not data.get(k)]
        if missing:
            raise EgressError(f"egress entry in module '{module}' is missing: {missing}")

        classes = set()
        for raw in data.get("data_classes") or ():
            try:
                classes.add(DataClass(raw))
            except ValueError as exc:
                accepted = ", ".join(c.value for c in DataClass)
                raise EgressError(
                    f"Unknown data_class {raw!r} in module '{module}' egress (accepted: {accepted})"
                ) from exc

        return cls(
            target=str(data["target"]),
            subprocessor=str(data["subprocessor"]),
            purpose=str(data["purpose"]),
            data_classes=frozenset(classes),
            residency=str(data.get("residency") or "unspecified"),
            required=bool(data.get("required", True)),
        )

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "subprocessor": self.subprocessor,
            "purpose": self.purpose,
            "data_classes": sorted(c.value for c in self.data_classes),
            "residency": self.residency,
            "required": self.required,
        }

    @property
    def carries_personal_data(self) -> bool:
        return bool(self.data_classes)


class EgressError(ValueError):
    """Raised when an egress declaration is malformed."""


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EgressFinding:
    """A module reaching a destination the tenant has not permitted."""

    module: str
    declaration: EgressDeclaration

    @property
    def severity(self) -> str:
        """``"leak"`` when personal data is involved, ``"call"`` otherwise.

        The distinction matters to whoever reads the boot log: an
        undeclared licence check is untidy, an undeclared destination
        carrying clinical data is a disclosure the clinic has not agreed
        to.
        """
        return "leak" if self.declaration.carries_personal_data else "call"


def audit_egress(policy: PrivacyPolicy) -> list[EgressFinding]:
    """Every installed module's egress the policy does not permit.

    Reads ``module_registry.list_modules()`` so an uninstalled module is
    not reported — it sends nothing because it is not mounted (ADR 0018).
    """
    from app.core.plugins.registry import module_registry

    findings: list[EgressFinding] = []
    for module in module_registry.list_modules():
        for declaration in module.get_manifest().egress:
            if not policy.allows_egress(declaration.target):
                findings.append(EgressFinding(module=module.name, declaration=declaration))
    return findings


def log_egress_audit(policy: PrivacyPolicy) -> list[EgressFinding]:
    """Run the audit and say what it found, once, at boot.

    Deliberately a warning and not a refusal. ``egress_allowed`` is
    default-deny, so enforcing it today would silently unplug the copilot
    and stop appointment reminders on every deployment that has not yet
    declared anything — breaking working clinics to enforce a field
    nobody has filled in. The finding is the product for now; blocking
    waits until operators have had a release to declare (ADR 0027).
    """
    findings = audit_egress(policy)
    if not findings:
        logger.info("Egress audit: every declared destination is permitted by the policy")
        return findings

    for finding in findings:
        logger.warning(
            "Egress audit: module %r sends %s to %r (%s), which TENANT_EGRESS_ALLOWED "
            "does not permit [%s]",
            finding.module,
            sorted(c.value for c in finding.declaration.data_classes) or "no personal data",
            finding.declaration.target,
            finding.declaration.subprocessor,
            finding.severity,
        )
    return findings
