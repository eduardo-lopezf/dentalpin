"""The reference catalogue is data, and the data holds together (ADR 0048).

One file per discipline, every treatment saying everything about itself.
The loader refuses a file that does not; these pin what it refuses, and
what somebody editing a file can rely on.
"""

import json

import pytest

from app.modules.catalog import reference
from app.modules.catalog.reference import (
    BY_CODE,
    CATEGORY_KEYS,
    REFERENCE_DIR,
    SPECIALTY_FILES,
    SPECIALTY_ORDER,
    SpecialtyFile,
)
from app.modules.catalog.seed import CATEGORIES, TREATMENTS


def test_there_is_one_file_per_discipline_and_nothing_else() -> None:
    assert tuple(SPECIALTY_FILES) == SPECIALTY_ORDER
    assert sorted(path.stem for path in REFERENCE_DIR.glob("*.json")) == sorted(SPECIALTY_ORDER)
    # Ten a clinic starts with, seven it adds.
    assert sum(file.baseline for file in SPECIALTY_FILES.values()) == 10


def test_a_treatment_is_written_once_in_the_file_of_its_first_discipline() -> None:
    codes = [t.code for file in SPECIALTY_FILES.values() for t in file.treatments]
    assert len(codes) == len(set(codes)) == len(BY_CODE)
    for owner, treatment in BY_CODE.values():
        assert treatment.category in CATEGORY_KEYS, treatment.code
        assert set(treatment.specialties) <= set(SPECIALTY_ORDER), treatment.code
        assert len(set(treatment.specialties)) == len(treatment.specialties), treatment.code
        assert treatment.specialties[0] == owner, treatment.code
        # A reference without a price or a duration is not a starting point.
        assert treatment.price is not None and treatment.minutes is not None, treatment.code


def test_every_subarea_is_used_and_no_discipline_is_offered_empty() -> None:
    for key, file in SPECIALTY_FILES.items():
        used = {treatment.subarea for treatment in file.treatments}
        assert used == {subarea.key for subarea in file.subareas}, key
        assert file.treatments, key


def test_the_seed_reads_the_same_catalogue() -> None:
    assert {category["key"] for category in CATEGORIES} == set(CATEGORY_KEYS)
    seeded = {item["internal_code"] for items in TREATMENTS.values() for item in items}
    assert seeded == set(BY_CODE)


def _orthodontics() -> dict:
    return json.loads((REFERENCE_DIR / "ortodoncia.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        # A field nobody defined: a typo must not pass for data.
        ("prise", "10.00"),
        # A sub-area the file does not list.
        ("subarea", "magia"),
        # A stage of care that does not exist.
        ("phase", "algun_dia"),
        # Somebody else's discipline first, in this file.
        ("specialties", ["general", "ortodoncia"]),
        # A code that is not a code.
        ("code", "orto retenedor"),
    ],
)
def test_a_file_that_does_not_hold_together_is_refused(field: str, value: object) -> None:
    doc = _orthodontics()
    SpecialtyFile.model_validate(doc)  # as written, it holds
    doc["treatments"][0][field] = value
    with pytest.raises(ValueError):
        SpecialtyFile.model_validate(doc)


def test_the_loader_refuses_a_repeated_code_and_a_stray_file(tmp_path, monkeypatch) -> None:
    for path in REFERENCE_DIR.glob("*.json"):
        (tmp_path / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(reference, "REFERENCE_DIR", tmp_path)
    assert len(reference._load()) == len(SPECIALTY_ORDER)

    # The same treatment in two files.
    pristine = (tmp_path / "higiene.json").read_text(encoding="utf-8")
    general = json.loads((tmp_path / "general.json").read_text(encoding="utf-8"))
    hygiene = json.loads(pristine)
    hygiene["treatments"].append(
        dict(
            general["treatments"][0],
            specialties=["higiene"],
            subarea=hygiene["subareas"][0]["key"],
        )
    )
    (tmp_path / "higiene.json").write_text(json.dumps(hygiene), encoding="utf-8")
    with pytest.raises(ValueError, match="is in both"):
        reference._load()
    (tmp_path / "higiene.json").write_text(pristine, encoding="utf-8")

    # A discipline nobody recognises.
    stray = dict(json.loads(pristine), key="astrologia", subareas=[], treatments=[])
    (tmp_path / "astrologia.json").write_text(json.dumps(stray), encoding="utf-8")
    with pytest.raises(ValueError, match="astrologia"):
        reference._load()
