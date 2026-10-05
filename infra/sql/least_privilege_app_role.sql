-- ============================================================================
-- least_privilege_app_role.sql — incident fix #3 (2026-09-18 outage)
-- ============================================================================
-- PROBLEM. The app connects to Postgres as the image SUPERUSER (DATABASE_URL's
-- user == POSTGRES_USER, see coolify.env.example). A superuser:
--   (a) can consume the `superuser_reserved_connections` slots — so when the pool
--       was exhausted on 2026-09-18 there was NO reserved slot left for an
--       emergency `psql` to diagnose/recover; and
--   (b) bypasses every permission check.
-- FIX. Run the app as a dedicated NON-superuser role, keeping the bootstrap
-- superuser (POSTGRES_USER) idle and free for emergencies. That alone protects
-- the reserved slots — the outage's diagnosability gap.
--
-- WHY THIS ISN'T A NARROW GRANT. django-tenants creates a NEW SCHEMA PER TENANT
-- AT RUNTIME: sales.services.provision_lead() -> tenant.create_schema() issues
-- `CREATE SCHEMA` then runs the full TENANT_APPS migration chain inside it,
-- including `CREATE INDEX CONCURRENTLY`. `migrate_schemas --shared` does the same
-- in `public`. So the app role must be able to create schemas and own/DDL objects
-- across `public` + every tenant schema. The correct least-privilege posture for
-- this single-database, dynamic-schema app is a non-superuser role that OWNS the
-- application database: it can do anything WITHIN its own DB, but nothing at the
-- cluster level (no other databases, no role/replication management, no reserved
-- slots). Verified: the current migration set needs NO `CREATE EXTENSION` and no
-- other superuser-only DDL (no pg_trgm/unaccent; only DML RunSQL + a plain
-- GinIndex on a normal column). If pg_trgm is ever added later, a superuser must
-- `CREATE EXTENSION pg_trgm;` once beforehand.
--
-- ─────────────────────────────────────────────────────────────────────────────
-- HOW TO RUN. As the SUPERUSER (POSTGRES_USER). Pass the new password out-of-band
-- (do NOT commit it). Pick Section A (fresh DB) OR Section B (existing DB) — not
-- both. TEST ON STAGING FIRST; Section B rewrites object ownership, so take a full
-- backup before running it in production.
--
--   psql "$SUPERUSER_DATABASE_URL" \
--     -v app_role=kepoli_app \
--     -v app_password="'REPLACE_WITH_LONG_RANDOM'" \   -- note the inner quotes
--     -v dbname=platform_db \
--     -v old_owner=platform_user \                      -- the current superuser app used
--     -f infra/sql/least_privilege_app_role.sql
-- ============================================================================

\set ON_ERROR_STOP on

-- ── 0. Create/refresh the role (idempotent, cluster-level) ───────────────────
--    NOSUPERUSER is the whole point. No CREATEDB (django-tenants makes SCHEMAS,
--    not databases). No CREATEROLE / NOREPLICATION / NOBYPASSRLS = minimal.
SELECT format(
  'role %I: %s',
  :'app_role',
  CASE WHEN EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_role')
       THEN 'exists — will ALTER' ELSE 'missing — will CREATE' END
) AS status \gset
\echo :status

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_role') THEN
    EXECUTE format(
      'ALTER ROLE %I WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
      :'app_role', :'app_password');
  ELSE
    EXECUTE format(
      'CREATE ROLE %I WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
      :'app_role', :'app_password');
  END IF;
END$$;

-- ═════════════════════════════════════════════════════════════════════════════
-- SECTION A — GREENFIELD / FRESH DATABASE (recommended; zero data-migration risk)
-- ═════════════════════════════════════════════════════════════════════════════
-- Run these two statements MANUALLY (CREATE DATABASE cannot run inside a txn/script
-- block cleanly, and you must connect to the new DB for the schema grant). Then
-- point DATABASE_URL at :app_role and let entrypoint.sh migrate_schemas run.
--
--   -- as superuser, connected to the 'postgres' maintenance DB:
--   CREATE DATABASE <dbname> OWNER <app_role>;
--   -- reconnect to <dbname>, then:
--   ALTER SCHEMA public OWNER TO <app_role>;
--   GRANT ALL ON SCHEMA public TO <app_role>;
--
-- Because :app_role OWNS the database and the public schema, it can CREATE SCHEMA
-- for every new tenant and own everything it creates — no further grants needed.

