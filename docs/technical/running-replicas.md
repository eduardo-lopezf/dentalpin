# Running more than one backend or frontend

How to run several processes of the same service against one database,
and how to check that a change still works when there are two. The rules
and why they are these live in
[ADR 0051](../adr/0051-a-backend-process-is-one-of-several.md); this is
the working reference.

`status: accepted` for the code and the bench. No deployment runs replicas
yet: Coolify and the tenant template of the control plane still describe
one backend and one frontend.

## What a deployment with several backends sets

Nothing here is needed with one backend. Every default describes one.

| Setting | With one backend | With several |
|---|---|---|
| `SCHEDULER_ENABLED` | `true` (default) | `true` in exactly one process, `false` in the rest. Nothing checks it: two send every reminder twice, none runs no job |
| `RATE_LIMIT_STORAGE_URI` | empty (default): counters in memory | `redis://<host>:6379/0`, so the limit is one and not one per backend |
| image build | default | `--build-arg PIP_EXTRAS=redis`, the client the line above needs |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` | `10`, `20` (defaults) | Chosen so that processes × (pool + overflow) stays under PostgreSQL's `max_connections`, with room for migrations and `psql` |
| storage volume | one | The same volume mounted in every backend. On several machines: not supported yet, there is no object-store backend |

A process counts if it is a backend at all: the `scheduler` holds a pool
like the ones that serve.

The frontend takes no setting. Its replicas run **the same image** and
are replaced together — two builds are not interchangeable, even of the
same code.

### What needs no setting

- **Starting together.** Migrations, the module registry and the demo
  seed are serialised by advisory locks (`app/core/advisory_locks.py`).
  The second process logs `Waiting for core:boot` and carries on when the
  first is done.
- **Turning a module off.** Every backend closes its gate within
  `SYNC_SECONDS` (5) of the command, wherever the command ran.

### What still takes a person

**Restarting.** `dienteazul modules restart` and the restart button
signal one process. After any `enable`, `disable`, `install`, `upgrade`
or `uninstall`, restart every backend, the scheduler included:

```bash
docker compose -f replicas/docker-compose.yml restart backend scheduler
```

Until they have all restarted, the ones that have and the ones that have
not answer differently for that module.

## The bench

`replicas/docker-compose.yml` is that deployment in small, for
development: two backends, two frontends, one scheduler, Redis, and an
nginx that spreads requests over them. It is a Compose project of its own
(`dienteazul-replicas`) with its own database and volumes, and can be up
next to the development stack.

```bash
docker compose -f replicas/docker-compose.yml up -d --build
```

| | |
|---|---|
| The app | `http://localhost:8080` |
| The API | `http://localhost:8081` |
| Login | `admin@demo.clinic` / `demo1234` |
| Who answered | the `X-Replica` response header |

```bash
docker compose -f replicas/docker-compose.yml down       # keeps the data
docker compose -f replicas/docker-compose.yml down -v    # and without it
```

It runs the images a deployment runs, with `ENVIRONMENT=production`, so
the rate limiter is on and the secrets check applies. The secrets in the
file are public on purpose and sign tokens for a throwaway database on
loopback.

**Run it from its folder's file, never from a copy at the root.** The
repository's `.env` sets `COMPOSE_PROJECT_NAME=dienteazul`, which wins
over the `name:` inside a Compose file. Read from the root, the bench
would be the development project — same service names, same `pgdata`
volume. Check with
`docker compose -f replicas/docker-compose.yml config | grep '^name:'`.

### Things to try on it

```bash
# Which replica answers
for i in 1 2 3 4; do curl -s -o /dev/null -D - http://localhost:8081/health | grep -i x-replica; done

# One more backend, picked up by the proxy within seconds
docker compose -f replicas/docker-compose.yml up -d --scale backend=3 --no-recreate

# A module turned off from the CLI: 409 from every backend
docker compose -f replicas/docker-compose.yml exec backend python -m app.cli modules disable recalls

# Where the jobs run: only `scheduler` logs "Running job"
docker compose -f replicas/docker-compose.yml logs scheduler | grep 'Running job'
```

While every replica of a service restarts at once the proxy answers
`502`: there is nobody to send the request to.

## The browser suite against the bench

The suite logs in far more than five times a minute, so the bench has to
start without the limiter. The modules `ci.yml` enables for the suite
(`periodontogram`, `consents`, `record`) are enabled the same way, and
then every backend restarted.

```bash
export BENCH_ENVIRONMENT=test    # for every compose command of this run
docker compose -f replicas/docker-compose.yml up -d

for m in periodontogram consents record; do
  docker compose -f replicas/docker-compose.yml exec backend python -m app.cli modules enable $m
done
docker compose -f replicas/docker-compose.yml restart backend scheduler

cd frontend
E2E_BASE_URL=http://localhost:8080 \
E2E_API_BASE=http://localhost:8081 \
API_BASE_URL=http://localhost:8081 \
  npx playwright test $(ls tests/e2e/*.spec.ts | grep -v session-idle)
```

- **Keep `BENCH_ENVIRONMENT` exported.** An `up` without it recreates the
  backends in `production`, limiter and all.
- **Both API variables, always.** Left unset, some specs fall back to
  `localhost:8000` and log in to the development stack.
- **`session-idle.spec.ts` is left out.** It hard-codes
  `http://localhost:3000` and would drive the development frontend.
- **Start from an empty database** (`down -v` first). Specs create data
  and are written for a fresh seed.
- With `BENCH_ENVIRONMENT=test` every backend logs
  `Frontend layer sync failed (non-fatal)` as it starts: outside
  `production` it tries to write `modules.json` for a Nuxt dev server,
  into a folder the production image does not have.

Last full run, 2026-10-07: 135 passed against two frontends and two
backends.

## Known limits

Listed in full under "Bad / accepted trade-offs" in
[ADR 0051](../adr/0051-a-backend-process-is-one-of-several.md). The ones
that bite first:

- One process's restart is not everyone's (above).
- Exactly one scheduler, by configuration and not by check.
- The agents' per-session brake counts per process.
- Verifactu's jobs are not declared through `get_scheduled_jobs()` and do
  not follow `SCHEDULER_ENABLED`.
