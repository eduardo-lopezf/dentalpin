"""Money written against a day that had already been counted.

Reception records Friday's cash on Monday and Friday was closed on Friday.
Refusing the back-date would only make them file it under today and lie
about the date, so it is allowed — but the count Friday signed no longer
describes Friday, and somebody has to find out.

Two things are pinned here. The first is that the **signed count does not
move**, which phase 2 already held and this phase must not quietly undo. The
second is that a late entry stops being shouted about only when somebody
says what is being done with it: a warning that is always on is a warning
nobody reads, the same failure that kills an arqueo whose difference is
never zero.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.utils.clinic_time import clinic_date
from app.modules.patients.models import Patient
from app.modules.payments.models import Payment, PaymentAllocation, Refund

BASE = "/api/v1/cashbox"
TZ = "America/Mexico_City"
TODAY = clinic_date(datetime.now(UTC), TZ)
YESTERDAY = TODAY - timedelta(days=1)


@pytest.fixture
async def ctx(
    db_session: AsyncSession,
    auth_headers: dict,
    client: AsyncClient,
    test_clinic: Clinic,
) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    patient = Patient(id=uuid4(), clinic_id=test_clinic.id, first_name="Tarde", last_name="Prueba")
    db_session.add(patient)
    await db_session.commit()
    return {
        "clinic_id": test_clinic.id,
        "user_id": UUID(me.json()["data"]["user"]["id"]),
        "patient_id": patient.id,
        "currency": test_clinic.currency,
    }


async def _pay(
    db: AsyncSession,
    ctx: dict,
    amount: str,
    day: date,
    *,
    method: str = "cash",
    reference: str | None = None,
) -> Payment:
    payment = Payment(
        id=uuid4(),
        clinic_id=ctx["clinic_id"],
        patient_id=ctx["patient_id"],
        amount=Decimal(amount),
        currency=ctx["currency"],
        method=method,
        payment_date=day,
        reference=reference,
        recorded_by=ctx["user_id"],
    )
    db.add(payment)
    await db.flush()
    db.add(
        PaymentAllocation(
            id=uuid4(),
            clinic_id=ctx["clinic_id"],
            payment_id=payment.id,
            target_type="on_account",
            amount=Decimal(amount),
            created_by=ctx["user_id"],
        )
    )
    await db.commit()
    return payment


async def _close(client: AsyncClient, headers: dict, day: date, counted: str, **overrides):
    body = {
        "business_date": day.isoformat(),
        "counted_cash": counted,
        "opening_float": "0",
        "closing_float": "0",
    }
    body.update(overrides)
    response = await client.post(f"{BASE}/closings", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _late(client: AsyncClient, headers: dict, **params) -> list[dict]:
    query = {"date_from": YESTERDAY.isoformat(), "date_to": TODAY.isoformat()}
    query.update(params)
    response = await client.get(f"{BASE}/late-entries", params=query, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


# --- Finding them -----------------------------------------------------


async def test_a_payment_written_after_the_count_is_surfaced(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    await _pay(db_session, ctx, "300.00", YESTERDAY)
    await _close(client, auth_headers, YESTERDAY, "300.00")

    await _pay(db_session, ctx, "400.00", YESTERDAY, reference="REF-TARDE")

    entries = await _late(client, auth_headers)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["kind"] == "payment"
    assert Decimal(entry["amount"]) == Decimal("400.00")
    assert entry["business_date"] == YESTERDAY.isoformat()
    assert entry["description"] == "REF-TARDE"
    assert entry["acknowledged"] is False


async def test_the_signed_count_does_not_move(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Phase 2's guarantee, restated here because this phase must not undo it."""
    await _pay(db_session, ctx, "300.00", YESTERDAY)
    closing = await _close(client, auth_headers, YESTERDAY, "300.00")

    await _pay(db_session, ctx, "400.00", YESTERDAY)

    reread = await client.get(f"{BASE}/closings/{closing['id']}", headers=auth_headers)
    data = reread.json()["data"]
    assert Decimal(data["expected_cash"]) == Decimal("300.00")
    assert Decimal(data["difference"]) == Decimal("0")


