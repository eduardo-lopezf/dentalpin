"""Tests for the catalog seeder.

Verifies that the seeded catalog includes globally-scoped treatments (cleaning,
whitening, whole-arch prosthesis, etc.) and that every seeded item uses one of
the four valid `treatment_scope` values.
"""

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth.models import Clinic
from app.modules.catalog.models import TreatmentCatalogItem
from app.modules.catalog.seed import seed_catalog

VALID_SCOPES = {"tooth", "multi_tooth", "global_mouth", "global_arch"}


@pytest.fixture
async def seeded_clinic(db_session: AsyncSession) -> Clinic:
    clinic = Clinic(
        id=uuid4(),
        name="Seed Clinic",
        tax_id="B44444444",
        address={"street": "x", "city": "y"},
        settings={"slot_duration_min": 15},
        account_tier="clinic",
    )
    db_session.add(clinic)
    await db_session.flush()
    await seed_catalog(db_session, clinic.id)
    await db_session.commit()
    return clinic


@pytest.mark.asyncio
async def test_seed_creates_global_mouth_items(
    db_session: AsyncSession, seeded_clinic: Clinic
) -> None:
    result = await db_session.execute(
        select(TreatmentCatalogItem).where(
            TreatmentCatalogItem.clinic_id == seeded_clinic.id,
            TreatmentCatalogItem.treatment_scope == "global_mouth",
        )
    )
    items = list(result.scalars().all())
    codes = {i.internal_code for i in items}

    # Essential globals that should always be seeded.
    assert "PREV-CLEAN" in codes
    assert "PREV-FLUOR" in codes
    assert "PREV-CHECKUP" in codes
    assert any(c.startswith("EST-BLAN") for c in codes), (
        "At least one whitening item should be global_mouth"
    )


@pytest.mark.asyncio
async def test_seed_creates_global_arch_items(
    db_session: AsyncSession, seeded_clinic: Clinic
) -> None:
    result = await db_session.execute(
        select(TreatmentCatalogItem).where(
            TreatmentCatalogItem.clinic_id == seeded_clinic.id,
            TreatmentCatalogItem.treatment_scope == "global_arch",
        )
    )
    items = list(result.scalars().all())
    codes = {i.internal_code for i in items}

    assert "REST-SPLINT-OCC" in codes
    assert "PROT-FULL-SUP" in codes
    assert "PROT-FULL-INF" in codes


@pytest.mark.asyncio
async def test_seed_creates_multi_tooth_items(
    db_session: AsyncSession, seeded_clinic: Clinic
) -> None:
    result = await db_session.execute(
        select(TreatmentCatalogItem).where(
            TreatmentCatalogItem.clinic_id == seeded_clinic.id,
            TreatmentCatalogItem.treatment_scope == "multi_tooth",
        )
    )
    items = list(result.scalars().all())
    codes = {i.internal_code for i in items}

    # All bridges must be multi_tooth.
    assert "REST-BRIDGE-MC" in codes
    assert "REST-BRIDGE-ZIR" in codes


@pytest.mark.asyncio
async def test_seed_items_have_valid_scope(db_session: AsyncSession, seeded_clinic: Clinic) -> None:
    result = await db_session.execute(
        select(TreatmentCatalogItem).where(
            TreatmentCatalogItem.clinic_id == seeded_clinic.id,
        )
    )
    items = list(result.scalars().all())
    assert items, "Seeder should create items"
    for item in items:
        assert item.treatment_scope in VALID_SCOPES, (
            f"{item.internal_code} has invalid scope {item.treatment_scope}"
        )


@pytest.mark.asyncio
async def test_seed_assigns_a_specialty_to_every_item(
    db_session: AsyncSession, seeded_clinic: Clinic
) -> None:
    """No treatment is left unclassified.

    The "Sin especialidad" group exists to surface gaps; a freshly seeded
    catalog should not put anything in it, or the specialty-filtered views
    silently hide treatments.
    """
    from app.modules.catalog.models import catalog_item_specialties

    unassigned = await db_session.scalar(
        select(func.count(TreatmentCatalogItem.id)).where(
            TreatmentCatalogItem.clinic_id == seeded_clinic.id,
            TreatmentCatalogItem.deleted_at.is_(None),
            ~select(catalog_item_specialties.c.catalog_item_id)
            .where(catalog_item_specialties.c.catalog_item_id == TreatmentCatalogItem.id)
            .exists(),
        )
    )
    assert unassigned == 0


