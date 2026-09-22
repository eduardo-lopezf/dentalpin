"""Fold the schedules seed's duplicate directory records back into the real ones.

``scripts/seed_demo.py`` creates one ``Professional`` per clinical user,
carrying the **account's own id** and its licence number; every appointment,
plan item and commission in the demo points at it. The schedules demo seed
used to derive an id of its own from the same account, look only there, and
create a *second* record for the same person — a duplicate in every
professional picker, with this module's weekly hours hanging off the copy
nobody books. The seed no longer does that
(``app/modules/schedules/seed.py``); this is the one-off pass for databases
seeded before the fix.

**What it considers a duplicate** — all of these, together:

- a record whose id is the uuid5 the schedules seed derives from a clinical
  user of the same clinic (that is the whole signature: the derivation is
  reproducible, so the match is exact rather than by name);
- with an account-id record for that same user present in the clinic;
- and carrying no clinical work: no appointments, budgets, plan items,
  plans, recalls, prescriptions, liquidations or commissions.

A duplicate holding any of those is reported and skipped: at that point it
is a record somebody has worked with, and merging it is a decision for a
person, not for a script.

What moves: weekly schedules and schedule overrides, from the duplicate to
the account-id record. What is then deleted: the duplicate itself.

Dry run by default — it prints what it would do and writes nothing.

    docker-compose exec backend python scripts/merge_duplicate_demo_professionals.py
    docker-compose exec backend python scripts/merge_duplicate_demo_professionals.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Force SQLAlchemy to resolve every cross-module relationship by loading all
# module models the same way the app does at startup.
from app.core.plugins.loader import load_modules  # noqa: E402
from app.main import app as _app  # noqa: E402

load_modules(_app)

from sqlalchemy import text  # noqa: E402

from app.database import async_session_maker  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("merge_duplicate_demo_professionals")

#: Every table that points at ``professionals.id``, and the column that does.
#: Split in two because the first group is what makes a record "in use" and
#: the second is what this script moves.
WORK_REFERENCES: list[tuple[str, str]] = [
    ("appointments", "professional_id"),
    ("budgets", "assigned_professional_id"),
    ("liquidations", "professional_id"),
    ("planned_treatment_items", "assigned_professional_id"),
    ("professional_commissions", "professional_id"),
    ("professional_specialties", "professional_id"),
    ("recalls", "assigned_professional_id"),
    ("treatment_plans", "assigned_professional_id"),
    ("treatment_prescriptions", "professional_id"),
]
MOVED_REFERENCES: list[tuple[str, str]] = [
    ("professional_weekly_schedules", "professional_id"),
    ("professional_overrides", "professional_id"),
]

CLINICAL_USERS = text("""
    SELECT u.id AS user_id, cm.clinic_id AS clinic_id
    FROM users u
    JOIN clinic_memberships cm ON cm.user_id = u.id
    WHERE cm.role IN ('dentist', 'hygienist')
""")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args()

    async with async_session_maker() as db:
        pairs = (await db.execute(CLINICAL_USERS)).mappings().all()

        merges: list[tuple[UUID, UUID, dict[str, int]]] = []
        for row in pairs:
            derived = uuid5(
                NAMESPACE_URL,
                f"dentalpin:legacy-professional:{row['clinic_id']}:{row['user_id']}",
            )
            present = (
                (
                    await db.execute(
                        text(
                            "SELECT id FROM professionals "
                            "WHERE clinic_id = :clinic AND id IN (:derived, :account)"
                        ),
                        {"clinic": row["clinic_id"], "derived": derived, "account": row["user_id"]},
                    )
                )
                .scalars()
                .all()
            )
            if derived not in present or row["user_id"] not in present:
                continue

            in_use = {}
            for table, column in WORK_REFERENCES:
                count = (
                    await db.execute(
                        text(f"SELECT count(*) FROM {table} WHERE {column} = :pid"),
                        {"pid": derived},
                    )
                ).scalar_one()
                if count:
                    in_use[f"{table}.{column}"] = count

            carried = {}
            for table, column in MOVED_REFERENCES:
                count = (
                    await db.execute(
                        text(f"SELECT count(*) FROM {table} WHERE {column} = :pid"),
                        {"pid": derived},
                    )
                ).scalar_one()
                if count:
                    carried[f"{table}.{column}"] = count

            if in_use:
                logger.warning(
                    "SKIP %s → %s: the duplicate carries clinical work (%s). Merge it by hand.",
                    derived,
                    row["user_id"],
                    ", ".join(f"{k}={v}" for k, v in in_use.items()),
                )
                continue

            merges.append((derived, row["user_id"], carried))

        if not merges:
            logger.info("No duplicate directory records to merge.")
            return

        logger.info("%s duplicate record(s) to fold in:\n", len(merges))
        for derived, account, carried in merges:
            moved = ", ".join(f"{k}={v}" for k, v in carried.items()) or "nothing to move"
            logger.info("  %s → %s  (%s)", derived, account, moved)

        if not args.apply:
            logger.info("\nDry run — nothing written. Re-run with --apply to merge them.")
            return

        for derived, account, _ in merges:
            for table, column in MOVED_REFERENCES:
                await db.execute(
                    text(f"UPDATE {table} SET {column} = :account WHERE {column} = :derived"),
                    {"account": account, "derived": derived},
                )
            await db.execute(
                text("DELETE FROM professionals WHERE id = :derived"),
                {"derived": derived},
            )

        await db.commit()
        logger.info("\n%s duplicate record(s) merged.", len(merges))


if __name__ == "__main__":
    asyncio.run(main())
