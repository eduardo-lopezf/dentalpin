#!/bin/sh
set -e

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  # One-time heal for the Fase C schedules-branch rewire (issue #56):
  # DBs bootstrapped while schedules lived on the main linear chain have
  # the schedules tables but no row in alembic_version for the new
  # branch. Stamp sch_0001 so "alembic upgrade heads" is a no-op instead
  # of re-creating tables that already exist.
  #
  # Guard against re-stamping sch_0001 once the branch has moved past it
  # (e.g. sch_0002+): alembic_version only ever holds the current head per
  # branch, so after sch_0002 applies, sch_0001 correctly disappears from
  # the table. Blindly checking "sch_0001 absent" re-inserts it alongside
  # sch_0002, leaving an ancestor and its descendant stamped together —
  # an invalid state that makes "alembic upgrade heads" fail with
  # "Requested revision sch_0002 overlaps with other requested revisions
  # sch_0001" and crash-loops the container. Only heal when the branch has
  # no stamp at all.
  PG_URL="$(python -c 'from app.config import settings; print(settings.DATABASE_URL.replace("postgresql+asyncpg://","postgresql://"))')"
  psql "$PG_URL" -v ON_ERROR_STOP=1 <<'SQL' || true
DO $$
BEGIN
  IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'clinic_weekly_schedules'
     )
     AND NOT EXISTS (
        SELECT 1 FROM alembic_version WHERE version_num IN ('sch_0001', 'sch_0002')
     )
  THEN
    INSERT INTO alembic_version(version_num) VALUES ('sch_0001');
    RAISE NOTICE 'Stamped sch_0001 for pre-branch schedules tables';
  END IF;
END
$$;
SQL

  # What to migrate depends on whether this database has a module
  # registry yet (audit S1).
  #
  #   * No ``core_module`` table  → bootstrap. Nothing has ever been
  #     uninstalled here, so ``upgrade heads`` is safe and creates the
  #     whole schema in one pass.
  #   * Registry present → migrate the core linear chain only. Module
  #     branches are applied by the lifespan processor, which knows
  #     which modules are installed. ``upgrade heads`` here would walk
  #     every branch on disk and re-create the tables of a module the
  #     admin uninstalled — issue #56's "cosmetic uninstall" one layer
  #     up.
  HAS_REGISTRY="$(psql "$PG_URL" -tAc "SELECT to_regclass('public.core_module') IS NOT NULL" 2>/dev/null | tr -d '[:space:]')"

  if [ "$HAS_REGISTRY" = "t" ]; then
    CORE_HEAD="$(python -c 'from app.core.plugins.alembic_paths import resolve_core_head; print(resolve_core_head() or "")')"
    if [ -z "$CORE_HEAD" ]; then
      echo "[entrypoint] Could not resolve the core Alembic head; refusing to guess." >&2
      exit 1
    fi
    echo "[entrypoint] Running alembic upgrade $CORE_HEAD (core chain; module branches follow at startup)..."
    alembic upgrade "$CORE_HEAD"
  else
    echo "[entrypoint] No module registry yet — bootstrapping with alembic upgrade heads..."
    alembic upgrade heads
  fi
fi

if [ "${SEED_ON_STARTUP:-0}" = "1" ]; then
  (
    SEED_LANG_ARG="${SEED_LANG:-es}"
    for i in $(seq 1 60); do
      if python -c "import urllib.request,sys
try:
    sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=1).status == 200 else 1)
except Exception:
    sys.exit(1)" 2>/dev/null; then
        echo "[entrypoint] Backend healthy — running seed (lang=$SEED_LANG_ARG)"
        PYTHONPATH=/app python /app/scripts/seed_demo.py --lang "$SEED_LANG_ARG" || echo "[entrypoint] Seed failed (non-fatal)"
        exit 0
      fi
      sleep 1
    done
    echo "[entrypoint] Backend never became healthy — seed skipped"
  ) &
fi

exec "$@"
