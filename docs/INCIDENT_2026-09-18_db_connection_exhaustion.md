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
1. **Stop the orphan accumulation (the real fix).** Ensure every deploy removes superseded containers —
   `docker compose up -d --remove-orphans` in the deploy, and/or a scheduled `docker container prune -f`
   on the host. Investigate why Coolify leaves old `admin` containers specifically (likely a
   service-name/compose-project mismatch across versions so compose doesn't recognize them as replaceable).
2. **Give Postgres headroom + reduce hold time.** Raise `PG_MAX_CONNECTIONS` (50 → 100) with a matching
   `POSTGRES_MEM_LIMIT`, and/or lower `CONN_MAX_AGE` so idle persistent connections are released sooner.
   Sizing rule already documented in `backend/docker/entrypoint.sh`: `workers*4 + ~10` across **all**
   services (api + admin + worker + beat).
3. **Least-privilege DB role.** The app connects as the Postgres **superuser**, which let it consume the
   `superuser_reserved_connections` slots — leaving no emergency slot for diagnostics/recovery. Create a
   dedicated non-superuser application role so the reserved slots stay available.
4. **Make `/api/health/` survive this.** The health view is designed to report `503 {db:down}`, but it
   sits **behind** the tenant-resolution middleware (which itself queries the DB), so on DB failure it
   returns a bare 500 instead. A DB-independent liveness route (or running the health check ahead of tenant
   resolution) would let the healthcheck report the real cause.
5. **Don't retry a 500 on the session bootstrap.** The frontend retry wrapper turned each failing
   `/api/customer/session/` into ~6 calls per page load — pure amplification once the endpoint is known-down.
