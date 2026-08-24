"""One-shot backfill of the catalog's specialty axis into existing clinics.

Why this exists: ``cat_0004``/``cat_0006`` create the ``specialties`` table
empty, and the only code that populates it is ``seed_catalog`` — reachable
solely through ``seed_demo.py``, which returns early when the demo clinic
already exists. A deployment created before the specialty axis landed
therefore upgrades cleanly and then shows an empty specialty list forever,
because no code path ever seeds one.

What it does: runs ``seed_all_clinics`` — i.e. ``seed_catalog`` for every
clinic in the database. That function is written for exactly this case:
VAT types, categories and specialties match on ``key``, items match on
``internal_code``, and an item that already exists only gets its missing
specialty links and ``default_phase`` filled in. Clinic-edited prices,
names and codes are never touched, and re-running creates nothing new.

Usage::

    docker-compose exec backend python /app/scripts/backfill_catalog_specialties.py

Run once after deploying the specialty axis. Can be re-run safely.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow running the script directly via `python backend/scripts/...`
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Force SQLAlchemy to resolve every cross-module relationship by
# loading all module models the same way the app does at startup.
from app.core.plugins.loader import load_modules  # noqa: E402
from app.database import async_session_maker  # noqa: E402
from app.main import app as _app  # noqa: E402

load_modules(_app)

from app.modules.catalog.seed import seed_all_clinics  # noqa: E402


async def main() -> int:
    async with async_session_maker() as db:
        summary = await seed_all_clinics(db)
        await db.commit()

    for clinic_id, result in summary.items():
        print(
            f"{clinic_id}: specialties={result['specialties']} "
            f"specialty_links=+{result['specialty_links']} "
            f"categories=+{result['categories']} items=+{result['items']} "
            f"phases_backfilled=+{result['phases_backfilled']}"
        )
    print(f"backfill_catalog_specialties: {len(summary)} clinic(s) processed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
