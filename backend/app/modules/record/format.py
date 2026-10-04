"""How a clinic wants its record laid out.

Three choices, stored with the clinic's settings:

- ``hidden_sections`` — sections the clinic does not use. They are left
  out of the *Expediente* tab and cannot be handed over. Nothing is
  deleted: the data stays where it is written, and unhiding brings the
  section back.
- ``section_order`` — the order sections read in, on screen and on paper.
  A section the order does not mention keeps its default place, after the
  ones it does, so one a newly enabled module adds still appears.
- ``disabled_requirements`` — points of the coverage check the clinic
  does not want reviewed.

The default — nothing hidden, the order of a paper *expediente*, every
requirement checked — is what an empty format means.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

_NAME = r"^[a-z0-9_]+(\.[a-z0-9_]+)?$"
_Names = Annotated[
    list[Annotated[str, Field(pattern=_NAME, max_length=80)]],
    Field(default_factory=list, max_length=60),
]

SETTINGS_KEY = "record_format"


class RecordFormat(BaseModel):
    hidden_sections: _Names
    section_order: _Names
    disabled_requirements: _Names


def read_format(settings: dict | None) -> RecordFormat:
    try:
        return RecordFormat.model_validate((settings or {}).get(SETTINGS_KEY) or {})
    except ValueError:
        # A stored format that no longer parses is not worth a broken
        # record: fall back to the default layout.
        return RecordFormat()


def arrange(sections: list, fmt: RecordFormat, name=lambda section: section.qualified_name) -> list:
    """Drop the hidden sections and put the rest in the clinic's order."""
    hidden = set(fmt.hidden_sections)
    position = {qualified: index for index, qualified in enumerate(fmt.section_order)}
    kept = [section for section in sections if name(section) not in hidden]
    # Stable: sections the order does not mention keep their default
    # sequence, after the ones it places.
    return sorted(kept, key=lambda section: position.get(name(section), len(position)))
