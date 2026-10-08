# 0051 — A backend process is one of several

- **Status:** accepted
- **Date:** 2026-10-07
- **Deciders:** Eduardo
- **Tags:** operations, deployment, scheduler, modules, security

## Context

[ADR 0049](0049-the-control-plane-is-a-separate-service.md) made a tenant
a stack: one database, one backend, one frontend. Nothing has ever run
two backends against one database, and the code was written by people —
and agents — who never had to picture it. The audit of 2026-07-03 had
noticed two of the places where that shows ("scheduler has no
multi-worker guard", "digest has no 'already sent today' guard") and
left them as findings.

Production still runs one of each, and this ADR does not change that. It
exists because the day one backend is not enough should be a change of
configuration, not a search for what breaks.

On 2026-10-07 a bench (`replicas/docker-compose.yml`) ran two backends
and two frontends behind a proxy for the first time. What it showed:

| What was tried | What happened |
|---|---|
| Two backends started together on an empty database | One died on `duplicate key … pg_type_typname_nsp_index`: both had created `alembic_version`. Docker's restart policy brought it back, which is also what hid it |
| The same, looking at the scheduler | Each registered and ran every periodic job |
| `dienteazul modules disable recalls` | Both backends went on answering `200` for the module until they were restarted |
| 14 logins with a wrong password, limit 5 a minute | 10 got through |
| Three backend processes at the default pool | Entitled to 90 of PostgreSQL's 100 connections |
| The frontend, two replicas, the whole browser suite | Nothing. 135 tests, requests split evenly, no error |

The third row is not about replicas. `module_gate` — the thing
[ADR 0018](0018-install-state-is-the-mount-authority.md) relies on to stop
a module answering between the command and the restart — was a set in the
memory of whichever process changed the state, and that process is the
CLI: `python -m app.cli`, beside the server, gone when the command
returns. The server was never told. It had not worked with one backend
either; two just made it visible.

One cause sits under all five: something that decides was kept in one
process's memory, or done by every process as if it were the only one.

## Decision

**A backend process behaves as one of several. What it holds alone may
make it faster, but is never the only place a decision lives; and work
that must happen once is claimed in PostgreSQL.**

Five rules.

1. **Startup work that writes is serialised.** Migrating, reconciling the
   module registry, carrying out pending installs and uninstalls, seeding:
   each runs under a session-level advisory lock
   (`app/core/advisory_locks.py`). `MIGRATION_LOCK` is taken in
   `alembic/env.py`, so it covers the entrypoint, the module processor and
   a person at a shell alike; `BOOT_LOCK` wraps reconciliation and the
   processor in the lifespan; `SEED_LOCK` wraps `scripts/seed_demo.py`.
   Where they nest it is boot, then migration, and never the reverse. The
   process that arrives second waits, finds the work done and does none.
   A lock belongs to its connection: a process that dies holding one
   releases it by dying. A new startup step that writes goes inside
   `BOOT_LOCK`.

2. **Periodic jobs run in one process.** `SCHEDULER_ENABLED` is on by
   default and a deployment with several backends leaves it on in exactly
   one — on the bench, a `scheduler` service of its own: the same image,
   behind no proxy. A job is declared through
   `BaseModule.get_scheduled_jobs()` and never added to the scheduler by
   hand: that is what makes it follow the switch.

3. **A module-level variable is a cache or a registry, never the record.**
   Handlers on the bus, tools in the registry, the active module set, the
   merged role permissions: all rebuilt at boot from the image and the
   database, identical in every process, and fine where they are. What
   one process decides and another must honour lives in the database, and
   the others read it. The module gate is the case in point: each backend
   reads `core_module` every `SYNC_SECONDS` (5) and closes the gate for
   what it still has mounted and the database says is off. `block()` stays
   as the immediate, local half for the process making the change.

4. **A limit that is per process is a setting, and its default describes
   one process.** `RATE_LIMIT_STORAGE_URI` gives the rate limiter a store
   the backends share; empty, it counts in memory as before. With a store
   configured it falls back to memory while the store is unreachable — the
   limiter stands in front of the login and must not take it down.
   `DB_POOL_SIZE` and `DB_MAX_OVERFLOW` default to the 10 and 20 they
   always were; their sum across every process has to fit under
   `max_connections`. The Redis client is the `redis` extra of
   `pyproject.toml`, which a default image does not install
   (`--build-arg PIP_EXTRAS=redis`).

5. **Every replica of the frontend runs the same image, and they are
   replaced together.** The Nuxt server keeps nothing between requests,
   but two builds are not interchangeable. Of the same code they differ
   in their build id — `_nuxt/builds/latest.json` and
   `_nuxt/builds/meta/<id>.json`, the other 349 files identical in name
   and content — so a page from one asks the other for a file it does not
   have and the app concludes a new version was deployed. Of different
   code they differ in the names of their chunks, and a page from one gets
   a 404 for its JavaScript from the other.

A deployment that sets none of this behaves as it did, with one exception
that is a correction: rule 3 makes the gate close for a single backend
too, which is what the documentation already said it did.

## Consequences

### Good

- Measured on the bench after each rule: three backends start together on
  an empty database with no crash and one seed; the jobs run in
  `scheduler` and in neither of the backends that serve; a module
  disabled from the CLI answers `409` on both; 5 logins get through a
  limit of 5; three processes configured to 15 connections each.
- The uninstall window of ADR 0018 is closed in the process that serves,
  which it never was.
- The bench stays. A change that is suspected of caring how many
  processes there are can be tried against two in a few minutes.
- Nothing was added to a deployment that runs one of each: no service, no
  dependency, no migration.

### Bad / accepted trade-offs

- **A second backend waits for the first.** Startup is one at a time, so
  each additional process is ready later by however long the one before
  it took — 15 to 20 seconds on the bench.
- **The locks have no timeout.** A process stuck in the middle of a
  migration keeps the others waiting, and says so in their logs. Giving
  up would mean doing the work unguarded.
- **Nothing checks that exactly one scheduler is on.** Two send every
  reminder twice; none runs no job, and nobody is told. And if that one
  process is down, the jobs wait for it to come back.
- **The gate is up to 5 seconds late**, and costs one small query every 5
  seconds while there is traffic. For that long after a module is turned
  off, a request can still reach it.
- **A restart is still one process.** `POST /api/v1/modules/-/restart`
  and `dienteazul modules restart` signal the process they reach. With
  several backends, whoever runs them restarts them all. Until then: after
  a disable or uninstall the processes disagree safely (the restarted one
  answers `404`, the other `409`); after an enable or install they
  disagree visibly (one serves the module, the other answers `404`); and
  the event handlers and jobs of an uninstalled module stay alive in the
  processes not yet restarted.
- **Session-level advisory locks do not survive a pooler in transaction
  mode.** The application connects to PostgreSQL directly; a PgBouncer in
  between means revisiting rule 1.
- **Not covered.**
  - The agents' per-session brake (`app/core/agents/guardrails.py`, 10
    actions a minute) still counts per process, as its own docstring
    says.
  - Files — uploads, import staging, module backups — live under
    `/app/storage`. Several backends on one machine share that volume;
    on several machines they need an object store, and `StorageBackend`
    has only its local implementation.
  - Work detached with `spawn()` and events queued for dispatch live in
    the process that started them and die with it. That was already so
    with one.
  - Verifactu registers its jobs from `install()` and not through
    `get_scheduled_jobs()`, so they do not follow rule 2 — nor, as far
    as the code reads, survive a restart. Tracked separately.
  - `pip-audit` in CI does not install the `redis` extra and so does not
    audit it.
  - Coolify and the tenant template of the control plane still describe
    one backend and one frontend.

