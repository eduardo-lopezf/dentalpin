"""The workspace's own name and logo, shown in the sidebar (ADR 0043)."""

import pytest
from httpx import AsyncClient

from app.core.auth.models import Clinic

URL = "/api/v1/auth/clinic/settings/brand"
LOGO = f"{URL}/logo"

#: The smallest PNG there is: one transparent pixel.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360000002000001e221bc330000000049454e44ae426082"
)


@pytest.mark.asyncio
async def test_the_workspace_shows_the_clinics_own_name_and_logo(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
) -> None:
    default = (await client.get(URL, headers=auth_headers)).json()["data"]
    assert default == {
        "display_name": None,
        "accent": None,
        "font": None,
        "corners": None,
        "density": None,
        "color_mode": None,
        "has_logo": False,
    }

    saved = await client.put(URL, headers=auth_headers, json={"display_name": "  Dent+Art  "})
    assert saved.json()["data"]["display_name"] == "Dent+Art"

    uploaded = await client.put(
        LOGO, headers=auth_headers, files={"file": ("logo.png", PNG, "image/png")}
    )
    assert uploaded.status_code == 204, uploaded.text
    assert (await client.get(URL, headers=auth_headers)).json()["data"]["has_logo"] is True
    shown = await client.get(LOGO, headers=auth_headers)
    assert shown.content == PNG and shown.headers["content-type"] == "image/png"

    # Back to the product's own.
    assert (await client.delete(LOGO, headers=auth_headers)).status_code == 204
    assert (await client.get(LOGO, headers=auth_headers)).status_code == 404
    cleared = await client.put(URL, headers=auth_headers, json={"display_name": ""})
    assert cleared.json()["data"]["display_name"] is None


@pytest.mark.asyncio
async def test_a_logo_is_a_small_png_or_jpeg_whatever_the_upload_claims(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
) -> None:
    disguised = await client.put(
        LOGO,
        headers=auth_headers,
        files={"file": ("logo.png", b"<svg onload=alert(1)>", "image/png")},
    )
    assert disguised.status_code == 400, disguised.text
    huge = await client.put(
        LOGO,
        headers=auth_headers,
        files={"file": ("logo.png", PNG + b"\0" * (513 * 1024), "image/png")},
    )
    assert huge.status_code == 400, huge.text


@pytest.mark.asyncio
async def test_every_member_reads_it_and_only_an_admin_changes_it(
    client: AsyncClient, db_session, test_clinic: Clinic
) -> None:
    from uuid import uuid4

    from app.core.auth.models import ClinicMembership, User
    from app.core.auth.service import create_access_token, hash_password

    user = User(
        email="reception@example.com",
        password_hash=hash_password("TestPass1234"),
        first_name="Re",
        last_name="Ception",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        ClinicMembership(id=uuid4(), user_id=user.id, clinic_id=test_clinic.id, role="receptionist")
    )
    await db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(user.id, token_version=0)}"}

    assert (await client.get(URL, headers=headers)).status_code == 200
    assert (await client.put(URL, headers=headers, json={"display_name": "x"})).status_code == 403
    assert (
        await client.put(LOGO, headers=headers, files={"file": ("l.png", PNG, "image/png")})
    ).status_code == 403


@pytest.mark.asyncio
async def test_the_clinic_picks_its_accent_and_typeface_from_a_closed_list(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
) -> None:
    saved = await client.put(
        URL,
        headers=auth_headers,
        json={"display_name": "Dent+Art", "accent": "teal", "font": "atkinson"},
    )
    assert saved.status_code == 200, saved.text
    data = saved.json()["data"]
    assert (data["display_name"], data["accent"], data["font"]) == ("Dent+Art", "teal", "atkinson")

    shaped = await client.put(
        URL, headers=auth_headers, json={"corners": "sharp", "density": "compact"}
    )
    assert shaped.status_code == 200, shaped.text
    assert (shaped.json()["data"]["corners"], shaped.json()["data"]["density"]) == (
        "sharp",
        "compact",
    )
    dark = await client.put(URL, headers=auth_headers, json={"color_mode": "dark"})
    assert dark.json()["data"]["color_mode"] == "dark"
    for body in ({"corners": "12px"}, {"density": "tiny"}, {"color_mode": "sepia"}):
        assert (await client.put(URL, headers=auth_headers, json=body)).status_code == 422, body

    # Not a colour picker, and not a font to fetch from somewhere.
    for body in (
        {"accent": "#ff00ff"},
        {"font": "Comic Sans MS"},
        {"font": "https://fonts.example/x"},
    ):
        refused = await client.put(URL, headers=auth_headers, json=body)
        assert refused.status_code == 422, (body, refused.text)

    # Leaving them out goes back to the product's own.
    reset = await client.put(URL, headers=auth_headers, json={"display_name": "Dent+Art"})
    assert reset.json()["data"]["accent"] is None and reset.json()["data"]["font"] is None
