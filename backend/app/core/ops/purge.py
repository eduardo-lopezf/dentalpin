"""Delete a clinic and everything that hangs from it. Development only.

A clinic created to try something out leaves rows in a hundred tables.
This removes them by following the foreign keys down from ``clinics``:
before a row goes, whatever points at it goes first, so nothing is left
dangling and no constraint has to be switched off.

It is the opposite of how this codebase treats a real clinic — records
are soft-deleted, the clinical record is append-only, invoices are kept
by law — which is why the route that calls it refuses to run in
production.
"""

from __future__ import annotations

import asyncio
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import ClinicMembership


@dataclass(frozen=True, slots=True)
class _ForeignKey:
    child: str
    child_columns: tuple[str, ...]
    parent_columns: tuple[str, ...]


async def _foreign_keys(db: AsyncSession) -> dict[str, list[_ForeignKey]]:
    """Every foreign key of the schema, by the table it points at. Names
    come back already quoted where they need to be."""
    rows = await db.execute(
        text(
            "SELECT con.conrelid::regclass::text, con.confrelid::regclass::text, "
            "  (SELECT array_agg(quote_ident(a.attname) ORDER BY k.ord) "
            "     FROM unnest(con.conkey) WITH ORDINALITY k(attnum, ord) "
            "     JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum), "
            "  (SELECT array_agg(quote_ident(a.attname) ORDER BY k.ord) "
            "     FROM unnest(con.confkey) WITH ORDINALITY k(attnum, ord) "
            "     JOIN pg_attribute a ON a.attrelid = con.confrelid AND a.attnum = k.attnum) "
            "FROM pg_constraint con "
            "WHERE con.contype = 'f' AND con.connamespace = current_schema()::regnamespace"
        )
    )
    by_parent: dict[str, list[_ForeignKey]] = defaultdict(list)
    for child, parent, child_columns, parent_columns in rows:
        by_parent[parent].append(_ForeignKey(child, tuple(child_columns), tuple(parent_columns)))
    return by_parent


async def _delete(
    db: AsyncSession,
    foreign_keys: dict[str, list[_ForeignKey]],
    table: str,
    where: str,
    params: dict,
    path: frozenset[str] = frozenset(),
) -> None:
    """Delete the rows of ``table`` matching ``where``, after the rows
    that point at them."""
    for key in foreign_keys.get(table, ()):
        # A table that points at itself is emptied in one statement, and a
        # cycle between tables is not followed twice.
        if key.child == table or key.child in path:
            continue
        pointing = (
            f"({', '.join(key.child_columns)}) IN "
            f"(SELECT {', '.join(key.parent_columns)} FROM {table} WHERE {where})"
        )
        await _delete(db, foreign_keys, key.child, pointing, params, path | {table})
    await db.execute(text(f"DELETE FROM {table} WHERE {where}"), params)


async def purge_clinic(db: AsyncSession, clinic_id: UUID, storage_root: Path) -> None:
    """Remove the clinic, its rows in every table, the accounts that
    belonged to no other clinic, and its folder of uploaded files."""
    # Asked before the memberships go: the accounts that are only this clinic's.
    elsewhere = select(ClinicMembership.user_id).where(ClinicMembership.clinic_id != clinic_id)
    only_here = list(
        await db.scalars(
            select(ClinicMembership.user_id).where(
                ClinicMembership.clinic_id == clinic_id,
                ClinicMembership.user_id.not_in(elsewhere),
            )
        )
    )

    foreign_keys = await _foreign_keys(db)
    await _delete(db, foreign_keys, "clinics", "id = :clinic_id", {"clinic_id": clinic_id})

    # An account something outside this clinic still points at stays: it
    # is left without a clinic rather than taking another clinic's rows.
    for user_id in only_here:
        try:
            async with db.begin_nested():
                await db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        except IntegrityError:
            continue

    await asyncio.to_thread(shutil.rmtree, storage_root / str(clinic_id), ignore_errors=True)
