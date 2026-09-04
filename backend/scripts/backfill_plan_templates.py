"""Install the starter plan templates into clinics that predate them.

The templates are seeded from ``clinic.created``, which only helps clinics
created after the feature shipped. Existing ones — and any clinic whose
catalog was seeded after its templates, leaving lines missing — need this.

Safe to re-run: ``PlanTemplateService.seed`` matches on ``key``, never
overwrites a template a clinic has edited, and only fills in lines whose
catalog item exists.

    docker-compose exec backend python scripts/backfill_plan_templates.py
"""

from __future__ import annotations

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

from sqlalchemy import select  # noqa: E402

from app.core.auth.models import Clinic  # noqa: E402
from app.database import async_session_maker  # noqa: E402
from app.modules.treatment_plan.templates_service import PlanTemplateService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backfill_plan_templates")


async def main() -> None:
    async with async_session_maker() as db:
        clinics = (await db.execute(select(Clinic.id, Clinic.name))).all()
        if not clinics:
            logger.info("No clinics found.")
            return

        for clinic_id, name in clinics:
            touched = await PlanTemplateService.seed(db, clinic_id)
            await db.commit()
            logger.info("%s: %s template(s) installed or completed", name, touched)


if __name__ == "__main__":
    asyncio.run(main())
