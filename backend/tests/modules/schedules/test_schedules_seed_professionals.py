"""The schedules demo seed must not mint a second directory record.

`scripts/seed_demo.py` creates one `Professional` per clinical user, with
the **account's own id**, and every appointment, plan item and commission in
the demo points at it. The schedules seed derived its own id from that
account and looked only there, so each run added a duplicate of the same
person — in every professional picker — and hung the weekly hours off the
copy nobody books.
"""

from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.professionals.models import Professional
from app.modules.schedules.models import ProfessionalWeeklySchedule
from app.modules.schedules.seed import seed_schedules_demo


async def _account(db: AsyncSession, name: str) -> User:
    """The derived branch copies the name off the account, so it needs one."""
    user = User(
        id=uuid4(),
        email=f"{name}-{uuid4().hex[:8]}@demo.clinic",
        password_hash="x",
        first_name=name.title(),
        last_name="Sinficha",
    )
    db.add(user)
    await db.flush()
    return user


def _derived_id(clinic_id, user_id):
    return uuid5(NAMESPACE_URL, f"dentalpin:legacy-professional:{clinic_id}:{user_id}")


@pytest.fixture
async def clinic(db_session: AsyncSession) -> Clinic:
    clinic = Clinic(
        id=uuid4(),
        name="Schedules Seed Clinic",
        tax_id="B55555555",
        address={"street": "x", "city": "y"},
        settings={"slot_duration_min": 15},
        account_tier="clinic",
    )
    db_session.add(clinic)
    await db_session.flush()
    return clinic


async def _professionals(db: AsyncSession, clinic_id) -> list[Professional]:
    rows = await db.execute(
        select(Professional)
        .where(Professional.clinic_id == clinic_id)
        .execution_options(populate_existing=True)
    )
    return list(rows.scalars().all())


@pytest.mark.asyncio
async def test_hours_land_on_the_record_the_rest_of_the_demo_uses(
    db_session: AsyncSession, clinic: Clinic
) -> None:
    dentist_id, hygienist_id = uuid4(), uuid4()
    for pid, kind in ((dentist_id, "dentist"), (hygienist_id, "hygienist")):
        db_session.add(
            Professional(
                id=pid,
                clinic_id=clinic.id,
                first_name="Demo",
                last_name=kind.title(),
                professional_type=kind,
                license_number=f"{kind}-1",
            )
        )
    await db_session.flush()

    await seed_schedules_demo(
        db_session, clinic_id=clinic.id, dentist_id=dentist_id, hygienist_id=hygienist_id
    )

    # No second record for the same person.
    assert {p.id for p in await _professionals(db_session, clinic.id)} == {
        dentist_id,
        hygienist_id,
    }

    # And the weekly hours hang off those records, not off a derived copy.
    owners = (
        (
            await db_session.execute(
                select(ProfessionalWeeklySchedule.professional_id).where(
                    ProfessionalWeeklySchedule.clinic_id == clinic.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert set(owners) == {dentist_id, hygienist_id}


@pytest.mark.asyncio
async def test_a_second_run_adds_nobody(db_session: AsyncSession, clinic: Clinic) -> None:
    dentist_id, hygienist_id = uuid4(), uuid4()
    for pid, kind in ((dentist_id, "dentist"), (hygienist_id, "hygienist")):
        db_session.add(
            Professional(
                id=pid,
                clinic_id=clinic.id,
                first_name="Demo",
                last_name=kind.title(),
                professional_type=kind,
            )
        )
    await db_session.flush()

    for _ in range(2):
        await seed_schedules_demo(
            db_session, clinic_id=clinic.id, dentist_id=dentist_id, hygienist_id=hygienist_id
        )

    count = await db_session.execute(
        select(func.count(Professional.id)).where(Professional.clinic_id == clinic.id)
    )
    assert count.scalar_one() == 2


@pytest.mark.asyncio
async def test_an_account_with_no_record_still_gets_one(
    db_session: AsyncSession, clinic: Clinic
) -> None:
    """The derived id keeps serving the case it was written for."""
    dentist_id = (await _account(db_session, "dentist")).id
    hygienist_id = (await _account(db_session, "hygienist")).id

    await seed_schedules_demo(
        db_session, clinic_id=clinic.id, dentist_id=dentist_id, hygienist_id=hygienist_id
    )

    assert {p.id for p in await _professionals(db_session, clinic.id)} == {
        _derived_id(clinic.id, dentist_id),
        _derived_id(clinic.id, hygienist_id),
    }


@pytest.mark.asyncio
async def test_a_record_in_another_clinic_is_not_borrowed(
    db_session: AsyncSession, clinic: Clinic
) -> None:
    """Same account id, different clinic: the directory is per clinic."""
    other = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B66666666",
        address={"street": "x", "city": "y"},
        settings={},
        account_tier="clinic",
    )
    db_session.add(other)
    await db_session.flush()

    dentist_id = (await _account(db_session, "dentist")).id
    hygienist_id = (await _account(db_session, "hygienist")).id
    db_session.add(
        Professional(
            id=dentist_id,
            clinic_id=other.id,
            first_name="Elsewhere",
            last_name="Dentist",
            professional_type="dentist",
        )
    )
    await db_session.flush()

    await seed_schedules_demo(
        db_session, clinic_id=clinic.id, dentist_id=dentist_id, hygienist_id=hygienist_id
    )

    assert {p.id for p in await _professionals(db_session, clinic.id)} == {
        _derived_id(clinic.id, dentist_id),
        _derived_id(clinic.id, hygienist_id),
    }
