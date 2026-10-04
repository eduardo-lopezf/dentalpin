"""What a dental clinical record is expected to hold, checked against one.

The list is this product's reading of NOM-004-SSA3-2012 for a dental
practice, in the scope the clinic chose: the dental record, plus family
history and prognosis. The systems review and laboratory results of a
general *historia clínica* are out of it.

**An engineering reading, pending legal review** — and a check of
*presence*, not of quality: it can say no diagnosis is written down, never
that the one written is right. "Not met" also covers "never asked": the
record cannot tell a patient with no family history from one nobody asked,
until somebody writes the answer down.

Sections are matched by name. The record still imports no contributing
module; a section that is absent — its module is off — simply leaves its
requirement unmet.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.core.record import RecordEntry

Sections = dict[str, list[RecordEntry]]

#: What identifies a patient in a record, beyond the name.
_IDENTITY_FIELDS = ("date_of_birth", "gender", "address")

_PERSONAL_HISTORY = (
    "patients_clinical.health_questionnaires",
    "patients_clinical.medical_context",
    "patients_clinical.allergies",
    "patients_clinical.medications",
    "patients_clinical.systemic_diseases",
    "patients_clinical.surgical_history",
)


@dataclass(frozen=True, slots=True)
class Requirement:
    key: str
    met: bool
    #: For a requirement met in part: which of its fields are empty.
    missing: list[str] = field(default_factory=list)


def _identification(sections: Sections) -> Requirement:
    entries = sections.get("patients.identification") or []
    if not entries:
        return Requirement("identification", False, list(_IDENTITY_FIELDS))
    missing = [name for name in _IDENTITY_FIELDS if not entries[0].detail.get(name)]
    return Requirement("identification", not missing, missing)


def _any(key: str, *names: str) -> Callable[[Sections], Requirement]:
    return lambda sections: Requirement(key, any(sections.get(name) for name in names))


def _plans_with(key: str, detail_key: str) -> Callable[[Sections], Requirement]:
    def check(sections: Sections) -> Requirement:
        plans = sections.get("treatment_plan.plans") or []
        return Requirement(key, any(plan.detail.get(detail_key) for plan in plans))

    return check


def _chief_complaint(sections: Sections) -> Requirement:
    """Why the patient came, as a health questionnaire records it."""
    asked = any(
        entry.detail.get("chief_complaint")
        for entry in sections.get("patients_clinical.health_questionnaires") or []
    )
    return Requirement("chief_complaint", asked)


def _diagnosis(sections: Sections) -> Requirement:
    """Written on a plan, or left as a diagnosis note."""
    noted = any(
        note.detail.get("note_type") == "diagnosis"
        for note in sections.get("clinical_notes.notes") or []
    )
    return Requirement(
        "diagnosis", noted or _plans_with("diagnosis", "diagnosis_notes")(sections).met
    )


def _informed_consent(sections: Sections) -> Requirement:
    signed = any(
        entry.detail.get("kind") == "informed" and entry.detail.get("status") == "signed"
        for entry in sections.get("consents.consents") or []
    )
    return Requirement("informed_consent", signed)


_CHECKS: tuple[Callable[[Sections], Requirement], ...] = (
    _identification,
    _chief_complaint,
    _any("family_history", "patients_clinical.family_history"),
    _any("personal_history", *_PERSONAL_HISTORY),
    _any("dental_chart", "odontogram.chart"),
    _diagnosis,
    _plans_with("prognosis", "prognosis"),
    _any("therapeutic_plan", "treatment_plan.plans"),
    _any("evolution_notes", "clinical_notes.notes"),
    _informed_consent,
)


def requirement_keys() -> list[str]:
    """Every requirement, by key, in the order a record reads."""
    return [requirement({}).key for requirement in _CHECKS]


def check(sections: Sections) -> list[Requirement]:
    """One answer per requirement, in the order a record reads."""
    return [requirement(sections) for requirement in _CHECKS]
