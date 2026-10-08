"""What the catalog offers other modules without being imported (ADR 0039)."""

from __future__ import annotations

from app.core.contracts import ReferenceSpecialty

from .seed import all_specialties

#: The discipline no clinic is created without: general dentistry is what
#: the Treatments App is, before any speciality is added to it.
REQUIRED_SPECIALTIES = frozenset({"general"})


class CatalogReferenceSpecialties:
    def available(self) -> list[ReferenceSpecialty]:
        return [
            ReferenceSpecialty(
                key=specialty["key"],
                names=specialty["names"],
                required=specialty["key"] in REQUIRED_SPECIALTIES,
            )
            for specialty in all_specialties()
        ]


specialties = CatalogReferenceSpecialties()
