# 0050 — A deployed image is pinned, carries only what runs, and is audited

- **Status:** accepted
- **Date:** 2026-10-06
- **Deciders:** Eduardo
- **Tags:** security, operations, deployment, ci

## Context

[ADR 0029](0029-security-invariants-with-chokepoints.md) named dependency
scanning as a decision of its own, and `security-audit.yml` answered it
for Python and npm packages. The images those packages ship in were not
covered by anything, and nobody had looked.

On 2026-10-06 Docker Scout was run on them for the first time:

| Image | Findings | Critical | High |
|---|---|---|---|
| PostgreSQL (`postgres:15-alpine`) | 71 | 4 | 33 |
| Backend | 156 | 1 | 10 |
| Frontend, production | 22 | 0 | 9 |
| Documentation portal | 18 | 0 | 5 |

Three things explained almost all of it, and none of them was the
application.

**A floating tag is pulled once.** `postgres:15-alpine` had been pulled in
July and sat there: PostgreSQL 15.18, three months behind. 15.19 fixes 36
CVEs in the server, several of them code execution at CVSS 8.8 and two in
`pgcrypto`, which the main database has installed — and the scanner listed
none, because PostgreSQL is compiled from source in that image and leaves
no package to recognise. The most serious problem was the one the report
could not show.

**Images carry things nothing runs.** The official PostgreSQL image starts
as root and drops privileges through `gosu`, a Go binary whose runtime
accounted for 46 of the 57 findings left after updating. The backend image
shipped the compiler it had used to build its dependencies (`binutils`
alone: 70 findings) and libraries WeasyPrint stopped loading at version
53. The frontend image shipped npm, which production never calls: 21 of
its 22. The portal ran on the full nginx image for a configuration that
uses none of its extra modules.

**Deleting is not removing.** A file removed in a layer on top stays in the
layer below, and a scanner reads layers. Measured: with `gosu` deleted in
a new layer the report was the same 57 findings.

## Decision

**Every image this repository deploys is pinned to a digest, carries only
what its process runs, does not start as root, and is scanned in CI
against a list of reasoned exceptions.**

It applies to `postgres/Dockerfile`, the `prod` stage of
`backend/Dockerfile`, `frontend/Dockerfile.prod` and
`docs/portal/Dockerfile`. Five rules.

1. **The base is pinned by version and digest**, never by a floating tag.
   Moving it is an edit to the Dockerfile, which is a commit, which is a
   reason to redeploy. The pin is not left to go stale in silence: the
   audit compares it with what upstream's floating tag for that line
   publishes today and fails when they differ. That comparison is the only
   signal for what a scanner cannot see — PostgreSQL's own CVEs, and
   CPython's.

2. **What does not run is not in the image.** Compilation happens in a
   build stage and only its result is copied. What the base image ships
   and production never calls — `gosu`, pip and setuptools, npm, yarn and
   corepack — is removed. Where the thing removed lives in the base's own
   layers, the runtime filesystem is **flattened**: copied into an empty
   image, with the metadata that copy drops declared again. Only the base
   is flattened; dependencies and application code stay layers of their
   own on top, so a code change rebuilds and ships only the code.

3. **The process does not start as root.** PostgreSQL starts as `postgres`,
   the backend as `appuser`, the frontend as `node`. Starting as the
   target user is also what makes `gosu` removable rather than something
   to rebuild. The portal is the exception, for now: see what is not
   covered, below.

4. **A fix the distribution has and the pinned base does not is asked for
   by name and version** in the Dockerfile (`apk add 'zlib>=1.3.2-r1'`),
   with the CVE beside it. The build fails if it cannot be met, and the
   line goes when the pin moves to a base that carries it. Never a blanket
   `apk upgrade`: that changes the image without changing the repository,
   which is the staleness this ADR exists to end, turned around.

5. **The audit has a floor and a list.** The `image-advisories` job builds
   each image, scans it with Docker Scout and hands the report to
   `scripts/image_audit_gate.py`. The floor is `high`. Exceptions are
   listed one by one, per image, each with a reason about *that* image; an
   exception granted to one does not cover another that ships the same
   package. An exception fails the job as loudly as a new finding when its
   fix becomes available, and when the finding stops being reported. A
   report that is not a Scout report, or an image the script does not
   know, is an error and not a pass.

An image we build is tagged with the version of what it runs and a counter
for our own rebuilds on it (`dienteazul-postgres:15.19-1`). Compose reuses
an image it already has under a tag; a tag it does not have is one it has
to build.

## Consequences

### Good

- The same day, with rules 1 to 4: PostgreSQL 71 → 11, backend 156 → 43,
  frontend 22 → 0, portal 18 → 0. No critical finding is left in any of
  them, and what is left has no fixed package in its distribution.
