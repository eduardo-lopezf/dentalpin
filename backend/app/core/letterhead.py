"""The letterheads of what a clinic prints.

A clinic has one letterhead of its own and, when its doctors want theirs,
one per professional. Every printed clinical document — the record, the
consent letters, the blank health questionnaire — asks
:func:`render_letterhead` for its head and says which professional the
document answers to.

**The rule** (ADR 0046): a document carries the letterhead of *its*
professional, or the clinic's when that professional has none or the
document answers to nobody. It never carries another doctor's. There is
no parameter to choose a letterhead by hand — that is how the rule holds.

A module that prints never builds a head of its own.
"""

from __future__ import annotations

import base64
from html import escape
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.core.auth.models import Clinic, ClinicLetterhead

#: ``owner_key`` of the clinic's own letterhead.
CLINIC = "clinic"

#: A logo is a small image. Bigger than this is a photograph.
LOGO_MAX_BYTES = 512 * 1024
#: What the PDF renderer draws and a browser shows, by the bytes a file
#: opens with. No SVG: nothing scriptable reaches the renderer.
_LOGO_SIGNATURES = {b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg"}


class LetterheadWords(BaseModel):
    """The words around the logo."""

    #: Replaces the clinic's name when set.
    heading: str | None = Field(default=None, max_length=120)
    #: A line of its owner's: the professional and their licence, a
    #: speciality, a motto.
    subheading: str | None = Field(default=None, max_length=200)
    show_address: bool = True
    show_contact: bool = True


def owner_key(professional_id: UUID | None) -> str:
    return str(professional_id) if professional_id else CLINIC


def logo_mime_type(image: bytes) -> str | None:
    """The type of an uploaded logo, read from the file's own first bytes
    rather than from what the upload claims to be. ``None`` if it is
    neither a PNG nor a JPEG."""
    return next((mime for magic, mime in _LOGO_SIGNATURES.items() if image.startswith(magic)), None)


async def get_letterhead(
    db: AsyncSession, clinic_id: UUID, key: str, *, with_logo: bool = False
) -> ClinicLetterhead | None:
    query = select(ClinicLetterhead).where(
        ClinicLetterhead.clinic_id == clinic_id, ClinicLetterhead.owner_key == key
    )
    if with_logo:
        query = query.options(undefer(ClinicLetterhead.logo))
    return (await db.execute(query)).scalar_one_or_none()


async def letterhead_for(
    db: AsyncSession, clinic_id: UUID, professional_id: UUID | None
) -> ClinicLetterhead | None:
    """The letterhead a document answering to ``professional_id`` carries.

    Theirs if they have one; otherwise the clinic's; otherwise none, and
    the document is headed by the clinic's bare name. Never another
    professional's.
    """
    if professional_id is not None:
        own = await get_letterhead(db, clinic_id, owner_key(professional_id), with_logo=True)
        if own is not None:
            return own
    return await get_letterhead(db, clinic_id, CLINIC, with_logo=True)


def _address(address: dict | None) -> str:
    if not address:
        return ""
    city = " ".join(filter(None, [address.get("postal_code"), address.get("city")]))
    return ", ".join(p for p in [address.get("street"), city, address.get("state")] if p)


def letterhead_html(clinic: Clinic | None, letterhead: ClinicLetterhead | None) -> str:
    """The head of a printed sheet."""
    words = (
        LetterheadWords.model_validate(letterhead, from_attributes=True)
        if letterhead is not None
        else LetterheadWords()
    )
    heading = words.heading or (clinic.name if clinic else "")
    lines = [words.subheading]
    if clinic is not None:
        if words.show_address:
            lines.append(_address(clinic.address))
        if words.show_contact:
            lines.append(" · ".join(filter(None, [clinic.phone, clinic.email])))
    details = "".join(f"<div>{escape(line)}</div>" for line in lines if line)
    image = ""
    if letterhead is not None and letterhead.logo:
        encoded = base64.b64encode(letterhead.logo).decode("ascii")
        image = (
            f"<img class='lh-logo' src='data:{letterhead.logo_mime_type};base64,{encoded}' alt=''>"
        )
    return (
        f"<div class='letterhead'>{image}<div><div class='lh-heading'>{escape(heading)}</div>"
        f"<div class='lh-lines'>{details}</div></div></div>"
    )


async def render_letterhead(db: AsyncSession, clinic_id: UUID, professional_id: UUID | None) -> str:
    """The head of a document that answers to ``professional_id``.

    Pass the professional the *document* answers to — who explained a
    consent, who hands a record over — never one picked for the look of
    their letterhead. ``None`` is the clinic's.
    """
    clinic = await db.get(Clinic, clinic_id)
    return letterhead_html(clinic, await letterhead_for(db, clinic_id, professional_id))


#: The letterhead's look, for a module's ``<style>``.
LETTERHEAD_CSS = """
  .letterhead { display: flex; align-items: center; gap: 12px;
                border-bottom: 1.5pt solid #111; padding-bottom: 6px; margin-bottom: 8px; }
  .lh-logo { max-height: 20mm; max-width: 42mm; }
  .lh-heading { font-size: 13pt; font-weight: 700; }
  .lh-lines { font-size: 8.5pt; color: #444; line-height: 1.35; }
"""
