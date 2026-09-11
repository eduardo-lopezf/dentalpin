"""Start the plans whose patient already came, before attendance moved them.

``pending → active`` used to happen only when the budget was accepted.
Since attendance became a second door into ``active``, a plan whose first
consultation is already in the past is stuck one step behind reality: it
reads *Confirmar* on the ficha and sits in the wrong pipeline queues,
even though the work has begun.

The runtime rule listens to ``appointment.completed``, so it can only
help visits that happen from now on. This is the one-off pass over the
visits that already happened.

**What counts as "the patient came"** — either is enough, and both mean
the same thing clinically:

- a completed appointment linked to one of the plan's items, or
- a completed plan item, whether or not an appointment backs it.

The second is not redundant: a clinic can tick a treatment off directly
on the plan (``completed_without_appointment``), which is how a first
consultation often gets recorded, and no appointment row ever exists for
it. A backfill keyed only to appointments would walk straight past those.

Only ``pending`` plans move. ``draft`` is left alone — an unconfirmed
plan must not skip confirmation — and every later status already means
the plan started.

Dry run by default: it prints what it would change and writes nothing.

    docker-compose exec backend python scripts/backfill_started_plans.py
    docker-compose exec backend python scripts/backfill_started_plans.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

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
from app.modules.treatment_plan.service import TreatmentPlanService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backfill_started_plans")


# Raw SQL because the evidence spans treatment_plan + agenda. Both are in
# treatment_plan's manifest.depends, and this mirrors how the bandeja
# query already joins the two.
CANDIDATES = text("""
    SELECT
        tp.id            AS plan_id,
        tp.clinic_id     AS clinic_id,
        tp.plan_number   AS plan_number,
        pat.first_name   AS first_name,
        pat.last_name    AS last_name,
        COUNT(DISTINCT pti.id) FILTER (WHERE pti.status = 'completed') AS done_items,
        COUNT(DISTINCT a.id)   FILTER (WHERE a.status = 'completed')   AS done_appointments
    FROM treatment_plans tp
    JOIN patients pat ON pat.id = tp.patient_id
    JOIN planned_treatment_items pti ON pti.treatment_plan_id = tp.id
    LEFT JOIN appointment_treatments at ON at.planned_treatment_item_id = pti.id
    LEFT JOIN appointments a ON a.id = at.appointment_id
    WHERE tp.deleted_at IS NULL
      AND tp.status = 'pending'
    GROUP BY tp.id, tp.clinic_id, tp.plan_number, pat.first_name, pat.last_name
    HAVING COUNT(DISTINCT pti.id) FILTER (WHERE pti.status = 'completed') > 0
        OR COUNT(DISTINCT a.id)   FILTER (WHERE a.status = 'completed')   > 0
    ORDER BY tp.plan_number
""")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the changes. Without it the script only reports.",
    )
    args = parser.parse_args()

    async with async_session_maker() as db:
        rows = (await db.execute(CANDIDATES)).mappings().all()

        if not rows:
            logger.info("Nothing to do: no pending plan has a past visit behind it.")
            return

        logger.info(
            "%s plan(s) whose patient already came:\n",
            len(rows),
        )
        for r in rows:
            logger.info(
                "  %-16s %-28s %s completed treatment(s), %s completed appointment(s)",
                r["plan_number"],
                f"{r['first_name']} {r['last_name']}",
                r["done_items"],
                r["done_appointments"],
            )

        if not args.apply:
            logger.info("\nDry run — nothing written. Re-run with --apply to move them.")
            return

        moved = 0
        for r in rows:
            plan = await TreatmentPlanService.activate_from_attendance(
                db, r["clinic_id"], r["plan_id"]
            )
            # The service is idempotent and refuses anything that is not
            # `pending`, so a plan someone changed between the query and
            # here simply stays put.
            if plan is not None and plan.status == "active":
                moved += 1

        await db.commit()
        logger.info("\n%s plan(s) moved to active.", moved)


if __name__ == "__main__":
    asyncio.run(main())
