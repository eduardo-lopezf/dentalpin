"""What this module answers when a patient exercises their rights.

Radiografías, fotos intraorales y documentos adjuntos. Parte del registro
asistencial.

**Los ficheros en disco no los toca esta capa.** El export devuelve los
metadatos del documento, no los bytes, y una supresión no borra el
objeto almacenado — ADR 0008 dejó la retención de almacenamiento
documentada y sin motor. Es un hueco real, no un descuido.

See ``app.core.privacy.subject`` and ADR 0026.
"""

from __future__ import annotations

from app.core.privacy import ChildLink, SubjectContributor, patient_keyed_export

from .models import Document, MediaAttachment

CLINICAL_RETENTION = (
    "El historial clínico se conserva: la normativa sanitaria fija un "
    "plazo de conservación que no cede ante una solicitud de supresión. "
    "Los datos dejan de identificar al paciente cuando se anonimiza su "
    "ficha de identidad, no borrando el registro asistencial."
)


def get_subject_contributors() -> list[SubjectContributor]:
    return [
        SubjectContributor(
            name="documents",
            export=patient_keyed_export(Document, ChildLink(MediaAttachment, "document_id")),
            retention_reason=CLINICAL_RETENTION,
        ),
    ]