@pytest.mark.asyncio
async def test_seed_spans_categories_where_a_discipline_does(
    db_session: AsyncSession, seeded_clinic: Clinic
) -> None:
    """Implantology is the case categories cannot express: placing the
    implant is `cirugia`, its crown is `restauradora`, the overdenture is
    `protesis`. All three must land on the one specialty."""
    from app.modules.catalog.models import Specialty, catalog_item_specialties

    implantology = await db_session.scalar(
        select(Specialty.id).where(
            Specialty.clinic_id == seeded_clinic.id,
            Specialty.key == "implantologia",
        )
    )
    assert implantology is not None

    codes = (
        (
            await db_session.execute(
                select(TreatmentCatalogItem.internal_code)
                .join(
                    catalog_item_specialties,
                    catalog_item_specialties.c.catalog_item_id == TreatmentCatalogItem.id,
                )
                .where(catalog_item_specialties.c.specialty_id == implantology)
            )
        )
        .scalars()
        .all()
    )

    assert "SURG-IMP-TI" in codes
    assert "REST-CROWN-IMPL-ZIR" in codes
    assert "PROT-OVERDENT" in codes


@pytest.mark.asyncio
async def test_seed_is_idempotent_for_specialties(
    db_session: AsyncSession, seeded_clinic: Clinic
) -> None:
    """Re-seeding neither duplicates specialties nor their links.

    `Specialty.key` exists for this: matching on the localized name would
    create a second row as soon as a clinic renames one.
    """
    from app.modules.catalog.models import Specialty, catalog_item_specialties

    async def counts() -> tuple[int, int]:
        specialties = await db_session.scalar(
            select(func.count(Specialty.id)).where(Specialty.clinic_id == seeded_clinic.id)
        )
        links = await db_session.scalar(
            select(func.count()).select_from(
                select(catalog_item_specialties.c.catalog_item_id)
                .join(
                    TreatmentCatalogItem,
                    TreatmentCatalogItem.id == catalog_item_specialties.c.catalog_item_id,
                )
                .where(TreatmentCatalogItem.clinic_id == seeded_clinic.id)
                .subquery()
            )
        )
        return specialties, links

    before = await counts()
    await seed_catalog(db_session, seeded_clinic.id)
    await db_session.commit()

    assert await counts() == before


@pytest.mark.asyncio
async def test_reseeding_keeps_a_renamed_specialty(
    db_session: AsyncSession, seeded_clinic: Clinic
) -> None:
    """A clinic that renames a seeded specialty keeps its own wording."""
    from app.modules.catalog.models import Specialty

    specialty = await db_session.scalar(
        select(Specialty).where(
            Specialty.clinic_id == seeded_clinic.id,
            Specialty.key == "ortodoncia",
        )
    )
    specialty.names = {"es": "Ortodoncia y alineadores", "en": "Orthodontics & aligners"}
    await db_session.commit()

    await seed_catalog(db_session, seeded_clinic.id)
    await db_session.commit()

    matching = await db_session.scalar(
        select(func.count(Specialty.id)).where(
            Specialty.clinic_id == seeded_clinic.id,
            Specialty.key == "ortodoncia",
        )
    )
    assert matching == 1
    await db_session.refresh(specialty)
    assert specialty.names["es"] == "Ortodoncia y alineadores"


@pytest.mark.asyncio
async def test_seed_assigns_a_phase_to_every_item(
    db_session: AsyncSession, seeded_clinic: Clinic
) -> None:
    """Every seeded treatment gets a stage of care."""
    unphased = await db_session.scalar(
        select(func.count(TreatmentCatalogItem.id)).where(
            TreatmentCatalogItem.clinic_id == seeded_clinic.id,
            TreatmentCatalogItem.deleted_at.is_(None),
            TreatmentCatalogItem.default_phase.is_(None),
        )
    )
    assert unphased == 0


