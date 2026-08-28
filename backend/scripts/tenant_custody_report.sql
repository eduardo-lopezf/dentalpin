-- Tenant custody × clinic tier, for one deployment.
--
-- Read this first, because the query is shaped by a constraint rather
-- than by convenience.
--
-- There is no single-statement join between these three columns, and
-- that is deliberate (ADR 0024). They live in two different databases:
--
--   control plane (ours)      tenants.tenant_id, tenants.custody_mode
--   data plane (the tenant's) clinics.id, clinics.account_tier
--
-- ``custody_mode`` says who may read this database. Storing it *in* the
-- database it describes would let its own subject rewrite it — an
-- operator could set 'managed' to 'self' and the system would assert it
-- cannot read what it is reading. So it stays in the control plane, and
-- no foreign key can span the gap.
--
-- The relation is not a key either. Within a tenant database, every
-- clinic belongs to that tenant by construction: the database *is* the
-- tenant (ADR 0012). That is why the join below is a CROSS JOIN against
-- a one-row CTE and not an equijoin — there is nothing to match on, and
-- a ``tenant_id`` column on ``clinics`` would be redundant at best and,
-- at worst, an invitation to put isolation back into a WHERE clause
-- somebody can forget.
--
-- Usage — the deployment facts come from the resolved TenantContext
-- (app.core.tenancy), which now reads TENANT_CUSTODY_MODE /
-- TENANT_JURISDICTIONS / TENANT_DATA_RESIDENCY. Not from this
-- database:
--
--   docker-compose exec -T db psql -U dental -d dental_clinic \
--     -v tenant_id="'00000000-0000-0000-0000-000000000001'" \
--     -v tenant_slug="'default'" \
--     -v custody_mode="'managed'" \
--     -f backend/scripts/tenant_custody_report.sql
--
-- Requires migration 0009 (clinics.tenant_type -> clinics.account_tier).

\if :{?tenant_id}
\else
\set tenant_id '00000000-0000-0000-0000-000000000001'
\endif
\if :{?tenant_slug}
\else
\set tenant_slug 'default'
\endif
\if :{?custody_mode}
\else
\set custody_mode 'managed'
\endif

WITH tenant AS (
    -- Stands in for the control plane's ``tenants`` row. When the
    -- control plane exists these three values are SELECTed from there,
    -- never from this database.
    SELECT
        :'tenant_id'::uuid   AS tenant_id,
        :'tenant_slug'::text AS tenant_slug,
        :'custody_mode'::text AS custody_type
)
SELECT
    t.tenant_id,
    t.tenant_slug,
    t.custody_type,
    -- What the custody mode implies. Derived, never stored: the mode is
    -- the single source of truth (ADR 0023).
    CASE t.custody_type
        WHEN 'self'    THEN 'none'
        WHEN 'managed' THEN 'break_glass'
        WHEN 'byok'    THEN 'break_glass'
    END AS operator_access,
    CASE t.custody_type
        WHEN 'self'    THEN 'customer'
        WHEN 'managed' THEN 'operator'
        WHEN 'byok'    THEN 'customer'
    END AS key_custody,
    c.id   AS clinic_id,
    c.name AS clinic_name,
    -- Commercial tier of one clinic. Unrelated to custody despite the
    -- old name (``tenant_type`` until migration 0009) suggesting
    -- otherwise.
    c.account_tier
FROM tenant t
CROSS JOIN clinics c
ORDER BY c.name;
