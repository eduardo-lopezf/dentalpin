"""The starter set of plan templates.

Eight shapes that cover most of general practice. They are a starting point,
not a doctrine: a clinic edits them, hides them, and — more usefully — saves
its own from any plan it has already built (``create_from_plan``).

Items are declared by catalog ``internal_code`` rather than by id, because a
template has to survive being seeded into a clinic whose catalog was created
independently. A code that is not in the clinic's catalog is skipped, and a
template whose items are all missing is not created at all: half a template
is worse than none, and the backfill script can fill it in later.

``phase`` is set only where the template disagrees with the catalog default.
"""

from typing import Final, TypedDict


class TemplateItemSpec(TypedDict, total=False):
    code: str
    phase: str | None


class TemplateSpec(TypedDict):
    key: str
    name: str
    description: str
    display_order: int
    items: list[TemplateItemSpec]


PLAN_TEMPLATES: Final[list[TemplateSpec]] = [
    {
        "key": "first_visit",
        "name": "Primera visita",
        "description": (
            "Consulta inicial con registro fotográfico y panorámica. "
            "No requiere seleccionar dientes."
        ),
        "display_order": 10,
        "items": [
            {"code": "DX-VISIT"},
            {"code": "DX-RXPAN"},
            {"code": "DX-PHOTO"},
        ],
    },
    {
        "key": "hygiene_phase",
        "name": "Fase higiénica",
        "description": (
            "Tartrectomía, instrucciones de higiene y revisión de control. "
            "No requiere seleccionar dientes."
        ),
        "display_order": 20,
        "items": [
            {"code": "PREV-CLEAN"},
            {"code": "PREV-HYGIENE-EDU"},
            {"code": "PREV-CHECKUP"},
        ],
    },
    {
        "key": "perio_basic",
        "name": "Tratamiento periodontal básico",
        "description": (
            "Estudio periodontal, raspado y alisado radicular por cuadrante y "
            "reevaluación. Selecciona un diente de cada cuadrante a tratar."
        ),
        "display_order": 30,
        "items": [
            {"code": "PERIO-STUDY"},
            {"code": "PERIO-RAR"},
            {"code": "PERIO-MAINT"},
        ],
    },
    {
        "key": "endo_resto_crown",
        "name": "Endodoncia + reconstrucción + corona",
        "description": (
            "La secuencia de tres pasos sobre la misma pieza. Selecciona el diente a tratar."
        ),
        "display_order": 40,
        "items": [
            {"code": "DX-RXPA"},
            {"code": "ENDO-MULTI"},
            {"code": "REST-RECONSTR"},
            {"code": "REST-CROWN-POST-ENDO"},
        ],
    },
    {
        "key": "single_implant",
        "name": "Implante unitario",
        "description": (
            "Extracción, implante, pilar y corona sobre implante. Selecciona la pieza a reponer."
        ),
        "display_order": 50,
        "items": [
            {"code": "DX-CBCT"},
            {"code": "SURG-EXT-SIMPLE", "phase": "estabilizacion"},
            {"code": "SURG-IMP-TI"},
            {"code": "REST-DEF-ABUT"},
            {"code": "REST-CROWN-IMPL-ZIR"},
        ],
    },
    {
        "key": "third_molars",
        "name": "Extracción de cordales",
        "description": (
            "Extracción quirúrgica. Selecciona los cordales a extraer (18, 28, 38, 48)."
        ),
        "display_order": 60,
        "items": [
            {"code": "DX-RXPAN"},
            {"code": "SURG-EXT-3MOLAR"},
        ],
    },
    {
        "key": "orthodontics",
        "name": "Ortodoncia",
        "description": ("Estudio, aparatología y retención. No requiere seleccionar dientes."),
        "display_order": 70,
        "items": [
            {"code": "DX-STUDY"},
            {"code": "DX-TELE"},
            {"code": "ORTO-METAL"},
            {"code": "ORTO-RET-REM"},
        ],
    },
    {
        "key": "aesthetics",
        "name": "Estética",
        "description": "Blanqueamiento y revisión de control. No requiere seleccionar dientes.",
        "display_order": 80,
        "items": [
            {"code": "EST-BLAN-CLIN"},
            {"code": "PREV-CHECKUP"},
        ],
    },
]
