"""How much disk a tenant's uploaded files take up.

Files a clinic uploads (radiographs, photographs, documents) live in file
storage, under the tenant's folder. They are measured by walking that
folder: what is on disk is the truth, and it also holds what no table
lists, such as the reduced copies made of every image.

Nothing here is filtered by clinic, on purpose: the folder is the
tenant's, and the figure is the account's.

The folder says how much; it does not say what a file *is*. That is the
knowledge of the module that filed it, asked through ``PatientDocuments``
(ADR 0039): a radiograph, a photograph, a document. What no patient file
accounts for — the reduced copies, a professional's portrait — is counted
from the folder and shown apart.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.contracts import DocumentKindUsage

#: Folder, under the tenant's storage root, where a module's tables are
#: dumped before it is uninstalled (``app.core.plugins.processor``). On the
#: same disk, but nobody uploaded it: it is left out of the count.
BACKUPS_FOLDER = "backups"

#: Counted from the folder, after the clinical kinds: the reduced copies
#: stored beside every image, and whatever is left.
PREVIEWS = "previews"
OTHER = "other"

# The naming is the media module's (``thumbnails.py``); core only needs to
# tell these copies from what somebody uploaded, so it knows the two
# endings and nothing else.
_PREVIEW_SUFFIXES = (".thumb.jpg", ".medium.jpg")


@dataclass(frozen=True, slots=True)
class TypeUsage:
    type: str
    bytes: int
    count: int


@dataclass(frozen=True, slots=True)
class FileUsage:
    total_bytes: int
    file_count: int
    previews_bytes: int
    previews_count: int


def file_usage(root: Path) -> FileUsage:
    """Add up the uploaded files under ``root``.

    Blocking: call it off the event loop. A folder that does not exist yet
    is an empty one — a tenant nobody has uploaded anything to. Symbolic
    links are not followed: what they point at is not this tenant's.
    """
    total_bytes = file_count = previews_bytes = previews_count = 0
    for folder, folders, names in os.walk(root, followlinks=False):
        if Path(folder) == root and BACKUPS_FOLDER in folders:
            folders.remove(BACKUPS_FOLDER)  # do not walk into it
        for name in names:
            try:
                size = os.lstat(os.path.join(folder, name)).st_size
            except OSError:  # deleted while we were counting
                continue
            total_bytes += size
            file_count += 1
            if name.lower().endswith(_PREVIEW_SUFFIXES):
                previews_bytes += size
                previews_count += 1
    return FileUsage(
        total_bytes=total_bytes,
        file_count=file_count,
        previews_bytes=previews_bytes,
        previews_count=previews_count,
    )


def by_clinical_kind(files: FileUsage, kinds: list[DocumentKindUsage]) -> list[TypeUsage]:
    """The folder's total, split by what the files are.

    The clinical kinds come first, as their owner reports them; then the
    reduced copies; then whatever the folder holds that neither accounts
    for. That remainder is never negative: a file a table lists and the
    disk no longer has cannot take space away from the others.
    """
    known = [TypeUsage(type=k.kind, bytes=k.bytes, count=k.count) for k in kinds]
    accounted_bytes = sum(k.bytes for k in kinds) + files.previews_bytes
    accounted_count = sum(k.count for k in kinds) + files.previews_count
    return [
        *known,
        TypeUsage(type=PREVIEWS, bytes=files.previews_bytes, count=files.previews_count),
        TypeUsage(
            type=OTHER,
            bytes=max(0, files.total_bytes - accounted_bytes),
            count=max(0, files.file_count - accounted_count),
        ),
    ]


#: How long a measurement of the files is good for. Walking a folder of
#: hundreds of thousands of files takes seconds; the answer barely moves
#: in ten minutes, and whoever needs it fresh can ask for it.
FILE_USAGE_TTL = timedelta(minutes=10)


@dataclass(frozen=True, slots=True)
class MeasuredFileUsage:
    usage: FileUsage
    measured_at: datetime


# Per process: each worker measures for itself, which costs one walk per
# worker and spares a shared store for a number that is only informative.
_measured: dict[Path, MeasuredFileUsage] = {}
_measuring = asyncio.Lock()


async def cached_file_usage(root: Path, *, refresh: bool = False) -> MeasuredFileUsage:
    """``file_usage(root)``, walked at most once per ``FILE_USAGE_TTL``.

    ``refresh`` walks again now. The lock keeps two requests arriving
    together from walking the same folder twice.
    """
    async with _measuring:
        known = _measured.get(root)
        now = datetime.now(UTC)
        if known is None or refresh or now - known.measured_at >= FILE_USAGE_TTL:
            # Walking a folder blocks; keep the event loop free.
            usage = await asyncio.to_thread(file_usage, root)
            known = _measured[root] = MeasuredFileUsage(usage=usage, measured_at=now)
        return known
