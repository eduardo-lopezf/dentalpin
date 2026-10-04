"""The letterheads of what a clinic prints.

One of the clinic's own and one per professional. What these pin: a
document carries the letterhead of the professional it answers to, the
clinic's when they have none, and **never another doctor's**; a
letterhead belongs to a professional of this clinic; the logo is a small
PNG or JPEG whatever the upload claims; and the three clinical documents
share the one mechanism.
"""

from pathlib import Path
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.letterhead import render_letterhead
from app.modules.professionals.models import Professional

URL = "/api/v1/auth/clinic/settings/letterheads"

#: The smallest PNG there is: one transparent pixel.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360000002000001e221bc330000000049454e44ae426082"
)


async def _doctor(db: AsyncSession, clinic: Clinic, first_name: str) -> Professional:
    professional = Professional(
        id=uuid4(),
        clinic_id=clinic.id,
        first_name=first_name,
        last_name="Ruiz",
        professional_type="dentist",
        is_active=True,
    )
    db.add(professional)
    await db.commit()
    return professional


@pytest.mark.asyncio
async def test_each_document_carries_its_own_professionals_letterhead_never_anothers(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_clinic: Clinic
) -> None:
    marta = await _doctor(db_session, test_clinic, "Marta")
    pablo = await _doctor(db_session, test_clinic, "Pablo")
    nuria = await _doctor(db_session, test_clinic, "Nuria")

    for owner, heading in (
        ("clinic", "Clínica Centro"),
        (marta.id, "Dra. Marta"),
        (pablo.id, "Dr. Pablo"),
    ):
        saved = await client.put(f"{URL}/{owner}", headers=auth_headers, json={"heading": heading})
        assert saved.status_code == 200, saved.text

    async def head(professional_id) -> str:
        return await render_letterhead(db_session, test_clinic.id, professional_id)

    assert "Dra. Marta" in await head(marta.id)
    assert "Dr. Pablo" not in await head(marta.id)
    assert "Dr. Pablo" in await head(pablo.id)
    # Nuria has none: the clinic's, not a colleague's.
    nurias = await head(nuria.id)
    assert "Clínica Centro" in nurias and "Marta" not in nurias and "Pablo" not in nurias
    # A document that answers to nobody is the clinic's too.
    assert "Clínica Centro" in await head(None)

    # Taking Marta's away sends her documents back to the clinic's.
    assert (await client.delete(f"{URL}/{marta.id}", headers=auth_headers)).status_code == 204
    assert "Clínica Centro" in await head(marta.id)

    listed = (await client.get(URL, headers=auth_headers)).json()["data"]
    assert [item["professional_id"] for item in listed] == [None, str(pablo.id)]


@pytest.mark.asyncio
async def test_with_no_letterhead_at_all_the_clinics_name_heads_the_sheet(
    db_session: AsyncSession, test_clinic: Clinic
) -> None:
    assert test_clinic.name in await render_letterhead(db_session, test_clinic.id, None)


@pytest.mark.asyncio
async def test_a_letterhead_belongs_to_a_professional_of_this_clinic(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
) -> None:
    stranger = await client.put(f"{URL}/{uuid4()}", headers=auth_headers, json={"heading": "X"})
    assert stranger.status_code == 404, stranger.text
    nonsense = await client.put(f"{URL}/everyone", headers=auth_headers, json={"heading": "X"})
    assert nonsense.status_code == 404, nonsense.text


@pytest.mark.asyncio
async def test_a_logo_is_a_small_png_or_jpeg_whatever_the_upload_claims(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
) -> None:
    logo = f"{URL}/clinic/logo"
    # Says it is a PNG; it is a script.
    disguised = await client.put(
        logo,
        headers=auth_headers,
        files={"file": ("logo.png", b"<svg onload=alert(1)>", "image/png")},
    )
    assert disguised.status_code == 400, disguised.text
    huge = await client.put(
        logo,
        headers=auth_headers,
        files={"file": ("logo.png", PNG + b"\0" * (513 * 1024), "image/png")},
    )
    assert huge.status_code == 400, huge.text

    # A real one is kept, shown, and removed without losing the words.
    await client.put(f"{URL}/clinic", headers=auth_headers, json={"heading": "Clínica Centro"})
    ok = await client.put(
        logo, headers=auth_headers, files={"file": ("logo.png", PNG, "image/png")}
    )
    assert ok.status_code == 204, ok.text
    shown = await client.get(logo, headers=auth_headers)
    assert shown.content == PNG and shown.headers["content-type"] == "image/png"
    [clinic] = (await client.get(URL, headers=auth_headers)).json()["data"]
    assert clinic["has_logo"] is True

    assert (await client.delete(logo, headers=auth_headers)).status_code == 204
    [clinic] = (await client.get(URL, headers=auth_headers)).json()["data"]
    assert clinic["has_logo"] is False and clinic["heading"] == "Clínica Centro"


@pytest.mark.parametrize(
    "printer",
    [
        "modules/record/pdf.py",
        "modules/consents/pdf.py",
        "modules/patients_clinical/questionnaire_pdf.py",
    ],
)
def test_the_clinical_documents_share_the_one_mechanism(printer: str) -> None:
    """None of them builds a head of its own, or reaches for a letterhead
    by any road but the one that applies the rule."""
    source = (Path(__file__).resolve().parents[1] / "app" / printer).read_text(encoding="utf-8")
    assert "render_letterhead" in source and "LETTERHEAD_CSS" in source, printer
    assert "get_letterhead" not in source and "ClinicLetterhead" not in source, printer


