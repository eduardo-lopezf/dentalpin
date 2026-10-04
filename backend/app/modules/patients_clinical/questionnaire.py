"""The health questionnaire a patient answers at a visit: what is asked.

The questions and the checklist of conditions, by key. The wording lives
with the screen (``healthQuestionnaire`` in the frontend locales) and is
copied for the printed form by ``scripts/generate_record_labels.py``.

A fixed form, not a per-clinic one: changing a question changes what
earlier answers meant, so a new question is a new key and
``FORM_VERSION`` moves. Stored answers keep the version they were given
under.
"""

from __future__ import annotations

FORM_VERSION = "1"

#: Yes/no questions, in the order they are asked. Any may carry a detail
#: ("cause", "which one").
QUESTIONS: tuple[str, ...] = (
    "medical_care_2y",
    "hospitalized_5y",
    "taking_medication",
    "drug_food_allergy",
    "prior_surgery",
    "anesthesia_reaction",
    "major_bleeding",
    "problem_after_dental_treatment",
    "weight_change_10kg",
    "pregnant",
    "breastfeeding",
    "contraceptive",
)

#: Conditions the patient has or has had, in the blocks the paper form
#: prints them in.
CONDITION_GROUPS: dict[str, tuple[str, ...]] = {
    "cardiovascular": (
        "hypotension",
        "hypertension",
        "heart_failure",
        "angina",
        "myocardial_infarction",
        "rheumatic_fever",
        "tachycardia",
        "bradycardia",
        "pacemaker",
        "arteriosclerosis",
        "atherosclerosis",
        "headache",
        "tinnitus",
        "phosphenes",
        "dizziness",
        "fainting",
        "obesity",
        "overweight",
        "exertional_chest_pain",
        "resting_chest_pain",
        "heart_murmur",
        "evening_leg_edema",
        "cyanosis",
        "bruising",
        "anemia",
        "epistaxis",
        "thrombosis",
        "transfusion",
        "blood_donor",
        "organ_donor",
        "stroke",
        "epigastric_pain",
    ),
    "systemic": (
        "gastric_ulcer",
        "reflux",
        "gastritis",
        "colitis",
        "diabetes",
        "sinusitis",
        "bronchitis",
        "glaucoma",
        "emphysema",
        "tuberculosis",
        "pharyngotonsillitis",
        "digestive_problems",
        "hepatitis",
        "gallbladder",
        "cirrhosis",
        "epilepsy",
        "hyperthyroidism",
        "seizures",
        "alcoholism",
        "smoking",
        "drugs",
        "hypothyroidism",
        "goiter",
        "asthma",
        "gout",
    ),
    "renal_other": (
        "kidney_infection",
        "kidney_stone",
        "dialysis",
        "prostate_problems",
        "cancer",
        "chemotherapy",
        "radiotherapy",
        "bisphosphonates",
        "std",
        "hiv_aids",
    ),
}

CONDITIONS: frozenset[str] = frozenset(key for group in CONDITION_GROUPS.values() for key in group)