- The 36 PostgreSQL CVEs are closed, which no scanner asked for.
- Falling behind is now a red job instead of something found by accident.
  It worked on its first day in both directions: a new high finding in
  zlib surfaced in the PostgreSQL image hours after the gate was written,
  and an exception that Scout stopped reporting was taken out by the rule
  on stale entries.
- Smaller images: the backend from 1.13 GB to 710 MB, the frontend from
  283 MB to 253 MB, the portal from 164 MB to 92 MB.
- A database, backend or frontend process compromised from the network
  does not land as root in its container.

### Bad / accepted trade-offs

- **These are now our images to maintain.** Flattening discards the
  upstream image's metadata, and what is declared again can drift from it
  on a version bump. Only `PG_VERSION` is checked by the build; the rest
  is checked by a person reading the upstream Dockerfile.
- **The job goes red on the world's schedule, not ours.** Official images
  are republished often — Python's more than PostgreSQL's — and advisories
  appear and disappear within hours. It runs on pull requests too, so a
  change that touches none of this can be the one that shows it.
- It needs a Docker Hub login (`DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`),
  because Scout answers to nothing else, and is skipped on pull requests
  from forks. The gate reads Scout's SARIF and nothing else: changing
  scanner means rewriting how the report is read.
- **The list is a place to hide**, the same hazard as ADR 0029's
  allowlists. One of the backend's three entries (`libstdc++`'s aligned
  `operator new`) is written down as accepted risk and not as proof: no
  path to it is known, which is not the same as none existing.
- An existing data volume must already belong to the user the image
  starts as (uid 70 for PostgreSQL on Alpine). One created by the Debian
  variant would not start.
- A flattened image shares no layers with its base and loses the base's
  provenance attestations, and Scout can no longer tell which base it came
  from.
- **Not covered.** The portal still starts as root: nginx binds port 80,
  and changing that changes the port the deployment exposes. The service
  containers in `ci.yml` run the official PostgreSQL image, pinned,
  because Actions cannot build one for a service. Development images
  (`frontend/Dockerfile`, `control/ui/Dockerfile`) follow none of this;
  they are not deployed and their ports are published on loopback only.
- The backend has no lock file for Python dependencies, so every rebuild
  resolves them again. Rule 1 pins the base and not what is installed on
  it.

## Alternatives considered

- **Keep the official images and pull them regularly** — fixes the system
  packages and the PostgreSQL version, and nothing else: `gosu`'s runtime,
  npm and the compiler come with the image at any date.
- **Mark the findings as not affected (VEX) and leave the files** — it
  records an argument about reachability for code that is present. Where
  the code could simply not be there, removing it is the stronger claim
  and needs no argument.
- **Rebuild `gosu` with a current Go** — one more binary to maintain, for
  a step that starting as `postgres` skips entirely.
- **Move the backend to Alpine** — its Python base reports 2 high findings
  against Debian's 5. It is a change of libc under a dozen compiled
  dependencies and was not tried; the three findings left on Debian are
  listed instead.
- **Vendor-hardened images** — offered for bases like these, behind a
  subscription or a second registry. Not evaluated.
- **Upgrade every package at build time** — see rule 4.

## How to verify the rule still holds

- `.github/workflows/security-audit.yml`, job `image-advisories`: one
  matrix entry per deployed image. Rules 1 and 5.
- `python3 scripts/image_audit_gate.py <image> <report.sarif>` on a report
  from `docker scout cves <image> --format sarif`. Rule 5.
- `grep -nE '^(FROM|ARG [A-Z_]+_IMAGE=)' postgres/Dockerfile backend/Dockerfile frontend/Dockerfile.prod docs/portal/Dockerfile`
  — every base that reaches a final stage carries `@sha256:`. The portal's
  builder stage is the one exception; it is not shipped. Rule 1.
- `docker image inspect <image> --format '{{.Config.User}}'` is not empty
  for the database, the backend and the frontend. Rule 3.
- **Nothing checks that a new Dockerfile joins the matrix.** A fifth
  deployed image would be outside all of this until someone adds it.

## References

- [ADR 0029](0029-security-invariants-with-chokepoints.md) — dependency
  scanning named as its own decision; the allowlist pattern
- [ADR 0049](0049-the-control-plane-is-a-separate-service.md) — a tenant's
  stack runs these same three images
- `postgres/Dockerfile`, `backend/Dockerfile`, `frontend/Dockerfile.prod`,
  `docs/portal/Dockerfile`
- `scripts/image_audit_gate.py` — the exceptions and their reasons
- `frontend/scripts/audit-gate.mjs` — the npm gate this one is modelled on
- `CHANGELOG.md`, `[Unreleased]` — the account of each image, with what
  was measured
- CVE-2026-85091 (zlib) — the fix requested under rule 4
