# Operating a Diente Azul instance

Guide for admins and self-hosters: install and remove modules, trigger
restarts, take backups, recover from errors. Covers the commands an
operator runs — not the Python internals.

> **Audience**: ops-aware user with shell access to the host running
> `docker compose up`. For contributor-facing docs see
> `docs/technical/creating-modules.md`.

---

## 1. Prerequisites

- Docker + Docker Compose on the host.
- Cloned Diente Azul repo (or equivalent deploy artefacts).
- `.env` filled in with `POSTGRES_PASSWORD`, `SECRET_KEY`, etc.
- A running stack: `docker compose up -d`.

Smoke-check:

```bash
curl -s http://localhost:8000/health
# {"status":"healthy","version":"0.1.0"}
```

---

## 2. Daily operations

### Listing modules

```bash
./bin/dienteazul modules list
```

Output (trimmed):

```
NAME            VERSION  STATE       CATEGORY  DEPENDS
billing         0.1.0    installed   official  clinical,catalog,budget
budget          0.1.0    installed   official  clinical,catalog
clinical        0.1.0    installed   official  -
```

JSON variant: `./bin/dienteazul modules list --json`.

### Inspecting one module

```bash
./bin/dienteazul modules info billing
```

Shows version, state, applied revision, last state change, errors.
JSON form: same command with `--json`.

### Status summary

```bash
./bin/dienteazul modules status
```

Counts by state plus pending + errored lists.

### Health check

```bash
./bin/dienteazul modules doctor
```

Surfaces:

- **Orphans** — rows in `core_module` whose code disappeared from disk.
- **Missing dependencies** — module X depends on Y that wasn't found.
- **Manifest errors** — schema violations in `MANIFEST`.
- **Errored modules** — rows where the last install/upgrade step failed.

Exit code is non-zero when any issue is reported; ideal for
monitoring scripts.

---

## 3. Installing a module

### Official modules

Bundled with every Diente Azul release. They auto-install on the first
boot of a fresh database; the optional ones start `disabled` (see §5).
Reinstall if they ended up in `uninstalled`:

```bash
./bin/dienteazul modules install billing
./bin/dienteazul modules restart
```

### Community modules

```bash
# 1. Install the Python package on the backend container
docker compose exec backend pip install dienteazul-my-module

# 2. Schedule the install
./bin/dienteazul modules install my_module

# 3. Restart the backend — applies migrations + seed + lifecycle
docker compose restart backend
# or: POST /api/v1/modules/-/restart

# 4. Rebuild the frontend if the module ships a Nuxt layer
docker compose build frontend && docker compose up -d frontend
```

Output of step 2 lists the dependency chain that will be touched:

```
Scheduled for install on next restart:
  - clinical
  - my_module
```

---

## 4. Upgrading a module

Bump the module's package (`pip install -U ...`) so the new version
appears on disk, then:

```bash
./bin/dienteazul modules upgrade my_module
./bin/dienteazul modules restart
```

The restart runs the new migrations, re-applies seeds, and calls the
module's `post_upgrade(ctx, from_version)` hook.

If the disk and DB versions already match, the command exits with
"Module is already at the declared version."

---

## 5. Enabling and disabling a module

The everyday switch. Neither touches the module's tables or data
([ADR 0035](../../adr/0035-apps-are-disabled-not-uninstalled.md)).

```bash
./bin/dienteazul modules enable verifactu
./bin/dienteazul modules disable verifactu
./bin/dienteazul modules restart
```

- `enable` also enables every dependency that is off, and lists them.
- `disable` is refused while another enabled module lists this one in
  its `depends`. Disable those first; there is no `--force`.
- After the restart a disabled module has no routes, navigation,
  permissions, jobs or event handlers. Its schema is still migrated on
  every boot, so enabling it again is immediate.
- A disabled module does not hear events. Data it derives from them
  (the patient timeline, for instance) has a gap for the time it was
  off.

