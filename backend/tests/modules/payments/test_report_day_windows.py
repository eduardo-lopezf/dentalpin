"""A report covers the clinic's days, not UTC's.

``Payment.payment_date`` is a DATE and already lands on the clinic's
calendar. ``Refund.refunded_at`` and ``PatientEarnedEntry.performed_at`` are
instants, and the reports bounded them with a **UTC** window. For a Madrid
clinic that ran "1–30 September" from 1 Sept 02:00 to 1 Oct 02:00 local:
the small hours of the first day fell out of the report and the small hours
of the day after fell in.

The fixtures below put money in exactly those two slivers, which is the only
place the two windows disagree — a refund at midday is counted either way.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.patients.models import Patient
from app.modules.payments.models import PatientEarnedEntry, Payment, Refund
from app.modules.payments.service import PaymentReportsService

TZ = "Europe/Madrid"  # UTC+2 in September
ZONE = ZoneInfo(TZ)
PERIOD_FROM = date(2026, 9, 1)
PERIOD_TO = date(2026, 9, 30)

# 00:30 on the first day of the period — inside it, but before UTC midnight,
# so the old window started too late to see it.
INSIDE_FIRST_NIGHT = datetime(2026, 9, 1, 0, 30, tzinfo=ZONE)
# 00:30 on 1 October — outside the period, but the old window ran two hours
# into it and counted this as September.
OUTSIDE_NEXT_MONTH = datetime(2026, 10, 1, 0, 30, tzinfo=ZONE)


@pytest.fixture
async def ctx(db_session: AsyncSession, client: AsyncClient, auth_headers: dict) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = UUID(me.json()["data"]["user"]["id"])
    clinic = Clinic(
        id=uuid4(),
        name="Reports Clinic",
        tax_id="A28007777",
        timezone=TZ,
        currency="EUR",
        settings={},
        account_tier="clinic",
    )
    db_session.add(clinic)
    await db_session.flush()
    db_session.add(ClinicMembership(id=uuid4(), clinic_id=clinic.id, user_id=user_id, role="admin"))
    patient = Patient(id=uuid4(), clinic_id=clinic.id, first_name="Ana", last_name="Informe")
    db_session.add(patient)
    await db_session.commit()
    return {"clinic_id": clinic.id, "patient_id": patient.id, "user_id": user_id}


async def _refund(db: AsyncSession, ctx: dict, amount: str, when: datetime) -> None:
    payment = Payment(
        id=uuid4(),
        clinic_id=ctx["clinic_id"],
        patient_id=ctx["patient_id"],
        amount=Decimal(amount),
        currency="EUR",
        method="cash",
        payment_date=when.date(),
        recorded_by=ctx["user_id"],
    )
    db.add(payment)
    await db.flush()
    db.add(
        Refund(
            id=uuid4(),
            clinic_id=ctx["clinic_id"],
            payment_id=payment.id,
            amount=Decimal(amount),
            method="cash",
            reason_code="duplicate",
            refunded_at=when,
            refunded_by=ctx["user_id"],
        )
    )
    await db.commit()


@pytest.mark.asyncio
async def test_summary_counts_the_first_local_night_and_not_the_next_month(
    db_session: AsyncSession, ctx: dict
) -> None:
    await _refund(db_session, ctx, "10.00", INSIDE_FIRST_NIGHT)
    await _refund(db_session, ctx, "99.00", OUTSIDE_NEXT_MONTH)

    result = await PaymentReportsService.summary(
        db_session, ctx["clinic_id"], "EUR", PERIOD_FROM, PERIOD_TO, TZ
    )
    assert result.total_refunded == Decimal("10.00")
    assert result.refund_count == 1


@pytest.mark.asyncio
async def test_refunds_report_uses_the_same_window(db_session: AsyncSession, ctx: dict) -> None:
    await _refund(db_session, ctx, "10.00", INSIDE_FIRST_NIGHT)
    await _refund(db_session, ctx, "99.00", OUTSIDE_NEXT_MONTH)

    result = await PaymentReportsService.refunds_report(
        db_session, ctx["clinic_id"], "EUR", PERIOD_FROM, PERIOD_TO, TZ
    )
    assert result.total_refunded == Decimal("10.00")


@pytest.mark.asyncio
async def test_by_professional_window_is_the_clinic_day(
    db_session: AsyncSession, ctx: dict
) -> None:
    for amount, when in (("40.00", INSIDE_FIRST_NIGHT), ("77.00", OUTSIDE_NEXT_MONTH)):
        db_session.add(
            PatientEarnedEntry(
                id=uuid4(),
                clinic_id=ctx["clinic_id"],
                patient_id=ctx["patient_id"],
                treatment_id=uuid4(),
                amount=Decimal(amount),
                performed_at=when,
                source_event="test",
            )
        )
    await db_session.commit()

    rows = await PaymentReportsService.by_professional(
        db_session, ctx["clinic_id"], PERIOD_FROM, PERIOD_TO, TZ
    )
    assert sum(r.total_earned for r in rows) == Decimal("40.00")


@pytest.mark.asyncio
async def test_trends_buckets_a_late_night_refund_into_its_local_day(
    db_session: AsyncSession, ctx: dict
) -> None:
    # 00:30 on 1 Sept in Madrid is 31 Aug 22:30 UTC. Bucketing on the raw
    # UTC date filed it under August — a column outside the report.
    await _refund(db_session, ctx, "10.00", INSIDE_FIRST_NIGHT)

    result = await PaymentReportsService.trends(
        db_session, ctx["clinic_id"], "EUR", PERIOD_FROM, PERIOD_TO, "day", TZ
    )
    refunded = {p.bucket_start: p.refunded for p in result.points if p.refunded}
    assert refunded == {date(2026, 9, 1): Decimal("10.00")}


@pytest.mark.asyncio
async def test_reports_refunds_is_not_swallowed_by_the_payment_id_route(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """`/reports/refunds` must resolve to the report, not to a payment id.

    FastAPI resolves in registration order, and `GET /{payment_id}/refunds`
    used to be declared first — so this URL answered 422 "reports is not a
    valid UUID" and the refunds report was unreachable from the app.
    """
    response = await client.get(
        "/api/v1/payments/reports/refunds",
        params={"date_from": "2026-09-01", "date_to": "2026-09-30"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert "total_refunded" in response.json()["data"]
