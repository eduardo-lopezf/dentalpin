"""Every response carries the headers that bound what a browser will do.

ADR 0029, invariant 4. The point of the test is coverage, not the exact
policy string: these headers used to be absent everywhere, and the way
they come back is one handler at a time setting its own.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings

EXPECTED = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow",
}


@pytest.mark.asyncio
@pytest.mark.parametrize("header,value", EXPECTED.items())
async def test_ok_response_carries_header(client: AsyncClient, header: str, value: str) -> None:
    response = await client.get("/api/v1")

    assert response.status_code == 200
    assert response.headers[header] == value


@pytest.mark.asyncio
async def test_unauthenticated_401_carries_headers(client: AsyncClient) -> None:
    """Error paths too — a 401 is still a response a browser renders."""
    response = await client.get("/api/v1/patients")

    assert response.status_code == 401
    for header, value in EXPECTED.items():
        assert response.headers[header] == value


@pytest.mark.asyncio
async def test_csp_forbids_everything_on_json(client: AsyncClient) -> None:
    response = await client.get("/api/v1")

    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp


@pytest.mark.asyncio
async def test_hsts_is_production_only(client: AsyncClient) -> None:
    """Pinning HSTS from a plaintext dev server would strand localhost."""
    response = await client.get("/api/v1")

    assert settings.ENVIRONMENT != "production"
    assert "Strict-Transport-Security" not in response.headers
