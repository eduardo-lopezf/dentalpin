"""Catalog event handlers.

Consumes ``clinic.created`` to install the clinic's baseline catalog —
VAT types, treatment categories, catalog items and specialties.

Core creates the clinic but must not import a module to populate it
(ADR 0003), so the module installs its own baseline data in reaction to
the event. The bus awaits handlers inline, so by the time ``/auth/setup``
returns its tokens the catalog is already queryable and the first screen
the new admin opens is not empty.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.database import async_session_maker

from .seed import seed_catalog

logger = logging.getLogger(__name__)


async def on_clinic_created(data: dict[str, Any]) -> None:
    """Seed the baseline catalog for a freshly created clinic.

    Idempotent: ``seed_catalog`` matches on ``key`` / ``internal_code``,
    so a replayed event creates nothing and leaves clinic-edited rows
    alone.
    """
    clinic_id_raw = data.get("clinic_id")
    if not clinic_id_raw:
        return

    try:
        clinic_id = UUID(str(clinic_id_raw))
    except (ValueError, TypeError):
        return

    async with async_session_maker() as db:
        try:
            summary = await seed_catalog(db, clinic_id)
            await db.commit()
        except Exception as exc:  # pragma: no cover - defensive
            # The bus swallows handler exceptions, so a failure here would
            # otherwise be invisible: the admin lands on an empty catalog
            # with nothing in the logs. Say so loudly and name the remedy.
            logger.error(
                "catalog.on_clinic_created failed for clinic %s: %s — "
                "run scripts/backfill_catalog_specialties.py to recover",
                clinic_id,
                exc,
                exc_info=True,
            )
            return

    logger.info(
        "catalog: seeded clinic %s (categories=%s items=%s specialties=%s)",
        clinic_id,
        summary["categories"],
        summary["items"],
        summary["specialties"],
    )
