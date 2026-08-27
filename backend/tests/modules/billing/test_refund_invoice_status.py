"""S2 — a refund must move its invoice out of ``paid``.

``docs/technical/audit-2026-07-03.md`` S2: publishers ``flush()`` and then
``publish()`` inside a request whose transaction has not committed, while
handlers run inline in their **own** session. So
``billing.on_payment_refunded`` recomputes the invoice from a database
where the ``Refund`` row does not exist yet, decides nothing changed, and
the invoice stays ``paid`` after being refunded. Deterministic, silent,
and about money.

This is the whole bug in one HTTP flow: issue → pay → refund → look.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.billing.models import Invoice, InvoiceItem, InvoicePayment, InvoiceSeries
from app.modules.patients.models import Patient


async def _issued_invoice(db: AsyncSession, clinic: Clinic, patient: Patient) -> Invoice:
    user_id = (await db.execute(select(User))).scalars().first().id
    db.add(
        InvoiceSeries(
            id=uuid4(),
            clinic_id=clinic.id,
            prefix="FAC",
            series_type="invoice",
            is_default=True,
        )
    )
    invoice = Invoice(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        status="draft",
        billing_name="Cliente Test",
        billing_tax_id="B12345678",
        subtotal=Decimal("100.00"),
        total=Decimal("100.00"),
        created_by=user_id,
    )
    db.add(invoice)
    await db.flush()
    db.add(
        InvoiceItem(
            id=uuid4(),
            clinic_id=clinic.id,
            invoice_id=invoice.id,
            description="Servicio",
            unit_price=Decimal("100.00"),
            quantity=1,
            vat_rate=0.0,
            line_subtotal=Decimal("100.00"),
            line_tax=Decimal("0.00"),
            line_total=Decimal("100.00"),
            display_order=0,
        )
    )
    await db.commit()
    return invoice


@pytest.mark.asyncio
async def test_refunded_invoice_does_not_stay_paid(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    invoice = await _issued_invoice(db_session, test_clinic, test_patient)

    issued = await client.post(
        f"/api/v1/billing/invoices/{invoice.id}/issue", json={}, headers=auth_headers
    )
    assert issued.status_code == 200, issued.text

    paid = await client.post(
        f"/api/v1/billing/invoices/{invoice.id}/payments",
        json={"amount": "100.00", "method": "cash", "payment_date": date.today().isoformat()},
        headers=auth_headers,
    )
    assert paid.status_code == 201, paid.text

    await db_session.refresh(invoice)
    assert invoice.status == "paid", "precondition: the invoice is collected in full"

    payment_id = (
        await db_session.execute(
            select(InvoicePayment.payment_id).where(InvoicePayment.invoice_id == invoice.id)
        )
    ).scalar_one()

    refunded = await client.post(
        f"/api/v1/payments/{payment_id}/refunds",
        json={"amount": "100.00", "method": "cash", "reason_code": "duplicate"},
        headers=auth_headers,
    )
    assert refunded.status_code == 201, refunded.text

    await db_session.refresh(invoice)
    assert invoice.status != "paid", (
        "the invoice is still 'paid' after a full refund — the "
        "payment.refunded handler ran before the refund was committed"
    )
    assert invoice.status == "issued"