The **Apps** section of Settings has three pages. *Apps* shows the App
catalog — first the *Workspace*, the main App, always enabled; then the
core Apps and the rest (an App groups modules — Agenda is `agenda` + `schedules`) and,
below it, every module with its state. *Widgets* lists what each App
contributes to other screens, with a live example of each. *APIs* lists
the outside services an App can connect to (Agenda: Google Calendar, not
available yet). All three are read-only. A fourth, *Workspace*, is the
main App's own page and the one that changes something: its *Home*
section chooses which widgets the home page shows and in what order, for
the whole clinic (admins only).
These commands are the only way to change a module, and
an App listed as disabled changes nothing about its modules yet.

---

## 5a. Switching an App off for the whole deployment

`backend/apps.json` lists the Apps and whether each is `enabled` or
`disabled` ([ADR 0038](../../adr/0038-apps-json-switches-apps-for-the-whole-deployment.md)):

```json
{ "name": "agenda", "version": "0.1", "status": "disabled",
  "modules": ["agenda", "schedules"] }
```

Edit the status and restart the backend. A disabled App's modules are
not mounted: no routes, no menu entry, no permissions, no jobs. Their
data and their state in the module list are untouched, so setting the
status back and restarting restores everything.

Apps today: `agenda` (appointments and working hours), `treatments`
(treatment plans, odontogram, periodontogram), `patients` and
`professionals`. The agenda books an appointment without any of the
other three. With `treatments` off
the agenda still books appointments, without treatments, and says "No
se pueden asignar tratamientos".

Unlike `modules disable`, this does not ask about dependents: the other
apps keep running, and where they used to offer an appointment they say
"No se pueden crear citas".

---

## 5b. Uninstalling a module

Removes the module's tables. Use it only to get rid of a module for
good; to switch one off, disable it.

```bash
./bin/dienteazul modules uninstall my_module
docker compose restart backend
```

The restart:

1. **Backs up** every table the module owns to
   `storage/backups/module_<name>_<timestamp>.sql` via `pg_dump --data-only`.
2. Calls the module's `uninstall(ctx)` hook.
3. Deletes every record tracked via `core_external_id`.
4. Runs `alembic downgrade <module>@base` — reverts the module's
   branch only.
5. Flips `core_module.state = uninstalled`.

### Why some modules refuse to uninstall

Two guardrails:

- `removable: false` in the manifest (officials). Override with
  `--force` if you really mean it.
- No Alembic branch (Fase A legacy modules). These cannot downgrade
  cleanly; uninstall is blocked even with `--force`. Wait for Fase B.
- Reverse dependencies — another installed module lists this one in
  its `depends`. Uninstall them first, or pass `--force`.

---

## 6. Restarts

Three ways, identical effect (SIGTERM the backend, let Docker respawn):

| Channel | Command |
|---------|---------|
| CLI hint | `./bin/dienteazul modules restart` prints next step |
| REST | `POST /api/v1/modules/-/restart` (admin token) |
| Host | `docker compose restart backend` |

Respawn takes 3-5 seconds. Lifespan processes every `to_*` row in
topological order before accepting traffic. Errors per module are
recorded in `core_module.error_message`; the rest of the stack still
comes up.

---

## 7. Frontend rebuilds

Community modules with a Nuxt layer require a frontend rebuild:

```bash
docker compose build frontend && docker compose up -d frontend
```

30-60s downtime on the UI. Official modules **don't** need a rebuild
— they're already in the bundle; toggling visibility is a filter on
`/api/v1/modules/-/active`.

If the frontend starts but a module doesn't appear:

1. Inspect `frontend/modules.json` — it should list the module's layer
   path.
2. Run `./bin/dienteazul modules sync-frontend` to regenerate the file.
3. Confirm the user has the permission listed in `navigation[].permission`.

---

## 8. Backups

