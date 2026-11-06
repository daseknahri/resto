# Incident 2026-09-18 — production API down (Postgres connection exhaustion)

Root-cause + fix record for **F1** in [`QA_FINDINGS_2026-09-18.md`](QA_FINDINGS_2026-09-18.md). Diagnosed live
in Coolify (server `85.31.239.111`, project `rostoy` / app `daseknahri/resto`, production).

## Symptom
Every `/api/*` request returned a bare Django **500** on both the platform host and tenant hosts; the
static SPA shell still loaded. Coolify showed the app **Degraded**, the `api` container **unhealthy**.

## Root cause — orphaned containers exhausting the Postgres connection pool
- Postgres was **up** but logging continuously: `FATAL: sorry, too many clients already` — the pool
  (`max_connections=50`, from `docker-compose.coolify.yml`) was 100% saturated (even a superuser `psql`
  from inside the container was refused, because the app connects **as the Postgres superuser**, so it
  consumed the reserved slots too).
- `docker ps` on the host showed **8 orphaned `admin-*` containers "Up 4 months"** (each from a different,
  superseded deploy hash — not the current `n0sg80s0oc8w8kkk4osg4s88`), all **healthy** → i.e. still
  connected to the live Postgres and holding persistent connections (`CONN_MAX_AGE=600`). Every other
  service (api, worker, beat, postgres, redis, frontend) had exactly **one** current container.
- 8 stale admin apps × their persistent connections + the current stack > 50 → exhaustion.
- **Coolify is not removing old `admin` containers on redeploy** (an orphan-cleanup gap), so they
  accumulated over ~4 months. This is why a plain Restart/Stop of the *current* deployment did **not** fix
  it — those actions don't touch the orphans, which keep hogging the pool.

## Immediate fix (recovery)
Remove the orphaned containers to free their connections (the exact 8 were saved to `/tmp/orphans.txt` on
the host during diagnosis; the current admin + all other services are excluded):
```bash
xargs -r docker rm -f < /tmp/orphans.txt
# verify (expect 200):
curl -s -o /dev/null -w '%{http_code}\n' "https://menu.ibnbatoutaweb.com/api/customer/session/?lang=en"
```
This closes their DB connections → the pool clears → the current `api` reconnects → API returns 200. No
data impact (they're stateless app containers; Postgres and its volume are untouched).

> Note: this destructive host command must be run by an operator — the assistant's harness blocks
> `docker rm -f`/`docker stop` on running containers ("interfere with workloads").

## Durable fixes (this week — so it can't recur)
1. **Stop the orphan accumulation (the real fix).** 🔶 **Drafted — [`infra/COOLIFY_ORPHAN_CONTAINER_CLEANUP.md`](../infra/COOLIFY_ORPHAN_CONTAINER_CLEANUP.md).**
   Two layers: (a) make Coolify's `docker compose up` pass **`--remove-orphans`** (or pin the compose
   project name) so superseded containers are reaped on deploy — the root cause; and (b) a dry-run-by-default
   safety-net script, [`infra/coolify/prune_stale_stack_containers.sh`](../infra/coolify/prune_stale_stack_containers.sh),
   that removes stale duplicate *stateless* containers (never postgres/redis) and can run as a host cron.
   Note `docker container prune` alone would NOT have helped — the orphans were *running*, and prune only
   removes *stopped* containers. Needs the owner to set the Coolify option + schedule the script.
2. **Give Postgres headroom + reduce hold time.** Raise `PG_MAX_CONNECTIONS` (50 → 100) with a matching
   `POSTGRES_MEM_LIMIT`, and/or lower `CONN_MAX_AGE` so idle persistent connections are released sooner.
   Sizing rule already documented in `backend/docker/entrypoint.sh`: `workers*4 + ~10` across **all**
   services (api + admin + worker + beat). _(PR #379 — see its own note.)_
3. **Least-privilege DB role.** 🔶 **Drafted — [`infra/sql/least_privilege_app_role.sql`](../infra/sql/least_privilege_app_role.sql).**
   The app connects as the Postgres **superuser**, which let it consume the `superuser_reserved_connections`
   slots — leaving no emergency slot for diagnostics/recovery. The script creates a dedicated **non-superuser**
   role that OWNS the app database (so django-tenants can still `CREATE SCHEMA` + run per-tenant migrations,
   incl. `CREATE INDEX CONCURRENTLY`, at runtime — verified no `CREATE EXTENSION`/superuser DDL is needed),
   with a greenfield path (recommended) and an in-place ownership-transfer path for the existing prod DB.
   Staging-gated + take a backup before the in-place path; then repoint `DATABASE_URL` and keep
   `POSTGRES_USER` as the idle bootstrap superuser. Needs the owner (prod DB access).
4. **Make `/api/health/` survive this.** ✅ **DONE (PR #378).** The health view is designed to report
   `503 {db:down}`, but it sat **behind** the tenant-resolution middleware (which itself queries the DB),
   so on DB failure it returned a bare 500 instead. Fixed: `TenantAwareMainMiddleware.process_request` now
   exempts `/api/health/` — it routes `force_public` and skips the `get_tenant` DB lookup, so the health
   view runs its own guarded `SELECT 1` and reports the real `503 {db: {ok: false}}` during an outage.
   Regression test: `backend/tests/test_health_middleware_outage_resilience.py`.
5. **Don't retry a 500 on the session bootstrap.** The frontend retry wrapper turned each failing
   `/api/customer/session/` into ~6 calls per page load — pure amplification once the endpoint is known-down.
