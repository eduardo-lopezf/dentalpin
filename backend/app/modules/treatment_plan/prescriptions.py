"""Prescriptions written from a plan treatment, and their printable PDF.

The doctor block (name, licence) is copied onto the row when the
prescription is issued — see ``TreatmentPrescription``. The clinic block and
the patient's name are read at print time: they identify *who*, and a clinic
that moves keeps handing out its current address.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from html import escape
from io import BytesIO
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.patients.models import Patient
from app.modules.professionals.models import Professional

from .models import PlannedTreatmentItem, TreatmentPrescription
from .service import TreatmentPlanService, _item_label


class ProfessionalNotFoundError(ValueError):
    """The chosen doctor is not in this clinic's directory."""


class PrescriptionService:
    @staticmethod
    async def list_for_item(
        db: AsyncSession, clinic_id: UUID, plan_id: UUID, item_id: UUID
    ) -> list[TreatmentPrescription] | None:
        """Prescriptions of one plan treatment, newest first. None if no such item."""
        item = await TreatmentPlanService._load_item_with_sessions(db, clinic_id, plan_id, item_id)
        if item is None:
            return None
        result = await db.execute(
            select(TreatmentPrescription)
            .where(
                TreatmentPrescription.clinic_id == clinic_id,
                TreatmentPrescription.plan_item_id == item_id,
            )
            .order_by(TreatmentPrescription.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def create(
        db: AsyncSession,
        clinic_id: UUID,
        user_id: UUID,
        plan_id: UUID,
        item_id: UUID,
        body: str,
        professional_id: UUID,
    ) -> TreatmentPrescription | None:
        """Issue a prescription for a plan treatment. None if no such item."""
        item: PlannedTreatmentItem | None = await TreatmentPlanService._load_item_with_sessions(
            db, clinic_id, plan_id, item_id
        )
        if item is None:
            return None
        plan = await TreatmentPlanService.get(db, clinic_id, plan_id)
        if plan is None:
            return None

        professional = (
            await db.execute(
                select(Professional).where(
                    Professional.id == professional_id,
                    Professional.clinic_id == clinic_id,
                )
            )
        ).scalar_one_or_none()
        if professional is None:
            raise ProfessionalNotFoundError("Professional not found")

        prescription = TreatmentPrescription(
            clinic_id=clinic_id,
            patient_id=plan.patient_id,
            plan_item_id=item.id,
            treatment_label=_item_label(item),
            professional_id=professional.id,
            professional_name=professional.full_name,
            professional_license=professional.license_number,
            body=body,
            issued_by=user_id,
        )
        db.add(prescription)
        await db.flush()
        await db.refresh(prescription)
        return prescription

    @staticmethod
    async def get(
        db: AsyncSession, clinic_id: UUID, prescription_id: UUID
    ) -> TreatmentPrescription | None:
        result = await db.execute(
            select(TreatmentPrescription).where(
                TreatmentPrescription.id == prescription_id,
                TreatmentPrescription.clinic_id == clinic_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def render_pdf(
        db: AsyncSession, prescription: TreatmentPrescription, locale: str = "es"
    ) -> bytes:
        clinic = await db.get(Clinic, prescription.clinic_id)
        patient = (
            await db.execute(
                select(Patient).where(
                    Patient.id == prescription.patient_id,
                    Patient.clinic_id == prescription.clinic_id,
                )
            )
        ).scalar_one()
        html = _render_html(prescription, clinic, patient, locale)
        # WeasyPrint is CPU-bound; keep the event loop free.
        return await asyncio.to_thread(_html_to_pdf, html)


_LABELS = {
    "es": {
        "title": "Receta médica",
        "license": "Cédula profesional",
        "patient": "Paciente",
        "age": "Edad",
        "years": "años",
        "date": "Fecha",
        "treatment": "Tratamiento",
        "signature": "Firma",
    },
    "en": {
        "title": "Prescription",
        "license": "Professional licence",
        "patient": "Patient",
        "age": "Age",
        "years": "years",
        "date": "Date",
        "treatment": "Treatment",
        "signature": "Signature",
    },
}


def _age(born: date | None, on: date) -> int | None:
    if born is None:
        return None
    return on.year - born.year - ((on.month, on.day) < (born.month, born.day))


def _address(address: dict | None) -> str:
    if not address:
        return ""
    city = " ".join(filter(None, [address.get("postal_code"), address.get("city")]))
    parts = [address.get("street"), city, address.get("state"), address.get("country")]
    return ", ".join(p for p in parts if p)


def _issued_on(prescription: TreatmentPrescription, clinic: Clinic | None) -> date:
    issued: datetime = prescription.created_at
    try:
        return issued.astimezone(ZoneInfo(clinic.timezone)).date() if clinic else issued.date()
    except Exception:  # unknown tz id — the UTC date is still a date
        return issued.date()


def _render_html(
    prescription: TreatmentPrescription,
    clinic: Clinic | None,
    patient: Patient,
    locale: str,
) -> str:
    labels = _LABELS.get(locale, _LABELS["es"])
    issued_on = _issued_on(prescription, clinic)
    age = _age(patient.date_of_birth, issued_on)

    clinic_lines = []
    if clinic is not None:
        clinic_lines = [
            clinic.legal_name if clinic.legal_name and clinic.legal_name != clinic.name else None,
            _address(clinic.address),
            " · ".join(filter(None, [clinic.phone, clinic.email])),
        ]
    clinic_block = "".join(f"<div>{escape(line)}</div>" for line in clinic_lines if line)

    license_line = (
        f"<div>{labels['license']}: {escape(prescription.professional_license)}</div>"
        if prescription.professional_license
        else ""
    )
    age_cell = (
        f"<div><span class='k'>{labels['age']}:</span> {age} {labels['years']}</div>"
        if age is not None
        else ""
    )
    treatment_cell = (
        f"<div><span class='k'>{labels['treatment']}:</span> "
        f"{escape(prescription.treatment_label)}</div>"
        if prescription.treatment_label
        else ""
    )
    patient_name = escape(f"{patient.first_name} {patient.last_name}")
    doctor = escape(prescription.professional_name)

    return f"""<!DOCTYPE html>
<html lang="{escape(locale)}">
<head>
<meta charset="utf-8">
<title>{labels["title"]}</title>
<style>
  @page {{ size: letter; margin: 16mm 18mm; }}
  body {{ font-family: "Helvetica Neue", Arial, sans-serif; font-size: 11pt; color: #111; }}
  header {{ display: flex; justify-content: space-between; gap: 16px;
            border-bottom: 2px solid #1f2937; padding-bottom: 10px; }}
  .clinic-name {{ font-size: 16pt; font-weight: 700; }}
  .muted {{ color: #4b5563; font-size: 9.5pt; line-height: 1.4; }}
  .doctor {{ text-align: right; }}
  .doctor-name {{ font-weight: 700; font-size: 12pt; }}
  h1 {{ font-size: 13pt; letter-spacing: 0.08em; text-transform: uppercase;
        margin: 14px 0 8px; }}
  .patient {{ display: flex; flex-wrap: wrap; gap: 4px 24px; padding: 8px 0;
              border-bottom: 1px solid #d1d5db; }}
  .k {{ color: #4b5563; }}
  .rx {{ font-size: 20pt; font-weight: 700; margin: 14px 0 4px; }}
  .body {{ white-space: pre-wrap; line-height: 1.6; min-height: 90mm; }}
  .signature {{ margin: 24mm auto 0; width: 70mm; text-align: center;
                border-top: 1px solid #111; padding-top: 4px; }}
</style>
</head>
<body>
  <header>
    <div>
      <div class="clinic-name">{escape(clinic.name) if clinic else ""}</div>
      <div class="muted">{clinic_block}</div>
    </div>
    <div class="doctor">
      <div class="doctor-name">{doctor}</div>
      <div class="muted">{license_line}</div>
    </div>
  </header>
  <h1>{labels["title"]}</h1>
  <div class="patient">
    <div><span class="k">{labels["patient"]}:</span> <strong>{patient_name}</strong></div>
    {age_cell}
    <div><span class="k">{labels["date"]}:</span> {issued_on.strftime("%d/%m/%Y")}</div>
    {treatment_cell}
  </div>
  <div class="rx">Rx</div>
  <div class="body">{escape(prescription.body)}</div>
  <div class="signature">
    <div>{labels["signature"]}</div>
    <div><strong>{doctor}</strong></div>
    <div class="muted">{license_line}</div>
  </div>
</body>
</html>"""


def _html_to_pdf(html: str) -> bytes:
    from weasyprint import HTML

    buffer = BytesIO()
    HTML(string=html).write_pdf(buffer)
    return buffer.getvalue()
