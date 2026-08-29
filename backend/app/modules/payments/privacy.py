"""What this module answers when a patient exercises their rights.

Cobros, sus asignaciones a facturas, el histórico y las devoluciones.
Documentos contables, con la misma excepción fiscal que las facturas.

See ``app.core.privacy.subject`` and ADR 0026.
"""

from __future__ import annotations

from app.core.privacy import ChildLink, SubjectContributor, patient_keyed_export

from .models import (
    PatientEarnedEntry,
    Payment,
    PaymentAllocation,
    PaymentHistory,
    Refund,
)

FISCAL_RETENTION = (
    "Los cobros y devoluciones son documentos contables: su conservación "
    "la fija la normativa tributaria, que no cede ante una solicitud de "
    "supresión."
)


def get_subject_contributors() -> list[SubjectContributor]:
    return [
        SubjectContributor(
            name="payments",
            export=patient_keyed_export(
                Payment,
                ChildLink(PaymentAllocation, "payment_id"),
                ChildLink(PaymentHistory, "payment_id"),
                ChildLink(Refund, "payment_id"),
            ),
            retention_reason=FISCAL_RETENTION,
        ),
        SubjectContributor(
            name="earned_entries",
            export=patient_keyed_export(PatientEarnedEntry),
            retention_reason=FISCAL_RETENTION,
        ),
    ]
