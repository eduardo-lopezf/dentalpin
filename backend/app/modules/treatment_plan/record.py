"""What this module contributes to a clinical record: the treatment plans
and the prescriptions written from them.

A plan carries its diagnosis and its treatments. Its price does not come
along — a record is not a financial document — and neither do the
internal notes, which are the clinic's, not the chart's.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.record import EntryStatus, RecordEntry, RecordSection, SectionCategory
from app.modules.odontogram.models import Treatment

from .models import PlannedTreatmentItem, TreatmentPlan, TreatmentPrescription
from .service import _item_label


async def _collect_plans(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> list[RecordEntry]:
    result = await db.execute(
        select(TreatmentPlan)
        .where(TreatmentPlan.clinic_id == clinic_id, TreatmentPlan.patient_id == patient_id)
        .options(
            selectinload(TreatmentPlan.items)
            .selectinload(PlannedTreatmentItem.treatment)
            .options(selectinload(Treatment.catalog_item), selectinload(Treatment.teeth))
        )
    )
    return [
        RecordEntry(
            occurred_at=plan.confirmed_at or plan.created_at,
            summary=" · ".join(filter(None, [plan.plan_number, plan.title])),
            detail={
                "status": plan.status,
                "diagnosis_notes": plan.diagnosis_notes,
                "prognosis": plan.prognosis,
                "prognosis_notes": plan.prognosis_notes,
                "confirmed_at": plan.confirmed_at,
                "closed_at": plan.closed_at,
                "closure_reason": plan.closure_reason,
                "items": [
                    {
                        "treatment": _item_label(item),
                        "teeth": [tooth.tooth_number for tooth in item.treatment.teeth]
                        if item.treatment
                        else [],
                        "status": item.status,
                        "completed_at": item.completed_at,
                    }
                    for item in plan.items
                ],
            },
            status=EntryStatus.RETRACTED if plan.deleted_at else EntryStatus.ACTIVE,
            authored_by_professional_id=plan.assigned_professional_id,
            recorded_by_user_id=plan.created_by,
            source_table="treatment_plans",
            source_id=plan.id,
        )
        for plan in result.scalars()
    ]


async def _collect_prescriptions(
    db: AsyncSession, clinic_id: UUID, patient_id: UUID
) -> list[RecordEntry]:
    result = await db.execute(
        select(TreatmentPrescription).where(
            TreatmentPrescription.clinic_id == clinic_id,
            TreatmentPrescription.patient_id == patient_id,
        )
    )
    return [
        RecordEntry(
            occurred_at=prescription.created_at,
            summary=prescription.body,
            detail={
                "treatment_label": prescription.treatment_label,
                "professional_name": prescription.professional_name,
                "professional_license": prescription.professional_license,
            },
            authored_by_professional_id=prescription.professional_id,
            recorded_by_user_id=prescription.issued_by,
            source_table="treatment_prescriptions",
            source_id=prescription.id,
        )
        for prescription in result.scalars()
    ]


def get_record_sections() -> list[RecordSection]:
    return [
        RecordSection(
            name="plans",
            title_key="record.section.plans",
            category=SectionCategory.THERAPEUTIC_PLAN,
            collect=_collect_plans,
            order=10,
        ),
        RecordSection(
            name="prescriptions",
            title_key="record.section.prescriptions",
            category=SectionCategory.THERAPEUTIC_PLAN,
            collect=_collect_prescriptions,
            order=20,
        ),
    ]
