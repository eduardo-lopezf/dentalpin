"""The attachment-owner registry lives in the core now.

``app.core.attachments`` is the home: a module that wants its rows to
take attachments registers there without importing ``media`` (ADR 0039).
This name stays for ``media``'s own code and for modules that depend on
it outright.
"""

from app.core.attachments import (
    AttachmentRegistry,
    OwnerSpec,
    PatientResolver,
    attachment_registry,
)

__all__ = ["AttachmentRegistry", "OwnerSpec", "PatientResolver", "attachment_registry"]
