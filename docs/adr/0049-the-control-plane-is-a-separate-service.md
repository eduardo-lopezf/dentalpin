# 0049 — The control plane is a separate service, and a tenant is a stack

- **Status:** accepted
- **Date:** 2026-10-05
- **Deciders:** Eduardo
- **Tags:** tenancy, operations, security, privacy, deployment

## Context

The platform needs an operator's panel: create tenants, watch what they
consume, read their logs. Three earlier decisions already fence where it
can live.

[ADR 0012](0012-multi-tenancy-brief.md) made a tenant a database and left
the SaaS side to a future `dienteazul-saas` module that swaps in its own
`TenantResolver`. [ADR 0024](0024-control-plane-holds-what-constrains-the-customer.md)
then ruled that whatever constrains the customer — tenant identity,
custody mode — is authoritative in a control plane and never in the
customer's own database, and it listed the cost in plain words: "there is
no control plane".

Meanwhile the data plane is still single-tenant by construction.
`backend/app/database.py` holds one global engine and `main.py` mounts
`SingleTenantResolver`; phase 2 of ADR 0012 (engine pool, per-tenant
`get_db`) is high-risk, large, and unstarted. So today "a tenant" is, in
fact, a deployment: one database, one backend, one frontend, configured
by `TENANT_*` variables and `backend/apps.json`
([ADR 0038](0038-apps-json-switches-apps-for-the-whole-deployment.md)).

Two shortcuts were on the table and both are wrong. A "superadmin" role
inside Diente Azul would store operator authority in the tenant's database,
which is the self-certification ADR 0024 rejects. And a panel that waits
for DB-per-tenant in a shared process waits for the riskiest refactor in
the backlog to deliver something that needs none of it.

## Decision

**The control plane is its own service, with its own database and its own
identities. It manages tenants as stacks on hosts, and it never sits
inside a tenant.**

Eight rules.

1. **Separate process, separate database, separate login.** The service
   shares no table, no `SECRET_KEY` and no user with any tenant. Its
   operators are *superadmins*, a concept that does not exist in
   Diente Azul's RBAC and must not be added to it. Neither side imports the
   other: `control` imports nothing from `backend/app`, and core never
   imports `control`.

2. **A tenant is a stack.** One database, one backend, one frontend, with
   their own volumes, generated from a template. Each stack keeps running
   `SingleTenantResolver`; isolation between tenants is that they are
   different containers on different databases. Phase 2 of ADR 0012 is
   not a prerequisite and stays deferred until the number of tenants
   makes a stack apiece expensive.

3. **A host is where stacks run, and local and remote are the same
   thing.** The control plane talks to the Docker API of each host: the
   local socket through a proxy that allowlists the operations it needs,
   a remote host over SSH with a key dedicated to that host. No agent is
   installed on a host. Where the control plane itself runs — a laptop
   today — is not part of the model.

4. **Two sources, two kinds of fact.** Infrastructure figures (state,
   CPU, memory, disk, logs) come from the host. Application figures
   (storage by kind, database size, active users, version, module state,
   recorded handler failures) come from an operations endpoint in core,
   called by the control plane with a token it signs. That endpoint
   returns **counts and sizes, never content**, and it does not exist in
   `CustodyMode.SELF`: a self-hosted deployment does not answer to
   anybody ([ADR 0028](0028-self-hosting-is-the-premium-tier.md)).

5. **What the operator can read holds no patient data.** Reading a
   tenant's logs is operator access under `managed`. Application logs
   shown in the panel carry identifiers (`request_id`, `clinic_id`,
   `user_id`), never names, contact details or clinical text. There is
   **no "sign in as the tenant"** until the break-glass mechanism of
   ADR 0024 exists and records the session in both planes.

6. **Provisioning never creates the clinic's credentials.** The control
   plane brings a stack up and hands over the link to `/auth/setup`; the
   first administrator is created by the clinic. The custody mode reaches
   the stack as `TENANT_CUSTODY_MODE`, written by the control plane and
   out of reach of the tenant's database, which is what ADR 0024 asks
   for.

