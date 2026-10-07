#!/usr/bin/env python3
"""Gate an image vulnerability report on a reasoned allowlist — ADR 0050.

The image counterpart of ``frontend/scripts/audit-gate.mjs``, and built on
the same choice: a scanner offers a gate that is red forever or one raised
past the severity we care about, and both end with nobody reading it. This
keeps the floor at ``high`` and lists the exceptions one by one.

It reads the SARIF report Docker Scout writes::

    docker scout cves dienteazul-postgres:15.19-1 --format sarif --output report.sarif
    python scripts/image_audit_gate.py postgres report.sarif

The first argument names the image and picks its list in ``ALLOWED``: an
exception is granted to one image for a reason that is about that image,
and does not carry over to another that happens to ship the same package.

It fails (exit 1) on any of:

1. A high or critical finding that is not in that image's list.
2. An allowed finding whose fix has become reachable — the report names a
   fixed version. The entry was a promise to act when that happened.
3. An allowed finding the report no longer carries. A stale exception is
   an exception for whatever takes that name next.

A report that is not a Scout report at all exits 2, and so does an image
this file does not know. "Did not run" must never collapse into "no
findings": an empty object parses fine and lists no vulnerabilities.

What a scanner cannot see is not covered here. PostgreSQL and CPython are
compiled from source in their images, so Scout lists none of their own
CVEs; the workflow that runs this also checks each pinned base against what
upstream publishes, which is the only signal for those.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

FAIL_AT: frozenset[str] = frozenset({"CRITICAL", "HIGH"})

# What Scout writes in `fixed_version` when the distribution has no fix.
NOT_FIXED = "not fixed"

# Entries are promises. Each needs a reason that survives review, and each
# goes the moment its fix is reachable — rule 2 above enforces that.
ALLOWED: dict[str, dict[str, str]] = {
    # postgres/Dockerfile — Alpine.
    "postgres": {
        # Stack overflow in libxml2's DTD-validation error path, fixed
        # upstream in 2.15.4. No Alpine branch has it: 3.24 and edge both
        # ship 2.13.9-r2 (checked on 2026-10-06), so there is nothing to
        # move to, and the Debian image carries the same library with more
        # findings. libxml2 cannot be dropped — PostgreSQL links it for the
        # `xml` type.
        #
        # Reaching it takes a database role feeding hostile XML to an SQL
        # XML function. The application issues no XML in SQL (its only XML
        # is lxml, in the backend) and the port is not published beyond
        # loopback.
        "CVE-2026-86140": (
            "libxml2: no fixed package in any Alpine branch; reached only through "
            "SQL XML functions by an authenticated role, which the app never calls"
        ),
    },
    # backend/Dockerfile — Debian trixie. Each was checked against the built
    # image on 2026-10-06, and none has a fixed package in trixie. A fourth
    # entry, CVE-2026-102010 (libstdc++ pb_ds), lasted a few hours: Scout
    # stopped reporting it the same day and rule 3 took it out.
    "backend": {
        # libstdc++, reported against the `gcc-14` source package (here:
        # libstdc++6 and libgcc-s1; the compiler is not installed).
        # Integer overflow in the aligned `operator new` for sizes near
        # SIZE_MAX. What links libstdc++ here is apt, greenlet, zopfli and
        # codecs inside Pillow's wheel; reaching it needs one of them to
        # request an over-aligned allocation of a size an attacker chose.
        # No path to that is known, which is not the same as none
        # existing: this entry is accepted risk, not a proof.
        "CVE-2026-95619": (
            "libstdc++ aligned operator new overflow on near-SIZE_MAX sizes; unfixed in "
            "every Debian release, no known caller with an attacker-chosen size"
        ),
        # Expat accepts a lone UTF-16 high surrogate. The Debian library
        # (2.8.3) is linked by fontconfig alone, which parses the font
        # configuration shipped in the image. Python does not use it:
        # `pyexpat` carries its own Expat, 2.8.5, the fixed release.
        "CVE-2026-93990": (
            "expat UTF-16 surrogate validation: Debian's libexpat1 is used only by "
            "fontconfig on its own config files; Python bundles the fixed 2.8.5"
        ),
        # Heap overflow in zlib's non-blocking gz* writes. Upstream gives
        # the affected range as 1.3.1.2–1.3.2 — the code was introduced in
        # 1.3.1.2 — and trixie ships 1.3.1; Debian's tracker lists it as
        # vulnerable while that range is settled. Where the code does
        # exist it takes gzprintf() on a non-blocking stream, which
        # neither Python's zlib module nor pg_dump to a pipe does.
        "CVE-2026-85091": (
            "zlib gz_vacate: trixie ships 1.3.1, below the affected 1.3.1.2-1.3.2; "
            "listed by Debian pending triage of the range"
        ),
    },
    # frontend/Dockerfile.prod — Alpine, and nothing on top of it but Node
    # and the built application. No exceptions: the report was empty when
    # this was written, so any high or critical finding is new.
    "frontend": {},
    # docs/portal/Dockerfile — nginx on Alpine serving static files. No
    # exceptions either.
    "docs-portal": {},
}


def load_findings(path: Path) -> list[dict[str, str]] | None:
    """The findings of a Scout SARIF report, or ``None`` if it is not one."""
    try:
        report = json.loads(path.read_text())
        run = report["runs"][0]
        driver = run["tool"]["driver"]
        results = run["results"]
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return None
    if not str(driver.get("name", "")).lower().startswith("docker scout"):
        return None
    if not isinstance(results, list):
        return None

    rules = {rule["id"]: rule.get("properties", {}) for rule in driver.get("rules", [])}
    findings: dict[tuple[str, str], dict[str, str]] = {}
    for result in results:
        rule_id = result["ruleId"]
        props = rules.get(rule_id, {})
        for purl in props.get("purls") or ["?"]:
            findings[(rule_id, purl)] = {
                "id": rule_id,
                "severity": str(props.get("cvssV3_severity") or "UNSPECIFIED").upper(),
                "package": purl.split("?")[0].removeprefix("pkg:"),
                "fixed": str(props.get("fixed_version") or NOT_FIXED),
            }
    return list(findings.values())


def main() -> int:
    if len(sys.argv) != 3:
        print(
            f"usage: image_audit_gate.py <{'|'.join(ALLOWED)}> <scout-report.sarif>",
            file=sys.stderr,
        )
        return 2
    image, report = sys.argv[1], sys.argv[2]

    if image not in ALLOWED:
        print(
            f"image-audit-gate: no list for image {image!r} (known: {', '.join(ALLOWED)}), "
            "so nothing was checked.",
            file=sys.stderr,
        )
        return 2
    allowed = ALLOWED[image]

    findings = load_findings(Path(report))
    if findings is None:
        print(
            f"image-audit-gate: {report} is not a Docker Scout SARIF report, "
            "so nothing was checked. This is not a clean scan.",
            file=sys.stderr,
        )
        return 2

    by_id = {f["id"]: f for f in findings}
    gating = sorted((f for f in findings if f["severity"] in FAIL_AT), key=lambda f: f["id"])

    # The whole picture, never the reason to fail: readable when the job
    # goes red for one finding.
    order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNSPECIFIED"]
    counts = {s: sum(f["severity"] == s for f in findings) for s in order}
    print(f"{image}: " + (", ".join(f"{n} {s.lower()}" for s, n in counts.items() if n) or "none"))

    unlisted = [f for f in gating if f["id"] not in allowed]
    fixable = [f for f in gating if f["id"] in allowed and f["fixed"] != NOT_FIXED]
    stale = [cve for cve in allowed if cve not in by_id]

    for f in gating:
        note = f"allowed — {allowed[f['id']]}" if f["id"] in allowed else "NOT LISTED"
        print(f"{f['severity'].lower():8} {f['id']:16} {f['package']:36} {note}")

    if unlisted:
        print(
            f"\nimage-audit-gate: {len(unlisted)} high or critical finding(s) without an "
            "entry. Fix them — usually by moving the pinned base — or add an entry with "
            "a reason.",
            file=sys.stderr,
        )
    for f in fixable:
        print(
            f"\nimage-audit-gate: {f['id']} is allowed but now fixed in {f['fixed']}. "
            "Move the pinned base and remove the entry.",
            file=sys.stderr,
        )
    for cve in stale:
        print(
            f"\nimage-audit-gate: {cve} is allowed but no longer reported. Remove the entry.",
            file=sys.stderr,
        )
    if unlisted or fixable or stale:
        return 1

    print("\nimage-audit-gate: no unlisted high/critical findings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