@pytest.mark.asyncio
async def test_a_consent_prints_under_the_letterhead_of_who_explained_it(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient,
    monkeypatch,
) -> None:
    marta = await _doctor(db_session, test_clinic, "Marta")
    pablo = await _doctor(db_session, test_clinic, "Pablo")
    await client.put(f"{URL}/{marta.id}", headers=auth_headers, json={"heading": "Dra. Marta"})
    await client.put(f"{URL}/{pablo.id}", headers=auth_headers, json={"heading": "Dr. Pablo"})

    from app.modules.consents import pdf as consent_pdf

    printed: list[str] = []
    monkeypatch.setattr(consent_pdf, "_html_to_pdf", lambda html: printed.append(html) or b"%PDF")

    consent = await client.post(
        f"/api/v1/consents/patients/{test_patient.id}",
        headers=auth_headers,
        json={
            "kind": "informed",
            "title": "Extracción",
            "body": "Texto de la clínica.",
            "explained_by_professional_id": str(pablo.id),
        },
    )
    letter = await client.get(
        f"/api/v1/consents/{consent.json()['data']['id']}/pdf", headers=auth_headers
    )
    assert letter.status_code == 200, letter.text
    [html] = printed
    assert "Dr. Pablo" in html and "Dra. Marta" not in html


# --- A doctor keeps their own -------------------------------------------------


async def _login_as_dentist(
    db: AsyncSession, clinic: Clinic, professional: Professional | None
) -> dict[str, str]:
    """A dentist's account — not an admin — linked to ``professional``."""
    from app.core.auth.models import ClinicMembership, User
    from app.core.auth.service import create_access_token, hash_password

    user = User(
        email=f"dentist-{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("TestPass1234"),
        first_name="Doc",
        last_name="Tor",
    )
    db.add(user)
    await db.flush()
    db.add(ClinicMembership(id=uuid4(), user_id=user.id, clinic_id=clinic.id, role="dentist"))
    if professional is not None:
        professional.user_id = user.id
    await db.commit()
    return {
        "Authorization": f"Bearer {create_access_token(user.id, token_version=user.token_version)}"
    }


@pytest.mark.asyncio
async def test_a_doctor_sets_up_their_own_letterhead_and_nobody_elses(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_clinic: Clinic
) -> None:
    marta = await _doctor(db_session, test_clinic, "Marta")
    pablo = await _doctor(db_session, test_clinic, "Pablo")
    as_marta = await _login_as_dentist(db_session, test_clinic, marta)

    mine = (await client.get(f"{URL}/mine", headers=as_marta)).json()["data"]
    assert mine["professional_id"] == str(marta.id) and mine["letterhead"] is None
    assert "Marta" in mine["suggested_subheading"]

    # Her own: words and logo.
    saved = await client.put(f"{URL}/{marta.id}", headers=as_marta, json={"heading": "Dra. Marta"})
    assert saved.status_code == 200, saved.text
    logo = await client.put(
        f"{URL}/{marta.id}/logo", headers=as_marta, files={"file": ("l.png", PNG, "image/png")}
    )
    assert logo.status_code == 204, logo.text
    assert (await client.get(f"{URL}/{marta.id}/logo", headers=as_marta)).content == PNG
    mine = (await client.get(f"{URL}/mine", headers=as_marta)).json()["data"]
    assert mine["letterhead"]["heading"] == "Dra. Marta" and mine["letterhead"]["has_logo"]

    # Not a colleague's, not the clinic's — neither words nor logo, nor to remove them.
    for owner in (str(pablo.id), "clinic"):
        refused = await client.put(f"{URL}/{owner}", headers=as_marta, json={"heading": "Mío"})
        assert refused.status_code == 403, (owner, refused.text)
        assert (
            await client.put(
                f"{URL}/{owner}/logo", headers=as_marta, files={"file": ("l.png", PNG, "image/png")}
            )
        ).status_code == 403
        assert (await client.delete(f"{URL}/{owner}", headers=as_marta)).status_code == 403
    # Nor the list of everybody's.
    assert (await client.get(URL, headers=as_marta)).status_code == 403

    # The clinic's administrator still manages hers.
    assert (
        await client.put(f"{URL}/{marta.id}", headers=auth_headers, json={"heading": "Dra. M."})
    ).status_code == 200

    # And she can take her own away.
    assert (await client.delete(f"{URL}/{marta.id}", headers=as_marta)).status_code == 204


@pytest.mark.asyncio
async def test_an_account_that_is_no_professional_has_no_letterhead_of_its_own(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic
) -> None:
    someone = await _doctor(db_session, test_clinic, "Marta")
    unlinked = await _login_as_dentist(db_session, test_clinic, None)

    mine = (await client.get(f"{URL}/mine", headers=unlinked)).json()["data"]
    assert mine == {"professional_id": None, "suggested_subheading": None, "letterhead": None}
    refused = await client.put(f"{URL}/{someone.id}", headers=unlinked, json={"heading": "X"})
    assert refused.status_code == 403, refused.text
