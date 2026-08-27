"""The invoice payment breakdown must carry the payment's date and method.

Audit S5, "fiscal display drift": the UI reads `payment_date` and
`payment_method` off `GET /invoices/{id}/payments`, but the response
schema carried neither — so the breakdown rendered the date as "-" and
the method as "undefined" on a money screen. The service already
eager-loads the payment, so the data was there all along; only the
response dropped it.
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
from app.modules.billing.models import Invoice, InvoiceItem, InvoiceSeries
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
async def test_payment_breakdown_carries_date_and_method(
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

    paid_on = date.today().isoformat()
    paid = await client.post(
        f"/api/v1/billing/invoices/{invoice.id}/payments",
        json={"amount": "40.00", "method": "card", "payment_date": paid_on},
        headers=auth_headers,
    )
    assert paid.status_code == 201, paid.text

    listing = await client.get(
        f"/api/v1/billing/invoices/{invoice.id}/payments", headers=auth_headers
    )
    assert listing.status_code == 200, listing.text

    rows = listing.json()["data"]
    assert len(rows) == 1
    row = rows[0]
    assert row["payment_date"] == paid_on
    assert row["payment_method"] == "card"
    assert Decimal(str(row["amount"])) == Decimal("40.00")
