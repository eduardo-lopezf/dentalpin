"""Shared pieces for free-text search over names.

Two modules search patients by name — `patients` for its own list and
`treatment_plan` for the bandeja — and both hit the same two problems in
Spanish, so the rules live here rather than being written twice and
drifting apart.

**Accents.** `ILIKE` is blind to case but not to diacritics, so "Perez"
does not match "Pérez". Reception types without accents because it is
faster, and the misses are silent: the patient simply is not in the
results. Where an email happens to hold the unaccented spelling the
search appears to work, which is worse — it hides the gap until you meet
a patient with no email.

`translate()` rather than the `unaccent` extension: it needs no
`CREATE EXTENSION` (managed Postgres commonly refuses one), it is
immutable, and the alphabet a clinic types is small and known.

**Words.** A name lives in two columns, so matching a whole query
against either finds nobody for "Juan Pérez". Splitting into words and
requiring each to match *something* (AND across words, OR across fields)
makes "Juan Pérez" and "Pérez Juan" land on the same person, while one
word alone still lists everyone who shares it.
"""

from __future__ import annotations

from typing import Final

_FOLD_PAIRS: Final[tuple[tuple[str, str], ...]] = (
    ("á", "a"),
    ("é", "e"),
    ("í", "i"),
    ("ó", "o"),
    ("ú", "u"),
    ("à", "a"),
    ("è", "e"),
    ("ì", "i"),
    ("ò", "o"),
    ("ù", "u"),
    ("â", "a"),
    ("ê", "e"),
    ("î", "i"),
    ("ô", "o"),
    ("û", "u"),
    ("ä", "a"),
    ("ë", "e"),
    ("ï", "i"),
    ("ö", "o"),
    ("ü", "u"),
    ("ñ", "n"),
    ("ç", "c"),
)

#: Alphabets for SQL ``translate(value, FOLD_FROM, FOLD_TO)``.
FOLD_FROM: Final[str] = "".join(a for a, _ in _FOLD_PAIRS) + "".join(
    a.upper() for a, _ in _FOLD_PAIRS
)
FOLD_TO: Final[str] = "".join(b for _, b in _FOLD_PAIRS) + "".join(
    b.upper() for _, b in _FOLD_PAIRS
)

if len(FOLD_FROM) != len(FOLD_TO):  # pragma: no cover - guards a typo above
    raise RuntimeError("translate() needs matching alphabets")

#: Cap on words honoured from one query. A search box is not a query
#: language, and each word costs a clause.
MAX_SEARCH_TOKENS: Final[int] = 6


def fold(value: str) -> str:
    """Python-side twin of the SQL ``translate``, for the search term."""
    return value.translate(str.maketrans(FOLD_FROM, FOLD_TO))


def search_tokens(search: str | None) -> list[str]:
    """Split a query into folded words, longest-sensible first."""
    if not search or not search.strip():
        return []
    return [fold(token) for token in search.split() if token.strip()][:MAX_SEARCH_TOKENS]
