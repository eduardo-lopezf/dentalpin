"""What this module answers when a patient exercises their rights.

A patient can always have a copy of what they signed. They cannot have it
erased: a consent letter is part of the clinical record, and it is the
clinic's proof that it informed and was authorised. Taking a consent back
is a **revocation**, which this module records — not an erasure.

See ``app.core.privacy.subject`` and ADR 0026.
"""

from __future__ import annotations

from app.core.privacy import SubjectContributor, patient_keyed_export

from .models import Consent

CONSENT_RETENTION = (
    "Las cartas de consentimiento forman parte del expediente clínico y son la "
    "constancia de que el paciente fue informado y autorizó: se conservan durante "
    "el plazo que fija la normativa sanitaria. Retirar un consentimiento se "
    "registra como revocación; no borra lo que se firmó."
)


def get_subject_contributors() -> list[SubjectContributor]:
    return [
        SubjectContributor(
            name="consents",
            export=patient_keyed_export(Consent),
            retention_reason=CONSENT_RETENTION,
        )
    ]
