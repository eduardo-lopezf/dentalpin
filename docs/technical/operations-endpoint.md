# The operations endpoint

What an operator's control plane reads from a deployment: how much each
clinic consumes, who signed in, where records were created. It is rule 4
of [ADR 0049](../adr/0049-the-control-plane-is-a-separate-service.md), and
rule 5 is its limit: **sizes, counts and identifiers, never content.**

It also holds the one thing the control plane writes: a new clinic with
its holder (rule 6).

Code: `backend/app/core/ops/` (`router.py`, `usage.py`). Tests:
`backend/tests/test_ops_endpoint.py`.

## Who may call it

Not the clinic's users — no staff session opens it. The caller presents a
JWT signed with `CONTROL_PLANE_SECRET` (HS256), with audience
`dienteazul-ops` and an expiry. The control plane signs one per request,
valid for a minute.

| Situation | Answer |
|---|---|
| `CONTROL_PLANE_SECRET` unset (the default) | `404` — the routes do not exist |
| `TENANT_CUSTODY_MODE=self` | `404`, whatever the secret holds: a self-hosted deployment answers to nobody ([ADR 0028](../adr/0028-self-hosting-is-the-premium-tier.md)) |
| No token, wrong secret, wrong audience, expired, or a staff token | `401` |

The routes sit in the `UNAUTHENTICATED` allowlist of
`tests/test_route_authorization_coverage.py` for the same reason the
WhatsApp webhook does: authorized, just not by a role.

## Routes

### `GET /api/v1/ops/usage`

`?refresh=true` measures again now; otherwise a measurement is kept ten
minutes per process (`USAGE_TTL`).

| Field | What it is |
|---|---|
| `database_bytes` | `pg_database_size` of the deployment's database. |
| `shared_database_bytes` | The part no clinic owns: tables without a `clinic_id`, rows with a null one, empty tables' overhead. |
| `storage_bytes`, `storage_files` | The tenant's storage folder, counted as `GET /auth/tenant/storage` counts it. |
| `clinics[]` | One entry per clinic: `id`, `name`, `created_at`, `apps` (chosen at creation; `null` = all), `status`, `deactivated_at`, `deletable_from`, `users`, `last_access_at`, `database_bytes`, `database_rows`, `storage_bytes`, `storage_files`. |

- **A clinic's database figure is a share, not a measurement.** Clinics
  share tables, so PostgreSQL has no per-clinic size. Each table with a
  `clinic_id` contributes its size on disk (`pg_total_relation_size`,
  indexes and TOAST included) split by how many of its rows are each
  clinic's. A clinic with few, very large rows is under-counted.
- **The tables are found in `information_schema`**, not by importing
  models: core may not import a module, and an uninstalled module has no
  table. It costs one `GROUP BY` per table, which is why it is cached.
- **A clinic's files are its folder**, `<clinic_id>/…`, where the media
  module stores uploads. What the storage holds outside every clinic's
  folder is in the total and in no clinic.
- **`status` is read now, not cached with the sizes.** In this order:
  `deactivated` (the operator closed it); `active` — one of its members
  has a session whose latest token is under an hour old, which is how
  long the app keeps an idle session (ADR 0030); `inactive` — no sign-in
  in fifteen days, or ever; `offline` otherwise. The windows are
  `SESSION_WINDOW` and `RECENT_WINDOW` in `usage.py`.
- **`last_access_at` is of the clinic's members.** A session belongs to a
  user, not a clinic: someone who works in two clinics counts in both.
- **`name` is the clinic's name** — the operator's customer. It is the
  one name this endpoint returns.

### `GET /api/v1/ops/clinics/{clinic_id}/log`

`?limit=` up to 500, default 100. Newest first.

