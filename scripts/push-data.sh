#!/bin/bash
# Push local table data to a remote database, incrementally.
# Rows that already exist remotely are skipped (INSERT ... ON CONFLICT DO NOTHING);
# nothing is ever updated or deleted on the remote.
#
# Usage:
#   ./scripts/push-data.sh --remote <URL> --preset catalog            # dry run
#   ./scripts/push-data.sh --remote <URL> --tables a,b,c --apply
#
# The remote URL may also come from REMOTE_DATABASE_URL. It is a libpq URL:
#   postgresql://user:pass@host:5432/dental_clinic
#
# Dry run is the default: the inserts are executed inside a transaction that is
# then rolled back, so you get the exact per-table row counts without writing.

set -euo pipefail

LOCAL_DB="${POSTGRES_DB:-dental_clinic}"
LOCAL_USER="${POSTGRES_USER:-dental}"
OUT_DIR="${OUT_DIR:-./dumps}"

REMOTE_URL="${REMOTE_DATABASE_URL:-}"
TABLES=""
PRESET=""
APPLY=false
NO_FK_CHECKS=false

# Presets are convenience lists; order does not matter, the script sorts by FK depth.
PRESET_catalog="vat_types specialties treatment_categories treatment_catalog_items catalog_item_sessions catalog_item_specialties treatment_odontogram_mappings"
PRESET_templates="plan_templates plan_template_items"

while [ $# -gt 0 ]; do
  case "$1" in
    --remote)   REMOTE_URL="$2"; shift 2 ;;
    --tables)   TABLES="$2"; shift 2 ;;
    --preset)   PRESET="$2"; shift 2 ;;
    --apply)    APPLY=true; shift ;;
    --no-fk-checks) NO_FK_CHECKS=true; shift ;;
    -h|--help)  sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

[ -n "$REMOTE_URL" ] || { echo "Missing --remote <URL> (or REMOTE_DATABASE_URL)." >&2; exit 1; }

# --- table list -------------------------------------------------------------

WANTED=""
if [ -n "$PRESET" ]; then
  eval "WANTED=\"\${PRESET_$PRESET:-}\""
  [ -n "$WANTED" ] || { echo "Unknown preset '$PRESET'. Available: catalog, templates." >&2; exit 1; }
fi
if [ -n "$TABLES" ]; then
  WANTED="$WANTED $(echo "$TABLES" | tr ',' ' ')"
fi
[ -n "$WANTED" ] || { echo "Nothing to push: pass --preset or --tables." >&2; exit 1; }

# --- helpers ----------------------------------------------------------------

lpsql() { docker compose exec -T db psql -X -q -v ON_ERROR_STOP=1 -U "$LOCAL_USER" -d "$LOCAL_DB" "$@"; }
rpsql() { docker compose exec -T db psql -X -q -v ON_ERROR_STOP=1 "$REMOTE_URL" "$@"; }

sql_array() { printf "ARRAY[%s]" "$(for t in $1; do printf "'%s'," "$t"; done | sed 's/,$//')"; }

fail() { echo "" >&2; echo "ABORTED: $*" >&2; exit 1; }

# --- preflight --------------------------------------------------------------

echo "==> Checking connections"
lpsql -tAc "select 1" >/dev/null || fail "cannot reach the local database."
REMOTE_VER=$(rpsql -tAc "show server_version" 2>/dev/null | tr -d '[:space:]') || fail "cannot reach the remote database."
echo "    local: $LOCAL_DB (in the db container)   remote: PostgreSQL $REMOTE_VER"

echo "==> Comparing Alembic heads"
LOCAL_HEADS=$(lpsql -tAc "select version_num from alembic_version order by 1" | tr -d '\r')
REMOTE_HEADS=$(rpsql -tAc "select version_num from alembic_version order by 1" | tr -d '\r')
if [ "$LOCAL_HEADS" != "$REMOTE_HEADS" ]; then
  echo "    Only local:" >&2;  comm -23 <(echo "$LOCAL_HEADS") <(echo "$REMOTE_HEADS") | sed 's/^/      /' >&2
  echo "    Only remote:" >&2; comm -13 <(echo "$LOCAL_HEADS") <(echo "$REMOTE_HEADS") | sed 's/^/      /' >&2
  fail "the two schemas are at different migrations. Deploy/migrate first — never paper over this with data."
fi
echo "    identical ($(echo "$LOCAL_HEADS" | wc -l | tr -d ' ') heads)"