-- ═════════════════════════════════════════════════════════════════════════════
-- SECTION B — ADOPT AN EXISTING DATABASE (production; has data owned by superuser)
-- ═════════════════════════════════════════════════════════════════════════════
-- Uncomment this block to run it. Connect to the APPLICATION database (not the
-- 'postgres' maintenance DB) as the superuser. Requires :dbname and :old_owner.
-- REASSIGN OWNED affects ONLY the current database. TAKE A BACKUP FIRST and
-- rehearse on staging — this rewrites ownership of every existing object.
--
-- \echo 'Section B: transferring ownership of :dbname (public + all tenant schemas) to :app_role'
--
-- -- 1. The app role owns the database and the public schema (so it can CREATE
-- --    SCHEMA for new tenants and manage shared-schema objects).
-- ALTER DATABASE :dbname OWNER TO :app_role;
-- ALTER SCHEMA public OWNER TO :app_role;
--
-- -- 2. Hand every existing object (public + every tenant schema, in THIS database)
-- --    currently owned by the old app superuser over to the app role.
-- REASSIGN OWNED BY :old_owner TO :app_role;
--
-- -- 3. Make sure the role can connect and use public even if PUBLIC grants were
-- --    tightened on this cluster.
-- GRANT CONNECT ON DATABASE :dbname TO :app_role;
-- GRANT USAGE, CREATE ON SCHEMA public TO :app_role;
--
-- -- 4. (Optional) also transfer ownership of each existing tenant schema container
-- --    explicitly. REASSIGN OWNED above already covers schemas the old_owner owned;
-- --    this loop is a belt-and-suspenders for any schema owned by a different role.
-- DO $$
-- DECLARE s text;
-- BEGIN
--   FOR s IN
--     SELECT nspname FROM pg_namespace
--     WHERE nspname NOT IN ('pg_catalog','information_schema','pg_toast')
--       AND nspname NOT LIKE 'pg_temp%' AND nspname NOT LIKE 'pg_toast_temp%'
--   LOOP
--     EXECUTE format('ALTER SCHEMA %I OWNER TO %I', s, :'app_role');
--   END LOOP;
-- END$$;

-- ─────────────────────────────────────────────────────────────────────────────
-- AFTER EITHER SECTION
-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Update the app env (Coolify) — KEEP POSTGRES_USER as the bootstrap superuser
--    (the postgres container + `pg_isready` healthcheck still use it), and point the
--    app at the new role:
--        DATABASE_URL=postgresql://kepoli_app:<password>@postgres:5432/<dbname>
--    (Add an APP_DB_PASSWORD secret; leave POSTGRES_USER/POSTGRES_PASSWORD as-is.)
-- 2. Keep an emergency slot: confirm `superuser_reserved_connections` >= 3 so the
--    now-idle superuser always has a slot for recovery `psql`.
-- 3. Redeploy to STAGING and verify the role can do everything the app needs:
--        - api boots (entrypoint runs migrate_schemas --shared AND --tenant clean),
--        - PROVISION A TENANT end-to-end (a new lead -> new schema -> per-tenant
--          migrations incl. CREATE INDEX CONCURRENTLY) — this is the real test that
--          the non-superuser role has enough privilege,
--        - /api/health/ returns 200 with db ok.
-- Only after staging passes, apply to prod.

-- ── Verification (run as the NEW role to prove it can create schemas) ─────────
-- Connect as :app_role to :dbname and run:
--   CREATE SCHEMA _privcheck; DROP SCHEMA _privcheck;   -- must succeed
--   SELECT rolsuper FROM pg_roles WHERE rolname = current_user;  -- must be 'f'