| `kind` | From | Carries |
|---|---|---|
| `login` | The first row of a refresh-token family (`auth_sessions`) | `user_id`, `role` |
| `logout` | A family revoked with reason `logout` | `user_id`, `role` |
| `session_revoked` | A family revoked with reason `reuse` — a refresh token presented twice (ADR 0029) | `user_id`, `role` |
| `record_created` | The newest rows of every table with `clinic_id` and `created_at` | `area` (the table's name) |

- **No names, no e-mail addresses, no record content.** A user is an id
  and a role; a record is a timestamp and a table. The test asserts a
  patient's surname and the user's e-mail never appear in the response.
- **Activity does not say who.** Few tables record an author, so
  `record_created` has no `user_id`. It also sees creations only: an edit
  or a soft delete leaves no entry.
- **There is no access log beyond sessions.** `auth_sessions` holds no IP
  and no user agent, on purpose (see the model's docstring); a failed
  login leaves no row.

### `POST /api/v1/ops/clinics/{clinic_id}/deactivate` · `…/reactivate`

Deactivating sets `clinics.deactivated_at`; from then on
`get_clinic_context` refuses the clinic to its members (`403`), who keep
any other clinic they belong to. **Nothing is deleted**, and
reactivating clears the column and brings everything back. Both answer
with the clinic's state: `status`, `last_access_at`, `deactivated_at`,
`deletable_from`.

- **`deletable_from` is `deactivated_at` plus ten days** (`DELETION_WAIT`).
  Deactivating an already deactivated clinic keeps the first date: the
  wait is not restarted by a second click.
- **There is no route that deletes a clinic.** The date says from when
  one may be; what deleting means is not decided. A clinic holds clinical
  records the law makes it keep, invoices, and a record that is
  append-only by design (ADR 0032), and this codebase soft-deletes
  patient data on principle.

### `GET /api/v1/ops/specialties`

The disciplines a clinic's treatment catalogue can start with: `key`,
`names` and `required`. They come from the catalog module through the
`ReferenceSpecialties` contract (ADR 0039), so the list is empty when the
deployment does not run the Treatments App. `required` marks the one
every clinic has — general dentistry.

### `GET /api/v1/ops/apps`

The deployment's Apps, from `backend/apps.json`: what there is to choose
from when a clinic is created.

| Field | What it is |
|---|---|
| `name`, `tier` | As in `apps.json` (`base`, `core`, `optional`). |
| `enabled` | Whether the deployment runs it at all. An App switched off for the deployment cannot be chosen for a clinic. |
| `requires` | Other Apps that own a module it depends on, transitively. |
| `mandatory_for` | The account tiers whose clinics always have it: every tier for the base App and the core ones, and for an optional App the tiers in its `core_for_tiers`. |

`core_for_tiers` is how the catalog says an App is core for some kinds
of clinic only. Professionals carries it for `clinic`, `clinic_pro` and
`hospital`: a clinic has several professionals, one professional's
practice need not list any.

### `POST /api/v1/ops/clinics`

Creates a clinic and its holder, who becomes its administrator — what
`/auth/setup` does for the first clinic of a deployment, for every one
after it. `201` with `clinic_id`, `name` and `holder_user_id`.

| Field | Notes |
|---|---|
| `account_tier` | Any `AccountTier` the deployment's custody mode is sold under (`validate_tier_custody`); `422` otherwise. |
| `timezone` | An IANA id; `422` if it does not exist. |
| `tax_id` | RFC — the holder's under an individual tier, the clinic's otherwise. |
| `holder_first_name`, `holder_last_name`, `holder_email` | The holder's account. `409` if the e-mail already has one. |
| `holder_professional_id` | Cédula profesional; stored on `users.professional_id`. |
| `holder_password` | The holder's first password, given by the control plane. Checked against the password rule; only its hash is stored, and the account is created with `must_change_password`. |
| `specialties` | Optional. The disciplines the treatment catalogue starts with, by key: exactly those end up enabled. Must hold every `required` one; `422` for an unknown key. Left out, the clinic gets the ten baseline disciplines, as after `/auth/setup`. |
| `apps` | The Apps the clinic is set up with, by name. `422` if one is not an enabled App of the deployment, if an App that is mandatory for the tier is missing, or if a chosen App lacks one it requires. Stored in catalog order in `clinics.apps`. |
| `clinic_name`, `clinic_legal_name`, `clinic_phone`, `clinic_email` | The clinic's own details. `clinic_name` is required unless the tier is an individual one, where all four are ignored. |

- **Individual tiers are `basic`, `medium` and `advanced`** — one
  professional's practice. The clinic record takes the holder's name and
  the holder's RFC, because every record in the system still hangs from a
  clinic.
- **`clinic.created` is published after the commit**, so modules seed
  their baseline data (the catalog its VAT types, categories and
  specialties) exactly as after `/auth/setup`.
- **The chosen Apps are recorded, not enforced.** What runs is decided
  for the whole deployment (ADR 0038), so a clinic sees every enabled App
  whatever `clinics.apps` holds. `NULL` there — every clinic that existed
  before, and the one `/auth/setup` makes — means nobody chose, and reads
  as all of them. Switching Apps per clinic is commitment 20 of
  [`commitments-register.md`](commitments-register.md); this column is
  where its choice already waits.
- **The holder has to replace the password at the first sign-in.** While
  `users.must_change_password` is set, `get_clinic_context` answers `403`
  to everything; the account can read `/auth/me` and call
  `POST /api/v1/auth/password` (current and new password; the new one
  must differ), which clears the flag. The app sends such an account to
  `/change-password` and nowhere else.
- **`specialties` travels on `clinic.created`.** The catalog seeds the
  clinic as usual and then disables the baseline disciplines that were
  not chosen and enables the chosen ones beyond the baseline — its own
  pack operations, so plan templates follow.

## Reading it from the control panel

In development the panel calls it for the stack of this repository. Set
the same value as `CONTROL_PLANE_SECRET` in the root `.env` and as
`CONTROL_DEV_PLANE_SECRET` in `control/.env`, then recreate both
containers. See `control/README.md`.
