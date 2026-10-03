"""Schedules reaches the professionals directory through the core contract
(ADR 0039), and carries on when nobody supplies it (ADR 0037)."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.schedules as schedules_pkg
from app.core.auth.models import Clinic
from app.core.plugins.registry import module_registry
from app.modules.professionals.models import Professional
from app.modules.schedules import SchedulesModule
from app.modules.schedules.services.analytics import AnalyticsService
from app.modules.schedules.services.professional_hours import ProfessionalHoursService


@pytest.fixture
def professionals_off():
    was_active = module_registry.is_installed("professionals")
    module_registry.deactivate("professionals")
    yield
    if was_active:
        module_registry.activate("professionals")


async def _clinic_with_dentist(db: AsyncSession) -> tuple[Clinic, Professional]:
    clinic = Clinic(
        id=uuid4(),
        name="Hours Clinic",
        tax_id="B00000088",
        address={"city": "Madrid"},
        settings={},
        account_tier="clinic",
    )
    db.add(clinic)
    await db.flush()
    dentist = Professional(
        id=uuid4(),
        clinic_id=clinic.id,
        first_name="Dra",
        last_name="Soto",
        professional_type="dentist",
        is_active=True,
    )
    db.add(dentist)
    await db.commit()
    return clinic, dentist


def test_schedules_does_not_import_professionals() -> None:
    """Not even under ``TYPE_CHECKING``. ``agenda`` is its one hard
    dependency and the only module it may import."""
    root = Path(schedules_pkg.__file__).parent
    offenders = []
    for path in root.rglob("*.py"):
        if "/migrations/" in str(path):
            continue
        for number, line in enumerate(path.read_text().splitlines(), 1):
            match = re.match(r"\s*(?:from|import)\s+app\.modules\.([a-z_]+)", line)
            if match and match.group(1) not in ("schedules", "agenda"):
                offenders.append(f"{path.relative_to(root)}:{number} imports {match.group(1)}")
    assert not offenders, "\n".join(offenders)
    assert SchedulesModule.manifest["depends"] == ["agenda"]


@pytest.mark.asyncio
async def test_a_bookable_professional_is_recognised_through_the_directory(
    db_session: AsyncSession,
) -> None:
    clinic, dentist = await _clinic_with_dentist(db_session)

    assert await ProfessionalHoursService.is_professional(db_session, clinic.id, dentist.id)
    assert not await ProfessionalHoursService.is_professional(db_session, clinic.id, uuid4())
    # Tenancy: the same id asked from another clinic is nobody.
    assert not await ProfessionalHoursService.is_professional(db_session, uuid4(), dentist.id)


@pytest.mark.asyncio
async def test_utilization_lists_the_directory_in_name_order(db_session: AsyncSession) -> None:
    clinic, dentist = await _clinic_with_dentist(db_session)
    db_session.add(
        Professional(
            id=uuid4(),
            clinic_id=clinic.id,
            first_name="Ana",
            last_name="Alba",
            professional_type="hygienist",
            is_active=True,
        )
    )
    await db_session.commit()

    rows = await AnalyticsService.utilization(
        db_session, clinic.id, date(2026, 6, 1), date(2026, 6, 7)
    )

    assert [row["professional_name"] for row in rows] == ["Ana Alba", "Dra Soto"]

    only = await AnalyticsService.utilization(
        db_session, clinic.id, date(2026, 6, 1), date(2026, 6, 7), professional_id=dentist.id
    )
    assert [row["professional_id"] for row in only] == [dentist.id]


@pytest.mark.asyncio
async def test_without_the_professionals_app_there_is_nobody_to_keep_hours_for(
    db_session: AsyncSession, professionals_off
) -> None:
    """The rows stay in the database; schedules just has no directory to ask."""
    clinic, dentist = await _clinic_with_dentist(db_session)

    assert not await ProfessionalHoursService.is_professional(db_session, clinic.id, dentist.id)
    assert (
        await AnalyticsService.utilization(
            db_session, clinic.id, date(2026, 6, 1), date(2026, 6, 7)
        )
        == []
    )


@pytest.mark.asyncio
async def test_the_seed_runs_with_nothing_mounted_when_handed_the_directory(
    db_session: AsyncSession, professionals_off
) -> None:
    """``scripts/seed_demo.py`` runs outside the app: no module is
    mounted, so the seed cannot look the directory up and is given it."""
    from app.modules.professionals.providers import professionals_directory
    from app.modules.schedules.seed import seed_schedules_demo

    clinic, dentist = await _clinic_with_dentist(db_session)

    with pytest.raises(RuntimeError, match="needs the professionals directory"):
        await seed_schedules_demo(db_session, clinic.id, dentist.id, dentist.id)

    stats = await seed_schedules_demo(
        db_session, clinic.id, dentist.id, dentist.id, directory=professionals_directory
    )
    assert stats["professional_shifts"] > 0