async def test_a_payment_written_before_the_count_is_not_late(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """It was in the drawer when the drawer was counted. Nothing happened."""
    await _pay(db_session, ctx, "300.00", YESTERDAY)
    await _close(client, auth_headers, YESTERDAY, "300.00")

    assert await _late(client, auth_headers) == []


async def test_a_payment_on_a_day_nobody_counted_is_not_late(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Late means "after the count". With no count there is nothing to be after."""
    await _pay(db_session, ctx, "400.00", YESTERDAY)
    assert await _late(client, auth_headers) == []


async def test_a_card_payment_is_never_late(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """It never entered the drawer, so the count it missed was not about it."""
    await _close(client, auth_headers, YESTERDAY, "0")
    await _pay(db_session, ctx, "900.00", YESTERDAY, method="card")

    assert await _late(client, auth_headers) == []


async def test_a_late_refund_subtracts(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Signed by its effect on the drawer, so the list can simply be summed."""
    payment = await _pay(db_session, ctx, "300.00", YESTERDAY)
    await _close(client, auth_headers, YESTERDAY, "300.00")

    db_session.add(
        Refund(
            id=uuid4(),
            clinic_id=ctx["clinic_id"],
            payment_id=payment.id,
            amount=Decimal("120.00"),
            method="cash",
            reason_code="overpaid",
            # Handed back at 19:00 yesterday, Mexico City — the day it
            # belongs to comes from the clinic's zone, not the timestamp.
            refunded_at=datetime.combine(YESTERDAY, datetime.min.time(), tzinfo=UTC)
            + timedelta(hours=25),
            refunded_by=ctx["user_id"],
        )
    )
    await db_session.commit()

    entries = await _late(client, auth_headers)
    refunds = [e for e in entries if e["kind"] == "refund"]
    assert len(refunds) == 1
    assert Decimal(refunds[0]["amount"]) == Decimal("-120.00")


async def test_a_movement_added_to_a_closed_day_is_late(
    client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """No timestamp comparison needed: closing stamps every open row.

    A movement still carrying no `closing_id` on a day that has one can only
    have arrived afterwards.
    """
    await _close(client, auth_headers, YESTERDAY, "0")

    await client.post(
        f"{BASE}/movements",
        json={
            "business_date": YESTERDAY.isoformat(),
            "direction": "out",
            "amount": "80.00",
            "category": "supplies",
            "concept": "Guantes que no se apuntaron",
        },
        headers=auth_headers,
    )

    entries = await _late(client, auth_headers)
    assert len(entries) == 1
    assert entries[0]["kind"] == "movement"
    assert Decimal(entries[0]["amount"]) == Decimal("-80.00")
    assert entries[0]["description"] == "Guantes que no se apuntaron"


async def test_the_list_carries_no_patient_identity(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """`cashbox` depends on `payments`, not on `patients`.

    A name here would be both a dependency the manifest does not declare and
    PII in a payload that does not need it: the reference and the amount are
    enough to find the row in Cobros, which is where the person belongs.
    """
    await _close(client, auth_headers, YESTERDAY, "0")
    await _pay(db_session, ctx, "400.00", YESTERDAY, reference="REF-9")

    entry = (await _late(client, auth_headers))[0]
    assert "patient_id" not in entry
    assert "Tarde" not in str(entry)
    assert "Prueba" not in str(entry)


async def test_summing_the_list_says_what_the_day_would_read_now(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    await _close(client, auth_headers, YESTERDAY, "0")
    await _pay(db_session, ctx, "400.00", YESTERDAY)
    await client.post(
        f"{BASE}/movements",
        json={
            "business_date": YESTERDAY.isoformat(),
            "direction": "out",
            "amount": "150.00",
            "category": "lab",
            "concept": "Mensajero",
        },
        headers=auth_headers,
    )

    entries = await _late(client, auth_headers)
    assert sum(Decimal(e["amount"]) for e in entries) == Decimal("250.00")


# --- Dealing with them ------------------------------------------------


async def test_acknowledging_takes_it_off_the_list(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Otherwise the list only grows and nobody reads it."""
    await _close(client, auth_headers, YESTERDAY, "0")
    payment = await _pay(db_session, ctx, "400.00", YESTERDAY)

    response = await client.post(
        f"{BASE}/late-entries/acknowledge",
        json={
            "kind": "payment",
            "entry_id": str(payment.id),
            "business_date": YESTERDAY.isoformat(),
            "resolution": "Entra en el arqueo de mañana.",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["acknowledged"] is True

    assert await _late(client, auth_headers) == []


async def test_an_acknowledged_entry_is_still_there_when_asked_for(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Hidden, not erased: the decision is part of the audit trail."""
    await _close(client, auth_headers, YESTERDAY, "0")
    payment = await _pay(db_session, ctx, "400.00", YESTERDAY)
    await client.post(
        f"{BASE}/late-entries/acknowledge",
        json={
            "kind": "payment",
            "entry_id": str(payment.id),
            "business_date": YESTERDAY.isoformat(),
            "resolution": "Entra en el arqueo de mañana.",
        },
        headers=auth_headers,
    )

    entries = await _late(client, auth_headers, include_acknowledged="true")
    assert len(entries) == 1
    assert entries[0]["acknowledged"] is True
    assert entries[0]["resolution"] == "Entra en el arqueo de mañana."
    assert entries[0]["acknowledger"]["id"] == str(ctx["user_id"])


async def test_a_blank_resolution_is_refused(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """ "Seen" is not a decision anybody can act on three months later."""
    await _close(client, auth_headers, YESTERDAY, "0")
    payment = await _pay(db_session, ctx, "400.00", YESTERDAY)

    for resolution in ("", "   "):
        response = await client.post(
            f"{BASE}/late-entries/acknowledge",
            json={
                "kind": "payment",
                "entry_id": str(payment.id),
                "business_date": YESTERDAY.isoformat(),
                "resolution": resolution,
            },
            headers=auth_headers,
        )
        assert response.status_code == 422


async def test_acknowledging_twice_is_refused(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    await _close(client, auth_headers, YESTERDAY, "0")
    payment = await _pay(db_session, ctx, "400.00", YESTERDAY)
    body = {
        "kind": "payment",
        "entry_id": str(payment.id),
        "business_date": YESTERDAY.isoformat(),
        "resolution": "Ya está visto.",
    }
    assert (
        await client.post(f"{BASE}/late-entries/acknowledge", json=body, headers=auth_headers)
    ).status_code == 201
    second = await client.post(f"{BASE}/late-entries/acknowledge", json=body, headers=auth_headers)
    assert second.status_code == 422


async def test_reopening_the_day_is_the_other_answer(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    """Reopen and recount, and there is nothing late any more.

    The entry was late relative to a count that no longer stands; once the
    day is counted again with the payment in it, the list is empty because
    the question it asked has been answered.
    """
    closing = await _close(client, auth_headers, YESTERDAY, "0")
    await _pay(db_session, ctx, "400.00", YESTERDAY)
    assert len(await _late(client, auth_headers)) == 1

    await client.post(
        f"{BASE}/closings/{closing['id']}/reopen",
        json={"reason": "Llegó el cobro del viernes."},
        headers=auth_headers,
    )
    await _close(client, auth_headers, YESTERDAY, "400.00")

    assert await _late(client, auth_headers) == []


async def test_another_clinics_late_entries_are_not_listed(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, ctx: dict
) -> None:
    other = Clinic(
        id=uuid4(),
        name="Otra Clínica",
        tax_id="B77777777",
        settings={},
        account_tier="clinic",
    )
    db_session.add(other)
    await db_session.flush()
    stranger = Patient(id=uuid4(), clinic_id=other.id, first_name="Ajena", last_name="Clinica")
    db_session.add(stranger)
    await db_session.commit()

    await _close(client, auth_headers, YESTERDAY, "0")
    await _pay(
        db_session,
        {**ctx, "clinic_id": other.id, "patient_id": stranger.id},
        "999.00",
        YESTERDAY,
    )

    assert await _late(client, auth_headers) == []