echo "==> Checking tenants"
LOCAL_CLINICS=$(lpsql -tAc "select id from clinics order by 1")
MISSING_CLINICS=$(rpsql -tAc "
  select c.id from unnest($(sql_array "$(echo "$LOCAL_CLINICS" | tr '\n' ' ')")::uuid[]) as c(id)
  where not exists (select 1 from clinics where clinics.id = c.id)")
if [ -n "$MISSING_CLINICS" ]; then
  echo "    These local clinic_ids do not exist on the remote:" >&2
  echo "$MISSING_CLINICS" | sed 's/^/      /' >&2
  rpsql -c "select id, name from clinics" >&2
  fail "the rows you are pushing carry a clinic_id the remote does not have. They would violate the FK (or land in the wrong tenant)."
fi
echo "    every local clinic_id exists remotely"

echo "==> Resolving tables"
for t in $WANTED; do
  rpsql -tAc "select to_regclass('public.$t')" | grep -q . || fail "table '$t' does not exist on the remote."
done
# Sort by FK depth so parents are inserted before children.
ORDERED=$(lpsql -tAc "
  WITH RECURSIVE sel(t) AS (SELECT unnest($(sql_array "$WANTED")::text[])),
  edges AS (
    SELECT c.conrelid::regclass::text AS child, c.confrelid::regclass::text AS parent
    FROM pg_constraint c
    WHERE c.contype = 'f' AND c.conrelid <> c.confrelid
      AND c.conrelid::regclass::text IN (SELECT t FROM sel)
      AND c.confrelid::regclass::text IN (SELECT t FROM sel)
  ),
  depth(t, d) AS (
    SELECT t, 0 FROM sel
    UNION ALL
    SELECT e.child, d.d + 1 FROM depth d JOIN edges e ON e.parent = d.t WHERE d.d < 20
  )
  SELECT t FROM (SELECT t, max(d) AS d FROM depth GROUP BY t) x ORDER BY d, t")
echo "    order: $(echo "$ORDERED" | tr '\n' ' ')"

# --- build the SQL ----------------------------------------------------------

mkdir -p "$OUT_DIR"
[ -f "$OUT_DIR/.gitignore" ] || printf '*\n!.gitignore\n' > "$OUT_DIR/.gitignore"
STAMP=$(date +%Y%m%d-%H%M%S)
SQL="$OUT_DIR/push-$STAMP.sql"

echo "==> Dumping local rows"
{
  echo "BEGIN;"
  $NO_FK_CHECKS && echo "SET session_replication_role = replica;"
  echo "CREATE TEMP TABLE _push_counts(t text primary key, before_n bigint, after_n bigint);"
  for t in $ORDERED; do
    echo "INSERT INTO _push_counts(t, before_n) SELECT '$t', count(*) FROM public.$t;"
  done
} > "$SQL"

for t in $ORDERED; do
  # The INSERTs are schema-qualified, so pg_dump's search_path reset is only noise.
  docker compose exec -T db pg_dump -U "$LOCAL_USER" -d "$LOCAL_DB" \
    --data-only --column-inserts --on-conflict-do-nothing \
    --no-owner --no-privileges --table="public.$t" \
    | grep -v "^SELECT pg_catalog.set_config" >> "$SQL"
done

{
  for t in $ORDERED; do
    echo "UPDATE _push_counts SET after_n = c.n FROM (SELECT count(*) AS n FROM public.$t) c WHERE t = '$t';"
  done
  echo "SELECT t AS tabla, before_n AS antes, after_n AS despues, after_n - before_n AS insertadas FROM _push_counts ORDER BY t;"
  if $APPLY; then echo "COMMIT;"; else echo "ROLLBACK;"; fi
} >> "$SQL"

echo "    $SQL ($(grep -c '^INSERT INTO public' "$SQL") INSERT statements)"

# --- apply ------------------------------------------------------------------

if $APPLY; then
  MAJOR="${REMOTE_VER%%.*}"
  CLIENT_MAJOR=$(docker compose exec -T db pg_dump --version | sed 's/[^0-9]*\([0-9]*\).*/\1/')
  BACKUP="$OUT_DIR/remote-backup-$STAMP.dump"
  TABLE_ARGS=$(for t in $ORDERED; do printf -- "--table=public.%s " "$t"; done)
  echo "==> Backing up the remote target tables"
  if [ "$MAJOR" -le "$CLIENT_MAJOR" ]; then
    # Same network context as every other remote call in this script.
    docker compose exec -T db pg_dump -Fc $TABLE_ARGS -d "$REMOTE_URL" > "$BACKUP"
  else
    # pg_dump refuses a server newer than itself; borrow a matching client.
    echo "    remote is PostgreSQL $MAJOR, local client is $CLIENT_MAJOR — using postgres:$MAJOR-alpine"
    docker run --rm -i "postgres:$MAJOR-alpine" pg_dump -Fc $TABLE_ARGS -d "$REMOTE_URL" > "$BACKUP"
  fi
  echo "    $BACKUP ($(du -h "$BACKUP" | cut -f1))"
  echo "==> Applying to the remote (COMMIT)"
else
  echo "==> DRY RUN — the transaction is rolled back at the end (pass --apply to commit)"
fi

rpsql < "$SQL"

echo ""
$APPLY && echo "Done. Rollback: pg_restore --data-only --clean the backup above." \
       || echo "Nothing was written. Re-run with --apply once the numbers look right."
