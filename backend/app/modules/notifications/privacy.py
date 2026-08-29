"""What this module answers when a patient exercises their rights.

Los mensajes enviados al paciente y sus preferencias de contacto. No son
registro asistencial ni contable: nada obliga a conservarlos, así que se
borran.

Dos columnas cargan la identidad y ninguna de las dos la lleva en el
nombre. ``to_address`` guarda el email o el teléfono del destinatario
—clasificada como ``CONTACT`` justo por esto— y ``body_text`` es el
mensaje ya renderizado ("Hola Ana, te recordamos tu cita…"), así que
lleva el nombre dentro aunque ninguna clasificación de columna pueda
verlo. Las dos se van con la supresión.

See ``app.core.privacy.subject`` and ADR 0026.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.privacy import (
    SubjectContributor,
    anonymize_instance,
    patient_keyed_export,
)

from .models import CommunicationMessage, NotificationPreference


async def _anonymize_messages(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> int:
    result = await db.execute(
        select(CommunicationMessage).where(
            CommunicationMessage.clinic_id == clinic_id,
            CommunicationMessage.patient_id == patient_id,
        )
    )
    scrubbed = 0
    for message in result.scalars().all():
        scrubbed += anonymize_instance(message)
        if message.body_text is not None:
            message.body_text = None
            scrubbed += 1
    return scrubbed


async def _anonymize_preferences(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> int:
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.clinic_id == clinic_id,
            NotificationPreference.patient_id == patient_id,
        )
    )
    return sum(anonymize_instance(row) for row in result.scalars().all())


def get_subject_contributors() -> list[SubjectContributor]:
    return [
        SubjectContributor(
            name="messages",
            export=patient_keyed_export(CommunicationMessage),
            anonymize=_anonymize_messages,
        ),
        SubjectContributor(
            name="contact_preferences",
            export=patient_keyed_export(NotificationPreference),
            anonymize=_anonymize_preferences,
        ),
    ]
