"""Catalog event handlers.

Consumes ``clinic.created`` to install the clinic's baseline catalog —
VAT types, treatment categories, catalog items and specialties. When the
event names the disciplines the clinic was created with (``specialties``),
the clinic ends up with exactly those enabled.

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

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker

from .packs import SpecialtyPackService
from .providers import REQUIRED_SPECIALTIES
from .seed import SPECIALTIES, seed_catalog

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
            if "specialties" in data:
                await _keep_only(db, clinic_id, set(data["specialties"]) | REQUIRED_SPECIALTIES)
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


async def _keep_only(db: AsyncSession, clinic_id: UUID, chosen: set[str]) -> None:
    """Leave a just-seeded clinic with the ``chosen`` disciplines enabled.

    The seed gives every clinic the baseline ones. A clinic created with a
    choice gets the choice instead: the baseline disciplines it did not
    pick are disabled — kept, so it can enable them later — and the ones
    it picked beyond the baseline are enabled. Both are the pack
    operations a clinic uses from its settings, so the plan templates
    follow through their events.
    """
    baseline = {specialty["key"] for specialty in SPECIALTIES}
    for key in sorted(baseline - chosen):
        await SpecialtyPackService.disable(db, clinic_id, key)
    for key in sorted(chosen - baseline):
        await SpecialtyPackService.enable(db, clinic_id, key)