Module-scoped backups live under `storage/backups/` inside the
backend's `storage_data` volume:

```bash
docker compose exec backend ls -l /app/storage/backups
```

Each uninstall produces one `.sql` file with INSERTs for every table
the module owned. Restore with:

```bash
docker compose exec -T db psql -U dental -d dental_clinic \
  < storage/backups/module_my_module_20260420T080000Z.sql
```

The schema must already exist (reinstall the module first, then
restore data).

For full-database backups use your usual Postgres workflow (pg_dump,
point-in-time restore, etc.) — the module system does not replace it.

---

## 9. Recovery

### A failed install

`dienteazul modules doctor` lists the module with its error. Options:

1. Fix the root cause (usually a migration or seed bug), then
   `dienteazul modules install <name>` + restart to retry.
2. Give up: `dienteazul modules orphan <name>` (marks uninstalled
   without running the uninstall flow). Only do this when the module
   wasn't actually present on disk.

### A stuck `to_install`

Happens when a crash takes down the backend mid-step. Restart — the
lifespan processor retries from the first incomplete step. Idempotent
design means migrate/seed/lifecycle are safe to re-run.

```bash
docker compose exec backend \
  psql -U dental -d dental_clinic \
  -c "SELECT * FROM core_module_operation_log ORDER BY id DESC LIMIT 20;"
```

### An orphan row

Module code was removed from disk without an uninstall (e.g. someone
uninstalled the Python package directly). Bootstrap will fail loud:

```
Orphan modules (in DB, missing from disk):
  - ghost
```

Options:

- Restore the package (`pip install dienteazul-ghost`).
- Mark uninstalled:

  ```bash
  ./bin/dienteazul modules orphan ghost
  ```

The orphan path **does not** run the uninstall steps (migrations are
not downgraded, external ids are not purged, no backup is taken). Use
with care.

### Permission denied after role change

Clear the user's auth cookies and re-login. Permissions are loaded
from `/me` at login time; stale sessions keep the old list.

---

## 10. SQL quick reference

Run inside `docker compose exec db psql -U dental -d dental_clinic`:

```sql
-- All modules + state + error
SELECT name, state, version, installed_at, error_message
FROM core_module
ORDER BY name;

-- Pending operations
SELECT name, state, last_state_change
FROM core_module
WHERE state LIKE 'to_%';

-- Recent operation log
SELECT module_name, operation, step, status, created_at
FROM core_module_operation_log
ORDER BY id DESC
LIMIT 25;

-- Seed records tracked for a module
SELECT xml_id, table_name, record_id, noupdate
FROM core_external_id
WHERE module_name = 'inventory';

-- Clear the Alembic pointer (dangerous — used by reset-db.sh)
DELETE FROM alembic_version;
```

---

## 11. Troubleshooting table

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `relation "core_module" does not exist` | Tests dropped all tables | `docker compose exec backend alembic upgrade head` |
| Module stuck in `to_install` | Crash mid-step | Inspect `core_module_operation_log`, restart backend |
| `403 Permission denied: billing.read` | Role lacks the permission | Check `ROLE_PERMISSIONS`, confirm cached `/me` |
| Frontend sidebar empty | `/api/v1/modules/-/active` failed (bad token?) | Check browser console, re-login |
| Community module page 404 | `modules.json` missing the layer path | `./bin/dienteazul modules sync-frontend` + frontend rebuild |
| Uninstall blocked: "no Alembic branch" | Fase A legacy module | Not supported; wait for Fase B |
| Uninstall blocked: "required by ..." | Reverse dependency exists | Uninstall dependents first, or `--force` |

---

## 12. Where to file bugs

GitHub: https://github.com/dienteazul/dienteazul/issues — include the
output of:

```bash
./bin/dienteazul modules doctor --json
./bin/dienteazul modules info <affected-module> --json
docker compose logs backend --tail 100
```

For security reports contact the maintainers privately rather than
opening a public issue.