7. **Secrets the control plane holds are encrypted at rest.** SSH keys,
   API tokens and database passwords of every tenant converge here. They
   are stored encrypted with a key that comes from the environment, and
   the service binds to loopback while it runs on a workstation.

8. **Suspending a tenant never blocks clinical reads or subject-rights
   endpoints.** The same line ADR 0028 draws for the licence key applies
   to the operator's switch.

## Consequences

### Good

- The panel is useful before any change to core: provisioning, resource
  figures and logs per tenant all fall out of "a tenant is a stack".
- Per-tenant CPU and memory are attributable, which they would not be in
  a shared process.
- ADR 0024's control plane gets a home, and its `tenants` table a first
  schema.
- Moving the panel from a laptop to a server changes where one container
  runs, nothing else.

### Bad / accepted trade-offs

- **Much of this does not exist yet.** What exists: the service, its
  database, superadmin login, and on the local host bringing a tenant's
  stack up, stopping it and starting it, with its secrets stored
  encrypted. The SSH driver, the operations endpoint, resource figures
  and logs, deletion, upgrades and `tenant_identity` (ADR 0024 rule 4)
  are pending.
- A stack per tenant costs a Postgres and two application containers per
  customer. That is the price of skipping phase 2, and it is paid in RAM.
- The Docker socket is root on the host. A proxy narrows it and a key per
  host contains a leak, but the control plane is the single most valuable
  thing to compromise, by design.
- A panel on a workstation does not watch anything while the lid is
  closed. Availability alerts stay with `monitoring/uptime-kuma.coolify.yml`.
- Log history across hosts needs a store of its own (Loki or similar).
  Until then the panel shows what the container still has.
- The code lives in `control/` at the repository root and is kept out of
  version control for now, so this ADR describes a folder a fresh clone
  does not have.

## Alternatives considered

- **A module or App inside Diente Azul** — it would run inside one tenant
  and be mounted, migrated and disabled like any module. A panel over
  every tenant cannot live in one of them.
- **A `superadmin` role in core RBAC** — operator authority stored in the
  database the customer owns; ADR 0024 rule 2.
- **DB-per-tenant in a shared process first (ADR 0012 phase 2)** — the
  long-term shape for density, and still open. Doing it first delays the
  panel behind a high-risk refactor and loses per-tenant resource
  attribution.
- **Coolify's API as the only driver** — ties the tenant model to one
  orchestrator and leaves local development without a path. It can be
  added as a second driver behind rule 3.
- **An agent on every host** — pushes metrics without inbound SSH, at the
  cost of something to install, version and secure on each server before
  there is a second server.

## How to verify the rule still holds

- `grep -rn "from app\.\(core\|modules\)" control/` returns nothing, and
  `grep -rn "control" backend/app --include=*.py -l` shows no import of
  the service. Rule 1.
- `grep -rn "superadmin" backend/app` returns nothing. Rule 1.
- `control/docker-compose.yml` publishes the API on `127.0.0.1` only and
  gives the socket proxy no published port. Rules 3 and 7.
- The socket proxy's environment enables only what the service uses; a
  capability switched on without a caller is a rule 3 violation.

## References

- [ADR 0012](0012-multi-tenancy-brief.md) — tenant vs clinic, the phases
- [ADR 0023](0023-privacy-policy-and-custody-modes.md) — custody modes
- [ADR 0024](0024-control-plane-holds-what-constrains-the-customer.md) — what the control plane holds
- [ADR 0028](0028-self-hosting-is-the-premium-tier.md) — no phone-home under `self`
- [ADR 0038](0038-apps-json-switches-apps-for-the-whole-deployment.md) — Apps per deployment
- `backend/app/core/tenancy/single.py` — the resolver every stack keeps
- `backend/app/core/tenancy/usage.py` — the storage figure the operations endpoint will reuse
- `control/README.md` — how to run the service
