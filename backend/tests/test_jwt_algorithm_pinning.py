"""A token is verified under the algorithm we chose, never the one it claims.

ADR 0029, invariant 3. Algorithm confusion is the flaw this guards against:
given a service's **public** key, an attacker forges an HS256 token by
handing that key to the HMAC verifier — possible only where the verifier is
left free to pick the algorithm from the token's own header.

This file was first written to keep a waiver honest. `python-jose` shipped
that flaw twice (CVE-2024-33663, then CVE-2026-85394, its incomplete fix)
with no fixed release, and the audit ignored the advisory on the strength of
the two conditions below. The library is gone — tokens are signed and
verified with PyJWT, which refuses a PEM key as an HMAC secret and will not
decode without `algorithms` — and so is the waiver. The conditions stay,
because they are the invariant and no library should be the only thing
holding it: `ALGORITHM` is HS256 with a symmetric `SECRET_KEY`, so there is
no public key to steal, and every decode site pins `algorithms=[...]`.

An AST walk rather than a grep, for the same reason as
``test_no_dynamic_sql.py``: what matters is the shape of the call, not that
the word appears somewhere in the file.
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.config import settings

APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def _decode_calls() -> list[tuple[Path, ast.Call]]:
    """Every ``jwt.decode(...)`` / ``jws.verify(...)`` in application code."""
    found: list[tuple[Path, ast.Call]] = []
    for path in APP_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            owner = node.func.value
            owner_name = owner.id if isinstance(owner, ast.Name) else ""
            if (owner_name, node.func.attr) in {("jwt", "decode"), ("jws", "verify")}:
                found.append((path, node))
    return found


def test_the_configured_algorithm_is_symmetric() -> None:
    """HS* takes a shared secret, so there is no public key to forge with."""
    assert settings.ALGORITHM.startswith("HS"), (
        f"ALGORITHM is {settings.ALGORITHM!r}. An asymmetric algorithm publishes a key, "
        "which is the input an algorithm-confusion forgery needs, and the code signs and "
        "verifies with the one SECRET_KEY — moving off HS* is a design change, not a setting."
    )


def test_every_decode_pins_its_algorithms() -> None:
    calls = _decode_calls()
    assert calls, "no decode call found — has the scan stopped matching?"

    unpinned = [
        f"{path.relative_to(APP_ROOT)}:{node.lineno}"
        for path, node in calls
        if not any(keyword.arg == "algorithms" for keyword in node.keywords)
    ]

    assert not unpinned, (
        "these verify a token under whatever algorithm its header asks for: "
        f"{', '.join(unpinned)}. Pass algorithms=[settings.ALGORITHM]."
    )