## Alternatives considered

- **Let the processes compete for each job run in the database** — no
  special process and no way to end up with two schedulers or none, at the
  price of a table, a claim per run and every job reasoning about a run it
  lost. The switch is a few lines and is honest about what it does not
  check.
- **Hold the scheduler behind an advisory lock for the life of the
  process** — the first to boot runs the jobs. It takes a connection that
  must never drop: when it does the lock is gone and a second scheduler
  starts while the first still believes it holds it.
- **Ask the database about the gate on every request** — no window at
  all, and a query added to every call of the API for a state that
  changes a few times a year.
- **Tell the other processes with `LISTEN`/`NOTIFY`** — immediate, and
  needs a dedicated connection per process plus what to do when it
  drops. A process that misses the notification never closes its gate;
  one that polls is late by a known amount.
- **Make Redis a dependency of every image** — simpler to build, and a
  package and a service for the many deployments that will only ever run
  one backend.
- **Have the restart reach every process through a marker in the
  database** — the right shape for the trade-off listed above. It is a
  table and a migration, and was not part of this work.

## How to verify the rule still holds

- `backend/tests/test_advisory_locks.py` — one holder at a time, released
  however the block ends, boot and migration nest. Rule 1.
- `test_two_upgrades_at_once_both_succeed` in
  `backend/tests/test_alembic_roundtrip.py` (`-m alembic_roundtrip`) —
  fails with the bench's own error when the lock is taken out. Rule 1.
- `backend/tests/test_scheduler_jobs.py` — the switch defaults to on, and
  a process with it off creates no scheduler. Rule 2.
- `backend/tests/test_module_gate.py`, "Closed from another process".
  Rule 3.
- `backend/tests/test_rate_limit_storage.py` — the defaults, and that
  naming a store turns the fallback on. Rule 4.
- `replicas/docker-compose.yml` and
  [`docs/technical/running-replicas.md`](../technical/running-replicas.md)
  — every measurement in this ADR can be repeated there, and the browser
  suite run against two of each. Rules 1 to 5.
- **Nothing checks rule 3 for new code.** A decision put in a module-level
  variable tomorrow works with one backend and is found on the bench or
  not at all. `grep -rnE '^_[a-z_]+(: [^=]+)? = (\{\}|\[\]|set\(\))' backend/app`
  lists the candidates.

## References

- [ADR 0018](0018-install-state-is-the-mount-authority.md) — the gate and
  the uninstall window; `core_module.state` decides what runs
- [ADR 0035](0035-apps-are-disabled-not-uninstalled.md) — "between a
  `disable` and the restart `module_gate` answers `409`"
- [ADR 0049](0049-the-control-plane-is-a-separate-service.md) — a tenant
  is a stack, one of each
- [ADR 0019](0019-events-publish-after-commit.md) — events are dispatched
  in process and are not durable
- `docs/technical/audit-2026-07-03.md` — the scheduler and digest findings
- `backend/app/core/advisory_locks.py`, `backend/alembic/env.py`,
  `backend/app/main.py`, `backend/scripts/seed_demo.py`
- `backend/app/core/scheduler.py`, `backend/app/config.py`
- `backend/app/core/plugins/gate.py`, `backend/app/core/plugins/service.py`
- `backend/app/core/auth/router.py`, `backend/app/database.py`,
  `backend/pyproject.toml`, `backend/Dockerfile`
- `replicas/docker-compose.yml`, `replicas/nginx.conf`
- `CHANGELOG.md`, `[Unreleased]` — the account of each change, with what
  was measured
