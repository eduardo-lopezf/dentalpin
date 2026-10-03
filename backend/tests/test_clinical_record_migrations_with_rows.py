"""The phase 0 migrations, run against a database that has patients in it.

ADR 0032 asks for this one by name: *"This is a data migration over populated
tables, which is the class of change that has already broken a deploy here. It
is tested against a database with rows, not only an empty one."*

The existing `test_alembic_roundtrip.py` proves the schema is reproducible from
empty. That is a different question from whether a clinic's rows survive the
upgrade — and the difference is where the damage lives: a constraint that only
fails when a table is not empty, a NOT NULL added without a default, an index
built on data that does not satisfy it.

Two failures this catches, one of them already caught:

1. **Ordering across migration branches.** A first draft added a foreign key to
   `professionals`. This module is on the core linear chain, which boot applies
   first; `professionals` is a removable module on its own branch, applied
   afterwards. The upgrade died with `relation "professionals" does not exist`
   on every fresh install, and nothing in the empty-database round-trip noticed,
   because that test upgrades to `heads` — every branch, in an order that
   happened to work.
2. **Rows quietly lost or rewritten.** The point of the whole change is that a
   clinical entry keeps its identity and the date it was first recorded.

Marked `alembic_roundtrip` like its neighbour: it rebuilds the schema of the
database it is pointed at, so it must not run inside the ordinary suite.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import asyncpg
import pytest

from app.config import settings

pytestmark = pytest.mark.alembic_roundtrip

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

#: The revisions under test and the ones before them.
BEFORE = "pc_0001"
AFTER = "pc_0002"
NOTES_BEFORE = "cn_0004"
NOTES_AFTER = "cn_0005"

CLINIC_ID = "11111111-1111-1111-1111-111111111111"
PATIENT_ID = "22222222-2222-2222-2222-222222222222"
ALLERGY_ID = "33333333-3333-3333-3333-333333333333"
MEDICATION_ID = "44444444-4444-4444-4444-444444444444"


def _alembic(*args: str) -> None:
    subprocess.run(["alembic", "-c", str(ALEMBIC_INI), *args], cwd=BACKEND_ROOT, check=True)


def _dsn() -> str:
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def _run(sql: str, *args):
    conn = await asyncpg.connect(_dsn())
    try:
        return await conn.fetch(sql, *args)
    finally:
        await conn.close()


async def _drop_everything() -> None:
    conn = await asyncpg.connect(_dsn())
    try:
        rows = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        for row in rows:
            await conn.execute(f'DROP TABLE IF EXISTS "{row["tablename"]}" CASCADE')
    finally:
        await conn.close()


async def _insert(conn, table: str, values: dict) -> None:
    """Insert a row, filling in whatever else the table insists on.

    The seeds here are used from both ends of the migration chain, and the
    tables grow NOT NULL columns as it advances — `clinics.account_tier`,
    `patients.do_not_contact`. Chasing each one as it appears would make this
    harness break every time an unrelated migration lands, so the row is
    completed from `information_schema`: anything required, without a default,
    that the caller did not name gets a harmless value of the right type.

    The values are deliberately boring. Nothing here is under test — the row
    exists so the migration has something to migrate.
    """
    present = await conn.fetch(
        "SELECT column_name, data_type, is_nullable, column_default "
        "FROM information_schema.columns WHERE table_name = $1",
        table,
    )
    known = {row["column_name"] for row in present}
    required = [
        row for row in present if row["is_nullable"] == "NO" and row["column_default"] is None
    ]
    # Values for columns this revision does not have yet are dropped rather
    # than failing: the caller names everything any revision might want.
    filled = {k: v for k, v in values.items() if k in known}
    for column in required:
        name, kind = column["column_name"], column["data_type"]
        if name in filled:
            continue
        if kind == "boolean":
            filled[name] = False
        elif kind in ("integer", "bigint", "smallint"):
            filled[name] = 0
        elif kind in ("timestamp with time zone", "timestamp without time zone"):
            continue  # created_at / updated_at are given explicitly below
        elif kind == "jsonb":
            filled[name] = "{}"
        else:
            filled[name] = "x"

    columns = list(filled)
    casts = ", ".join(
        f"${i + 1}::jsonb" if columns[i] in ("settings", "address") else f"${i + 1}"
        for i in range(len(columns))
    )
    await conn.execute(
        f"INSERT INTO {table} ({', '.join(columns)}, created_at, updated_at) "
        f"VALUES ({casts}, now(), now())",
        *[filled[c] for c in columns],
    )


async def _seed_a_patient_with_history() -> None:
    """The smallest clinic that can hold an allergy: one clinic, one patient."""
    conn = await asyncpg.connect(_dsn())
    try:
        await _insert(
            conn,
            "clinics",
            {
                "id": CLINIC_ID,
                "name": "Scratch",
                "tax_id": "B1",
                # Named even though older revisions lack the column, and
                # constrained by a CHECK the generic filler cannot guess.
                "account_tier": "clinic",
            },
        )
        await _insert(
            conn,
            "patients",
            {
                "id": PATIENT_ID,
                "clinic_id": CLINIC_ID,
                "first_name": "Ana",
                "last_name": "García",
                "status": "active",
            },
        )
        await _insert(
            conn,
            "patients_clinical_allergy",
            {
                "id": ALLERGY_ID,
                "patient_id": PATIENT_ID,
                "clinic_id": CLINIC_ID,
                "name": "Penicilina",
                "severity": "critical",
            },
        )
        await _insert(
            conn,
            "patients_clinical_medication",
            {
                "id": MEDICATION_ID,
                "patient_id": PATIENT_ID,
                "clinic_id": CLINIC_ID,
                "name": "Sintrom",
            },
        )
    finally:
        await conn.close()


def test_clinical_history_upgrade_survives_populated_tables() -> None:
    async def _prepare() -> str:
        await _drop_everything()
        return ""

    asyncio.run(_prepare())

    # Arrive at the revision before the change, the way a running clinic did.
    _alembic("stamp", "base")
    _alembic("upgrade", BEFORE)
    asyncio.run(_seed_a_patient_with_history())

    before = asyncio.run(
        _run("SELECT id, name, created_at FROM patients_clinical_allergy ORDER BY name")
    )
    assert [row["name"] for row in before] == ["Penicilina"]
    first_recorded = before[0]["created_at"]

    # The upgrade under test, on a table that is not empty.
    _alembic("upgrade", AFTER)

    after = asyncio.run(
        _run(
            "SELECT id, name, created_at, ended_at, retracted_at, retraction_reason, "
            "recorded_by_user_id FROM patients_clinical_allergy ORDER BY name"
        )
    )
    assert len(after) == 1, "the row is still there"
    assert after[0]["id"] == before[0]["id"], "and it is the same row, not a copy"
    assert after[0]["created_at"] == first_recorded, (
        "an allergy that loses the date it was first recorded cannot say since when it was known"
    )
    # Existing rows are live and unattributed: they predate the rule, and an
    # author who never signed them is not invented.
    assert after[0]["ended_at"] is None
    assert after[0]["retracted_at"] is None
    assert after[0]["recorded_by_user_id"] is None

    medications = asyncio.run(_run("SELECT name FROM patients_clinical_medication"))
    assert [row["name"] for row in medications] == ["Sintrom"]


def test_clinical_history_downgrade_keeps_the_rows() -> None:
    """Going back drops the columns, never the patient's history.

    A downgrade that takes rows with it is not a way back — it is a second
    outage on top of whichever one prompted it.
    """
    _alembic("downgrade", BEFORE)

    rows = asyncio.run(_run("SELECT id, name FROM patients_clinical_allergy"))
    assert [row["name"] for row in rows] == ["Penicilina"]
    assert rows[0]["id"] == asyncio.run(_run("SELECT id FROM patients_clinical_allergy"))[0]["id"]

    columns = asyncio.run(
        _run(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'patients_clinical_allergy'"
        )
    )
    names = {row["column_name"] for row in columns}
    assert "retracted_at" not in names

    # And forward again, which is the state the suite leaves behind.
    _alembic("upgrade", AFTER)
    again = asyncio.run(_run("SELECT name, retracted_at FROM patients_clinical_allergy"))
    assert [row["name"] for row in again] == ["Penicilina"]
    assert again[0]["retracted_at"] is None


# ---------------------------------------------------------------------------
# cn_0005 — note amendments
#
# `clinical_notes` is on its own branch and its tables reference core ones, so
# this half cannot upgrade its branch in isolation the way the history half
# does. It goes to `heads` and steps the one branch back, which is also closer
# to what a real upgrade does.
# ---------------------------------------------------------------------------

USER_ID = "55555555-5555-5555-5555-555555555555"
NOTE_ID = "66666666-6666-6666-6666-666666666666"


async def _seed_a_note() -> None:
    conn = await asyncpg.connect(_dsn())
    try:
        await _insert(
            conn,
            "users",
            {
                "id": USER_ID,
                "email": "autor@example.com",
                "password_hash": "x",
                "first_name": "Autora",
                "last_name": "Demo",
                "is_active": True,
            },
        )
        await _insert(
            conn,
            "clinical_notes",
            {
                "id": NOTE_ID,
                "clinic_id": CLINIC_ID,
                "note_type": "administrative",
                "owner_type": "patient",
                "owner_id": PATIENT_ID,
                "body": "Refiere dolor en el 26.",
                "author_id": USER_ID,
            },
        )
    finally:
        await conn.close()


def test_note_amendments_upgrade_survives_populated_tables() -> None:
    asyncio.run(_drop_everything())
    _alembic("stamp", "base")
    _alembic("upgrade", "heads")

    # Step the notes branch back to before the change, the way a clinic was.
    _alembic("downgrade", NOTES_BEFORE)
    asyncio.run(_seed_a_patient_with_history())
    asyncio.run(_seed_a_note())

    columns = asyncio.run(
        _run(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'clinical_notes'"
        )
    )
    assert "version" not in {row["column_name"] for row in columns}

    _alembic("upgrade", NOTES_AFTER)

    notes = asyncio.run(
        _run("SELECT id, body, version, amended_at, created_at FROM clinical_notes")
    )
    assert len(notes) == 1, "the note survived"
    assert notes[0]["body"] == "Refiere dolor en el 26."
    assert notes[0]["version"] == 1, "an existing note is version 1, filled by the server default"
    assert notes[0]["amended_at"] is None, (
        "claiming a date for amendments made before the migration would be inventing one"
    )

    versions = asyncio.run(_run("SELECT count(*) AS n FROM clinical_note_versions"))
    assert versions[0]["n"] == 0, "no history is manufactured for notes that were never amended"


def test_note_amendments_downgrade_keeps_the_notes() -> None:
    """Going back drops the versions table, never the notes themselves."""
    _alembic("downgrade", NOTES_BEFORE)

    notes = asyncio.run(_run("SELECT id, body FROM clinical_notes"))
    assert [row["body"] for row in notes] == ["Refiere dolor en el 26."]

    tables = asyncio.run(_run("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
    assert "clinical_note_versions" not in {row["tablename"] for row in tables}

    _alembic("upgrade", NOTES_AFTER)
    again = asyncio.run(_run("SELECT body, version FROM clinical_notes"))
    assert again[0]["version"] == 1


# ---------------------------------------------------------------------------
# pc_0003 / cn_0006 — clinical authorship
#
# These are the revisions whose first draft failed on an empty database, when
# the foreign key to `professionals` was declared without `depends_on`. The
# check that matters is therefore the plain one: they apply at all, from
# nothing, with rows already in the tables.
# ---------------------------------------------------------------------------

AUTHOR_BEFORE = "pc_0002"
AUTHOR_AFTER = "pc_0003"


def test_clinical_authorship_upgrade_reaches_an_empty_database() -> None:
    """The FK into another module's branch resolves, from base, with rows.

    Without `depends_on` this died with `relation "professionals" does not
    exist`: `patients_clinical` rides the core chain that boot applies first,
    `professionals` is a removable module applied afterwards. Nothing in the
    empty-schema round-trip caught it, because that one upgrades to `heads`.
    """
    asyncio.run(_drop_everything())
    _alembic("stamp", "base")
    _alembic("upgrade", AUTHOR_BEFORE)
    asyncio.run(_seed_a_patient_with_history())

    _alembic("upgrade", AUTHOR_AFTER)

    # The dependency pulled in the revision that creates the table.
    tables = asyncio.run(_run("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
    assert "professionals" in {row["tablename"] for row in tables}

    rows = asyncio.run(
        _run(
            "SELECT name, recorded_by_professional_id FROM patients_clinical_allergy ORDER BY name"
        )
    )
    assert [row["name"] for row in rows] == ["Penicilina"]
    assert rows[0]["recorded_by_professional_id"] is None, (
        "an entry recorded before the rule is not assigned an author who never signed it"
    )


def test_note_authorship_upgrade_reaches_an_empty_database() -> None:
    """Same for the notes branch, which also had to reach across."""
    _alembic("upgrade", "heads")
    asyncio.run(_seed_a_note())

    notes = asyncio.run(_run("SELECT body, authored_by_professional_id FROM clinical_notes"))
    assert [row["body"] for row in notes] == ["Refiere dolor en el 26."]
    assert notes[0]["authored_by_professional_id"] is None

    columns = asyncio.run(
        _run(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'clinical_note_versions'"
        )
    )
    assert "superseded_by_professional_id" in {row["column_name"] for row in columns}

    # And `professionals` grew the link the whole thing depends on.
    link = asyncio.run(
        _run(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'professionals' AND column_name = 'user_id'"
        )
    )
    assert len(link) == 1
