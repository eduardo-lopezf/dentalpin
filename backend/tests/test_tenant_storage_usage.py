"""Disk space a tenant's uploaded files take up (Settings → Account)."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.core.contracts import DocumentKindUsage
from app.core.tenancy import usage as usage_module
from app.core.tenancy.usage import FileUsage, by_clinical_kind, cached_file_usage, file_usage
from app.modules.patients.models import Patient

URL = "/api/v1/auth/tenant/storage"


@pytest.mark.asyncio
async def test_an_administrator_reads_the_space_used(
    client: AsyncClient, auth_headers: dict[str, str], test_clinic: Clinic
) -> None:
    response = await client.get(URL, headers=auth_headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    # Whatever the clinical kinds, the folder's own two close the list.
    assert [entry["type"] for entry in data["types"]][-2:] == ["previews", "other"]
    assert data["total_bytes"] == sum(entry["bytes"] for entry in data["types"])
    assert data["file_count"] == sum(entry["count"] for entry in data["types"])
    assert data["measured_at"]
    # Only the files: nothing about the database.
    assert set(data) == {"total_bytes", "file_count", "types", "measured_at"}


@pytest.mark.asyncio
async def test_it_is_not_public(client: AsyncClient) -> None:
    assert (await client.get(URL)).status_code == 401


def test_the_folder_is_split_by_what_the_files_are() -> None:
    folder = FileUsage(total_bytes=10_000, file_count=12, previews_bytes=500, previews_count=4)
    kinds = [
        DocumentKindUsage(kind="xray", bytes=6_000, count=3),
        DocumentKindUsage(kind="document", bytes=1_500, count=2),
    ]
    split = {entry.type: entry for entry in by_clinical_kind(folder, kinds)}
    assert list(split) == ["xray", "document", "previews", "other"]
    assert (split["xray"].bytes, split["xray"].count) == (6_000, 3)
    assert (split["previews"].bytes, split["previews"].count) == (500, 4)
    # What neither a patient file nor a reduced copy accounts for.
    assert (split["other"].bytes, split["other"].count) == (2_000, 3)
    assert sum(entry.bytes for entry in split.values()) == folder.total_bytes


def test_a_file_listed_but_gone_from_disk_takes_nothing_from_the_rest() -> None:
    folder = FileUsage(total_bytes=1_000, file_count=1, previews_bytes=0, previews_count=0)
    listed = [DocumentKindUsage(kind="photo", bytes=5_000, count=2)]
    other = by_clinical_kind(folder, listed)[-1]
    assert (other.type, other.bytes, other.count) == ("other", 0, 0)


def test_with_media_off_everything_is_other() -> None:
    folder = FileUsage(total_bytes=900, file_count=3, previews_bytes=100, previews_count=1)
    assert [(e.type, e.bytes, e.count) for e in by_clinical_kind(folder, [])] == [
        ("previews", 100, 1),
        ("other", 800, 2),
    ]


def test_uploaded_files_are_added_up_and_backups_left_out(tmp_path) -> None:
    clinic = tmp_path / "a0ee" / "patients" / "p1"
    clinic.mkdir(parents=True)
    (clinic / "rx.jpg").write_bytes(b"x" * 1000)
    (clinic / "rx.jpg.thumb.jpg").write_bytes(b"x" * 50)
    (clinic / "consent.pdf").write_bytes(b"x" * 400)
    (tmp_path / "backups" / "schedules").mkdir(parents=True)
    (tmp_path / "backups" / "schedules" / "dump.sql").write_bytes(b"x" * 300)
    # Only the top-level folder is the backups one.
    (clinic / "backups").mkdir()
    (clinic / "backups" / "scan.pdf").write_bytes(b"x" * 200)
    # A link out of the folder is not this tenant's to count.
    outside = tmp_path.parent / f"{tmp_path.name}-outside.bin"
    outside.write_bytes(b"x" * 10_000)
    (clinic / "link.bin").symlink_to(outside)

    usage = file_usage(tmp_path)
    # rx.jpg, its reduced copy, two PDFs and the link itself (a few bytes).
    assert usage.file_count == 5
    assert 1650 <= usage.total_bytes < 2000
    assert (usage.previews_bytes, usage.previews_count) == (50, 1)


def test_a_tenant_with_no_folder_yet_has_no_files(tmp_path) -> None:
    usage = file_usage(tmp_path / "never-created")
    assert (usage.total_bytes, usage.file_count, usage.previews_count) == (0, 0, 0)


@pytest.mark.asyncio
async def test_the_files_are_counted_once_and_kept(tmp_path, monkeypatch) -> None:
    (tmp_path / "a.bin").write_bytes(b"x" * 100)
    first = await cached_file_usage(tmp_path)
    assert first.usage.total_bytes == 100

    # A new file does not show until the figure is due, or asked for.
    (tmp_path / "b.bin").write_bytes(b"x" * 400)
    kept = await cached_file_usage(tmp_path)
    assert kept.usage.total_bytes == 100 and kept.measured_at == first.measured_at

    asked = await cached_file_usage(tmp_path, refresh=True)
    assert asked.usage.total_bytes == 500 and asked.measured_at > first.measured_at

    # Past its time, it is counted again by itself.
    (tmp_path / "c.bin").write_bytes(b"x" * 1000)
    monkeypatch.setattr(usage_module, "FILE_USAGE_TTL", usage_module.timedelta(0))
    assert (await cached_file_usage(tmp_path)).usage.total_bytes == 1500


@pytest.mark.asyncio
async def test_media_reports_what_the_patients_files_weigh_by_kind(
    db_session: AsyncSession,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
    test_patient: Patient,
) -> None:
    from app.modules.media.models import Document
    from app.modules.media.providers import documents

    uploader = (await db_session.execute(select(User.id).limit(1))).scalar_one()
    files = [("xray", 4_000, "active"), ("xray", 1_000, "archived"), ("document", 300, "active")]
    for index, (kind, size, status) in enumerate(files):
        db_session.add(
            Document(
                clinic_id=test_clinic.id,
                patient_id=test_patient.id,
                document_type="other",
                title=f"file {index}",
                original_filename=f"f{index}.bin",
                storage_path=f"usage-test/{index}.bin",
                mime_type="application/octet-stream",
                file_size=size,
                media_kind=kind,
                uploaded_by=uploader,
                status=status,
            )
        )
    await db_session.flush()

    usage = await documents.usage_by_kind(db_session)
    # Largest first; an archived file is still on the disk.
    assert [(u.kind, u.bytes, u.count) for u in usage] == [("xray", 5_000, 2), ("document", 300, 1)]
