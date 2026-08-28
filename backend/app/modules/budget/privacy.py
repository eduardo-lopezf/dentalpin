"""What this module answers when a patient exercises their rights.

Un presupuesto es una **oferta precontractual**, no un documento fiscal:
mientras no se factura, nada obliga a conservarlo. Por eso este módulo sí
borra, a diferencia de ``billing``.

La firma es lo que de verdad identifica: ``budget_signatures`` guarda el
nombre y el email de quien aceptó, y son las únicas columnas clasificadas
del módulo. Se van con ``anonymize_instance``; el resto (importes,
partidas, histórico) queda como registro comercial anónimo.

See ``app.core.privacy.subject`` and ADR 0026.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.privacy import (
    ChildLink,
    SubjectContributor,
    patient_keyed_anonymize,
    patient_keyed_export,
)

from .models import Budget, BudgetHistory, BudgetItem, BudgetSignature

_LINKS = (
    ChildLink(BudgetItem, "budget_id"),
    ChildLink(BudgetHistory, "budget_id"),
    ChildLink(BudgetSignature, "budget_id"),
)

# Free text a clinic writes about the patient. Not clinical record and
# not fiscal, so it goes with the erasure — and it is the field most
# likely to carry a name the classification cannot see.
_FREE_TEXT = ("internal_notes", "patient_notes", "rejection_note")

_scrub_classified = patient_keyed_anonymize(Budget, *_LINKS)
_export = patient_keyed_export(Budget, *_LINKS)


async def _anonymize(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> int:
    from sqlalchemy import select

    scrubbed = await _scrub_classified(db, clinic_id, patient_id)
    result = await db.execute(
        select(Budget).where(Budget.clinic_id == clinic_id, Budget.patient_id == patient_id)
    )
    for budget in result.scalars().all():
        for column in _FREE_TEXT:
            if getattr(budget, column) is not None:
                setattr(budget, column, None)
                scrubbed += 1
    return scrubbed


def get_subject_contributors() -> list[SubjectContributor]:
    return [
        SubjectContributor(
            name="budgets",
            export=_export,
            anonymize=_anonymize,
        ),
    ]
