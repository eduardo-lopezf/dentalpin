"""A token is verified under the algorithm we chose, never the one it claims.

ADR 0029, invariant 3. `python-jose` has now shipped two algorithm-confusion
flaws (CVE-2024-33663, and CVE-2026-85394 which is its incomplete fix): given
a service's **public** key, an attacker can forge an HS256 token by handing
that key to the HMAC verifier — but only where the verifier was left free to
pick the algorithm from the token's own header.

Neither condition holds here. `ALGORITHM` is HS256 with a symmetric
`SECRET_KEY`, so there is no public key to steal, and both decode sites pin
`algorithms=[...]`. Upstream has published no fixed release — 3.5.0 is the
latest and is affected — so `.github/workflows/security-audit.yml` ignores the
advisory, and this file is what keeps that promise honest: the day someone
decodes without pinning, or moves to an asymmetric algorithm, the reason the
advisory was waived stops being true and this fails instead of the waiver
quietly covering it.

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
        "which is the input both python-jose confusion advisories need — re-check the "
        "--ignore-vuln entries in .github/workflows/security-audit.yml before changing it."
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