@pytest.mark.asyncio
async def test_phase_splits_a_category_that_mixes_stages(
    db_session: AsyncSession, seeded_clinic: Clinic
) -> None:
    """`restauradora` holds both disease control and rehabilitation.

    A single "correctivo" bucket would have swallowed two thirds of the
    catalog; the point of the axis is that it separates these.
    """

    async def phase_of(code: str) -> str | None:
        return await db_session.scalar(
            select(TreatmentCatalogItem.default_phase).where(
                TreatmentCatalogItem.clinic_id == seeded_clinic.id,
                TreatmentCatalogItem.internal_code == code,
            )
        )

    assert await phase_of("REST-COMP") == "estabilizacion"
    assert await phase_of("REST-CROWN-ZIR") == "rehabilitacion"
    assert await phase_of("REST-VEN-PORC") == "estetica"
    # Urgency cuts across categories.
    assert await phase_of("SURG-EXT-SIMPLE") == "urgencia"
    assert await phase_of("PERIO-MAINT") == "mantenimiento"


ORTHOGNATHIC_CODES = {
    "MXF-CONS-01",
    "MXF-EST-01",
    "MXF-PREAN-01",
    "MXF-VSP-01",
    "MXF-CIR-01",
    "MXF-GENIO-01",
    "MXF-OSTEO-01",
}


@pytest.mark.asyncio
async def test_seed_creates_the_orthognathic_pathway(
    db_session: AsyncSession, seeded_clinic: Clinic
) -> None:
    """The maxillofacial codes must survive a reset-and-reseed.

    They were built by hand in a clinic and lived only in that database, so
    the first `reset-db` + `seed-demo` took the whole orthognathic pathway
    with it — and with it every plan that referenced those codes.
    """
    rows = await db_session.execute(
        select(TreatmentCatalogItem.internal_code).where(
            TreatmentCatalogItem.clinic_id == seeded_clinic.id,
            TreatmentCatalogItem.internal_code.in_(ORTHOGNATHIC_CODES),
        )
    )
    assert set(rows.scalars().all()) == ORTHOGNATHIC_CODES


@pytest.mark.asyncio
async def test_orthognathic_items_act_on_the_mouth_not_on_a_tooth(
    db_session: AsyncSession, seeded_clinic: Clinic
) -> None:
    """A Le Fort I is not done to a tooth, and the chart must not try to draw it."""
    rows = await db_session.execute(
        select(TreatmentCatalogItem)
        .where(
            TreatmentCatalogItem.clinic_id == seeded_clinic.id,
            TreatmentCatalogItem.internal_code.in_(ORTHOGNATHIC_CODES),
        )
        .options(selectinload(TreatmentCatalogItem.odontogram_mapping))
    )
    for item in rows.scalars():
        assert item.treatment_scope == "global_mouth", item.internal_code
        assert item.odontogram_mapping is not None, item.internal_code
        assert item.odontogram_mapping.visualization_rules == [], item.internal_code


@pytest.mark.asyncio
async def test_the_surgical_act_carries_its_year_of_follow_up(
    db_session: AsyncSession, seeded_clinic: Clinic
) -> None:
    """Sessions belong to the catalog item, not to whoever builds the plan.

    Without them the eight reviews had to be added by hand, one endpoint call
    at a time — and that endpoint was broken, so in practice they could not be
    added at all. Only the first session carries money; the reviews are
    included, and the item stays open until the last one is done.
    """
    item = (
        await db_session.execute(
            select(TreatmentCatalogItem)
            .where(
                TreatmentCatalogItem.clinic_id == seeded_clinic.id,
                TreatmentCatalogItem.internal_code == "MXF-CIR-01",
            )
            .options(selectinload(TreatmentCatalogItem.sessions))
        )
    ).scalar_one()

    sessions = sorted(item.sessions, key=lambda s: s.sequence)
    assert len(sessions) == 8
    assert sum(s.default_price for s in sessions) == item.default_price
    assert sessions[0].default_price == item.default_price
    assert all(s.default_price == 0 for s in sessions[1:])
