# Incident Response Runbook — Kepoli / Resto (R23)

**Scope:** Production deployment of the django-tenants Kepoli/Resto app hosted on a
VPS via Coolify (`docker-compose.coolify.yml`). Services: `api`, `frontend`, `admin`,
`worker`, `beat`, `postgres`, `redis`.

**Last updated:** 2026-06-16

---

## Severity levels

| Level | Definition | Target response |
|-------|-----------|----------------|
| **SEV1 — Outage** | App entirely down (503/502 on all tenants, health returns `"down"`, DB unreachable) | Immediate — wake on-call |
| **SEV2 — Degraded** | Partial service (payments failing, WebSockets dead, Celery/Redis down, one tenant 500s) | Within 15 min |
| **SEV3 — Minor** | Non-critical feature broken, elevated latency, stale backup alert, single endpoint 4xx | Best-effort same shift |

---

## Owner TODOs (fill before going live)

<!-- TODO(owner): replace every placeholder below before first production incident -->

| Item | Placeholder |
|------|------------|
| On-call contact | `<!-- TODO(owner): name + phone/Signal -->` |
| Escalation chain (L2/L3) | `<!-- TODO(owner): L2 = ..., L3 = ... -->` |
| Coolify dashboard URL | `<!-- TODO(owner): https://coolify.your-vps.com -->` |
| Sentry project URL | `<!-- TODO(owner): https://sentry.io/organizations/ORG/projects/PROJECT/ -->` |
| Alert webhook (Slack/Discord) | `<!-- TODO(owner): same URL in /etc/default/kepoli-backup (set during install_backup_cron.sh) -->` |
| VPS host / SSH access | `<!-- TODO(owner): ssh user@VPS_IP  — key in ... -->` |
| Postgres resource UUID | `<!-- TODO(owner): from Coolify dashboard URL for the stack resource -->` |

---

## First 5 minutes — triage checklist

Run these in order regardless of the reported symptom:

```bash
# 1. Hit the health endpoint (SSL-redirect-exempt; always HTTP-accessible from inside VPS)
curl -s https://menu.ibnbatoutaweb.com/api/health/ | python3 -m json.tool

# 2. Check all container states
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Health}}'

# 3. Tail api container logs (most issues surface here)
docker logs --tail 100 -f $(docker ps -qf name=api)

# 4. Check Sentry for a spike in the last 10 min
# --> Open: <!-- TODO(owner): Sentry project URL -->

# 5. Check uptime probe manually
bash /opt/resto/infra/coolify/uptime_probe.sh \
  --check "https://menu.ibnbatoutaweb.com/api/health/|200"
```

**Health response quick read:**

| `status` | `checks.db.ok` | Meaning |
|----------|---------------|---------|
| `"ok"` | true | All green |
| `"degraded"` | true | Cache / Celery / channel-layer / media issue (SEV2) |
| `"down"` | false | DB unreachable — SEV1, act immediately |

---

## Playbook 1 — Bad deploy / app down / 500s

### Symptoms
- Coolify health check turns red; `frontend`/`admin` containers stuck in "starting"
  (they `depends_on: api: condition: service_healthy`)
- `/api/health/` returns 503 or connection refused
- Container logs show entrypoint dying before the uvicorn line

### Why the entrypoint is fail-closed

`backend/docker/entrypoint.sh` runs with `set -eu`. Any step that exits non-zero
halts the whole entrypoint — Coolify sees the container exit and keeps the **previous
healthy container** rather than replacing it with a broken one. Steps that can
abort:

1. `migrate_schemas --shared` / `--tenant`
2. `check_schema_health` (unless `SKIP_SCHEMA_HEALTHCHECK=1`)
3. `check --deploy --fail-level ERROR` (unless `SKIP_DEPLOY_CHECK=1`)
4. Media writability probe (unless `SKIP_MEDIA_WRITABLE_CHECK=1` or S3 backend)

### Diagnose

```bash
# Find the api container (may be the new failing one or the old healthy one)
docker ps -a --format 'table {{.Names}}\t{{.Status}}' | grep api

# Read full entrypoint output to find which step failed
docker logs <api-container-name> 2>&1 | tail -200
```

Look for lines like:
- `[entrypoint] migrate_schemas` followed by a Python traceback → **migration failure** (see Playbook 5)
- `[entrypoint] check_schema_health` → schema drift (see Playbook 5)
- `ERROR: /app/media is not writable` → volume permission issue
- `check --deploy` errors about `REDIS_URL` → missing env var

### Fix — primary: rollback via Coolify

**Deploy IS manual in this project.** Rollback means re-deploying a previous commit:

1. Open Coolify dashboard: `<!-- TODO(owner): Coolify dashboard URL -->`
2. Navigate to the resource (the Docker Compose stack).
3. Click **Deployments** tab → find the last green deployment.
4. Click **Redeploy** on that deployment to rebuild from its commit SHA.

> The entrypoint's fail-closed design means a partially-failed new deploy already
> left the old container running — a rollback simply makes that official and cleans up.

### Fix — USE_ASGI=0 fallback (WebSocket regression only)

If the app is up but WebSockets are broken after a uvicorn upgrade:

1. In Coolify env vars, set `USE_ASGI=0`.
2. Redeploy. The entrypoint falls back to `gunicorn config.wsgi:application`.
3. Revert the upstream code change; re-enable `USE_ASGI=1` on next deploy.

### Fix — emergency SKIP_* bypass

Only use these if you need the container to start despite a failing check and you
have confirmed the check is a false positive:

| Env var | Skips |
|---------|-------|
| `SKIP_SCHEMA_HEALTHCHECK=1` | `check_schema_health` after migrate |
| `SKIP_DEPLOY_CHECK=1` | `check --deploy` (e.g. single-process dev-mode emergency) |
| `SKIP_MEDIA_WRITABLE_CHECK=1` | media volume writability probe |

Set the var in Coolify env, redeploy, **remove the var again immediately after.**

### Verify

```bash
curl -s https://menu.ibnbatoutaweb.com/api/health/ | python3 -m json.tool
# status: "ok", checks.db.ok: true

curl -I https://menu.ibnbatoutaweb.com/
# HTTP/2 200
```

### Post-incident
- Document which commit caused the failure and why the entrypoint halted.
- Add a regression note to `backend/MIGRATIONS.md` if a migration was involved.
- Open a Sentry issue search to confirm no 500s leaked to users during the window.

---

## Playbook 2 — Database incident (corruption / data loss / accidental deletion)

### Symptoms
- `checks.db.ok: false` in health response (SEV1)
- Django logs: `OperationalError`, `relation does not exist`, `could not connect to server`
- Accidental `DROP TABLE` or bulk `DELETE` confirmed in logs

### Diagnose

```bash
# Check postgres container health
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Health}}' | grep postgres

# Attempt a direct psql connection
docker exec <postgres-container> psql -U ibnbatoutaweb_user -d ibnbatoutaweb_platform \
  -c "SELECT count(*) FROM public.django_migrations;"

# Run schema health check (exit 0 = structurally OK, non-zero = drift)
docker exec <api-container> python manage.py check_schema_health
```

### Fix — restore from backup

**Do NOT restore directly into the live database first.** Restore into a throwaway DB,
verify, then promote. Full procedure: **[infra/COOLIFY_DB_BACKUP_RUNBOOK.md §8](COOLIFY_DB_BACKUP_RUNBOOK.md)**

Quick reference:

```bash
# 1. Find the latest backup
ls -lt /var/backups/ibnbatoutaweb/*.dump | head -5

# 2. Restore into THROWAWAY database (never live DB first)
bash /opt/resto/infra/coolify/restore_postgres.sh \
  --resource-uuid <RESOURCE_UUID> \
  --backup-file /var/backups/ibnbatoutaweb/ibnbatoutaweb_platform_<TS>.dump \
  --db-name ibnbatoutaweb_restore_drill \
  --db-user ibnbatoutaweb_user \
  --admin-user ibnbatoutaweb_user

# 3. Run schema health check against restored DB
docker exec \
  -e DATABASE_URL="postgres://ibnbatoutaweb_user:<PASSWORD>@localhost/ibnbatoutaweb_restore_drill" \
  <api-container> python manage.py check_schema_health

# 4. If health check passes, promote: restore into live DB (stop traffic first)
# Bring down api/worker/beat:
docker stop <api-container> <worker-container> <beat-container>

bash /opt/resto/infra/coolify/restore_postgres.sh \
  --resource-uuid <RESOURCE_UUID> \
  --backup-file /var/backups/ibnbatoutaweb/ibnbatoutaweb_platform_<TS>.dump \
  --db-name ibnbatoutaweb_platform \
  --db-user ibnbatoutaweb_user \
  --admin-user ibnbatoutaweb_user

# 5. Redeploy (Coolify → Redeploy) to let entrypoint re-run migrations + seed_plans
# 6. Drop throwaway DB
docker exec <postgres-container> psql -U ibnbatoutaweb_user -d postgres \
  -c 'DROP DATABASE IF EXISTS ibnbatoutaweb_restore_drill;'
```

> For the complete restore drill checklist including checksum verification and
> off-VPS copy confirmation, see **[infra/COOLIFY_DB_BACKUP_RUNBOOK.md §8](COOLIFY_DB_BACKUP_RUNBOOK.md)**.

### Verify

```bash
curl -s https://menu.ibnbatoutaweb.com/api/health/ | python3 -m json.tool
# checks.db.ok: true

docker exec <api-container> python manage.py check_schema_health
# expect: exit 0
```

### Post-incident
- Record dump file used, timestamp, who performed the restore, and `check_schema_health` result in the restore drill log (COOLIFY_DB_BACKUP_RUNBOOK.md §8 table).
- Identify how data was lost. Add write-guard if an API endpoint caused an accidental bulk delete.
- Check Sentry `logger:payments` for any payment events that occurred after the last backup and are now lost — customers may need manual wallet adjustments.

---

## Playbook 3 — Redis down

### Symptoms
- `/api/health/` returns `"degraded"`, `checks.cache.ok: false`, `checks.channel_layer.ok: false`
- Celery probe: `beat_down` or `error: ConnectionError`
- Live order/payment status broadcasts to customers stop working (WebSocket events use channel layer)
- Login throttle and OTP rate-limiting fall back to per-process in-memory state (no cross-worker protection)
- `check --deploy` at next boot would ERROR on missing `REDIS_URL` in prod (halting startup)

### Diagnose

```bash
# Check redis container state
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Health}}' | grep redis

# Manual ping
docker exec <redis-container> redis-cli ping
# expected: PONG

# Check logs
docker logs --tail 50 <redis-container>

# Confirm REDIS_URL is set in api env
docker exec <api-container> printenv REDIS_URL
```

### Fix

**Container restart (most common):**

```bash
docker restart <redis-container>
# Wait for health to go green, then verify api cache
curl -s https://menu.ibnbatoutaweb.com/api/health/ | python3 -m json.tool
```

**If Redis data volume is corrupt:** restart with `--no-appendonly` to skip the AOF,
or remove `redis_data` volume and restart (all cache keys and Celery queue lost —
in-flight tasks will need to be re-queued, beat will recreate heartbeat within 60s).

**Emergency single-process bypass** (no Redis, no cross-worker cache):
Set `SKIP_DEPLOY_CHECK=1` in Coolify env → Redeploy. The api starts with LocMemCache.
WebSocket broadcasts and shared idempotency mutexes are broken — inform tenants. Remove `SKIP_DEPLOY_CHECK=1` once Redis is restored.

### Verify

```bash
docker exec <redis-container> redis-cli ping    # PONG
curl -s https://menu.ibnbatoutaweb.com/api/health/ | python3 -m json.tool
# checks.cache.ok: true, checks.channel_layer.ok: true
```

### Post-incident
- Determine root cause (OOM on VPS? volume full? host restart killed container?).
- Review whether any Celery tasks were lost (check `worker` logs for unacked tasks).
- If this was an OOM: see Playbook 7 (performance / high load) and Playbook 8 (disk full).

---

## Playbook 4 — Backup failures / stale backup alert

### Symptoms
- Webhook alert fires from `backup_freshness_probe.sh` (newest dump older than 26 h)
- `crontab -l | grep kepoli` shows no backup marker line (cron was wiped)
- `/var/log/kepoli-backup.log` shows errors

### Diagnose

```bash
# Check backup cron markers
crontab -l | grep kepoli

# Inspect backup log
tail -n 100 /var/log/kepoli-backup.log

# Check newest dump age
ls -lt /var/backups/ibnbatoutaweb/*.dump | head -3

# Manual freshness probe (exit 1 = stale/missing)
bash /opt/resto/infra/coolify/backup_freshness_probe.sh \
  --output-dir /var/backups/ibnbatoutaweb \
  --db-name ibnbatoutaweb_platform
```

### Fix — run a manual backup immediately

```bash
bash /opt/resto/infra/coolify/backup_postgres.sh \
  --resource-uuid <RESOURCE_UUID> \
  --db-name ibnbatoutaweb_platform \
  --db-user ibnbatoutaweb_user \
  --output-dir /var/backups/ibnbatoutaweb \
  --retention-days 14
```

**If cron was wiped, reinstall:**

```bash
cd /opt/resto
bash infra/coolify/install_backup_cron.sh \
  --resource-uuid <RESOURCE_UUID> \
  --db-name ibnbatoutaweb_platform \
  --db-user ibnbatoutaweb_user \
  --output-dir /var/backups/ibnbatoutaweb \
  --retention-days 14 \
  --webhook-url "<!-- TODO(owner): webhook URL -->" \
  --alert-format slack
```

Full backup setup: **[infra/COOLIFY_DB_BACKUP_RUNBOOK.md §6](COOLIFY_DB_BACKUP_RUNBOOK.md)**

### Verify

```bash
ls -lt /var/backups/ibnbatoutaweb/*.dump | head -3   # new dump present
crontab -l | grep kepoli                              # two marker lines present

bash /opt/resto/infra/coolify/backup_freshness_probe.sh \
  --output-dir /var/backups/ibnbatoutaweb \
  --db-name ibnbatoutaweb_platform
# exit 0 = fresh
```

### Post-incident
- Confirm the off-VPS copy is also present (3-2-1 rule).
- Run the restore drill if no drill has been done in the past quarter: [COOLIFY_DB_BACKUP_RUNBOOK.md §8](COOLIFY_DB_BACKUP_RUNBOOK.md).

---

## Playbook 5 — Migration failure on deploy

### Symptoms
- New deploy fails — api container exits during entrypoint; old container stays up (this is correct and intentional)
- Container logs show `python manage.py migrate_schemas` traceback
- Or: migrate exits 0 but `check_schema_health` exits non-zero (recorded-but-not-applied migration)

### How it works (fail-closed)

`backend/docker/entrypoint.sh` runs with `set -eu`. A failed `migrate_schemas` exits
non-zero → entrypoint halts → Coolify keeps the old container. The new broken image is
never promoted. This is the intended safety behaviour.

### Diagnose

```bash
# Inspect the failed deploy container (may already be stopped)
docker logs <new-api-container> 2>&1 | grep -A 20 "migrate_schemas"

# If migrate exited 0 but check_schema_health failed:
docker logs <new-api-container> 2>&1 | grep -A 10 "check_schema_health"

# Run schema health manually against the running (old) container to confirm it is still OK:
docker exec <running-api-container> python manage.py check_schema_health

# Check for INVALID indexes (AddIndexConcurrently failure):
docker exec <postgres-container> psql -U ibnbatoutaweb_user -d ibnbatoutaweb_platform \
  -c "SELECT indexrelid::regclass, indisvalid FROM pg_index WHERE NOT indisvalid;"
```

### AddIndexConcurrently gotcha

Migrations on hot tables (`Order`, `WalletTransaction`, `Profile`, etc.) must use
`AddIndexConcurrently` with `atomic = False`. A plain `AddIndex` takes an
`ACCESS EXCLUSIVE` lock once **per tenant schema** (N tenants = N sequential write
outages). See **[backend/MIGRATIONS.md](../backend/MIGRATIONS.md)** for the full
convention and the pending conversion gate.

If `CREATE INDEX CONCURRENTLY` leaves an `INVALID` index (interrupted build):

```bash
# Identify the invalid index name from the query above, then drop it:
docker exec <postgres-container> psql -U ibnbatoutaweb_user -d ibnbatoutaweb_platform \
  -c 'SET search_path TO <tenant_schema>; DROP INDEX CONCURRENTLY IF EXISTS <index_name>;'
# Then redeploy to let the migration rebuild it.
```

### Fix — rollback the migration commit

1. Revert the migration file in git (or revert the commit).
2. Push to `main`.
3. Coolify → Redeploy (always manual — see `DEPLOY_REAL_APP_COOLIFY.md`).

The old container is still live throughout — there is no downtime unless you manually
stopped it.

### Verify

```bash
docker exec <api-container> python manage.py check_schema_health   # exit 0
curl -s https://menu.ibnbatoutaweb.com/api/health/ | python3 -m json.tool
# status: "ok"
```

### Post-incident
- Add the migration pattern to `backend/MIGRATIONS.md` if a new failure mode was discovered.
- Run the staging rehearsal described in `MIGRATIONS.md` before re-attempting the migration.

---

## Playbook 6 — Security incident (suspected breach / leaked credential)

### Immediate actions (do within minutes)

```
1. Rotate DJANGO_SECRET_KEY immediately (invalidates all sessions).
2. Rotate DATABASE_URL password.
3. Rotate REDIS_URL password (if auth enabled).
4. Rotate DJANGO_SUPERADMIN_PASSWORD / PLATFORM_ADMIN_PASSWORD env vars.
5. After rotating, set the new values in Coolify env and Redeploy.
   The entrypoint calls `ensure_platform_admin` on boot, which updates the
   platform admin password from DJANGO_SUPERADMIN_PASSWORD automatically.
```

**Generating a new SECRET_KEY:**

```bash
python3 -c "import secrets; print(secrets.token_hex(50))"
```

### Rotate creds in Coolify

1. Open Coolify → resource → **Environment Variables**.
2. Update `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD` (+ `DATABASE_URL`), `REDIS_URL`.
3. Click **Save** → **Redeploy**.

On boot, `ensure_platform_admin` reads `DJANGO_SUPERADMIN_PASSWORD` (mapped to
`PLATFORM_ADMIN_PASSWORD`) and updates the admin account. No `--password` flag is
used (avoids credential leakage via `/proc`).

### Invalidate active sessions

Rotating `DJANGO_SECRET_KEY` invalidates all signed cookies (sessions). If you use
the Redis-backed session cache, also flush Redis:

```bash
docker exec <redis-container> redis-cli FLUSHALL
```

**Warning:** `FLUSHALL` also evicts the Celery queue and all cache keys. Celery will
drain cleanly on next task submission. The beat heartbeat will re-appear within 60 s.

### Per-account login lockout (R7a)

The per-account brute-force lockout is implemented in
`backend/accounts/serializers.py` via a cache-backed fixed-window counter. If you
need to clear a lockout for a specific account during the incident:

```bash
# Clear the lockout key for a user (substitute the user PK)
docker exec <api-container> python manage.py shell -c "
from django.core.cache import cache
cache.delete('login_fail:<USER_PK>')
"
```

### Where are the logs?

| Log channel | Where to read |
|-------------|--------------|
| Security / throttle events | `docker logs <api-container>` — logger `security.throttle` |
| Request log (per-request audit trail) | `docker logs <api-container>` — logger `app.request` |
| Payment mutations | `docker logs <api-container>` — logger `payments` |
| Sentry (5xx + throttle spikes) | <!-- TODO(owner): Sentry project URL --> |
| Optional file log | Set `DJANGO_SECURITY_LOG_FILE` to a path writable by UID 10001 (e.g. under a pre-chowned volume) |

If `DJANGO_LOG_FORMAT=json` (recommended in prod), pipe logs to `jq`:

```bash
docker logs <api-container> 2>&1 | grep '"logger":"security.throttle"' | tail -50
docker logs <api-container> 2>&1 | grep '"logger":"payments"' | tail -50
```

### Verify

```bash
# Confirm new secret key took effect (any old session cookie should be rejected)
curl -s https://menu.ibnbatoutaweb.com/api/health/ | python3 -m json.tool
# status: "ok" (DB + cache up with new creds)

# Confirm admin login still works with new password
# (via browser or curl — do NOT log the password in shell history)
```

### Post-incident
- File a full post-mortem: what was exposed, for how long, blast radius.
- Audit `ADMIN_AUDIT_RETENTION_DAYS` log for abnormal admin actions.
- Review `DJANGO_SENTRY_CAPTURE_THROTTLE` and throttle alert setup: [infra/COOLIFY_THROTTLE_ALERT_VERIFICATION.md](COOLIFY_THROTTLE_ALERT_VERIFICATION.md).
- Consider enabling `DJANGO_SENTRY_CAPTURE_THROTTLE=True` if not already set.

---

## Playbook 7 — Performance / high load

### Symptoms
- Elevated p95 latency (Sentry traces or uvicorn logs)
- `HTTP 504` from Traefik (requests exceeding `HTTP_REQUEST_TIMEOUT`)
- Coolify health check flapping (5s timeout, 5 retries)
- High CPU / memory on VPS

### Diagnose

```bash
# Check container resource usage
docker stats --no-stream

# Check current worker count
docker exec <api-container> printenv GUNICORN_WORKERS
# default: 3

# Check current HTTP timeout
docker exec <api-container> printenv HTTP_REQUEST_TIMEOUT
# default: 120 (seconds); 0 = disabled

# Check health endpoint latency
time curl -s https://menu.ibnbatoutaweb.com/api/health/ > /dev/null

# Check for DB slow queries (inside postgres container)
docker exec <postgres-container> psql -U ibnbatoutaweb_user -d ibnbatoutaweb_platform \
  -c "SELECT pid, now() - pg_stat_activity.query_start AS duration, query
      FROM pg_stat_activity
      WHERE (now() - pg_stat_activity.query_start) > interval '5 seconds';"
```

### Scaling knobs

All set in Coolify environment variables, take effect on next Redeploy:

| Env var | Default | Effect |
|---------|---------|--------|
| `GUNICORN_WORKERS` | `3` | Number of uvicorn (or gunicorn) worker processes |
| `HTTP_REQUEST_TIMEOUT` | `120` | Per-HTTP-request timeout in seconds (WebSockets and SSE `/api/marketplace/track/` are exempt); set `0` to disable |
| `GUNICORN_TIMEOUT` | `60` | Only applies when `USE_ASGI=0` (gunicorn WSGI fallback) |

**Single-flight cache** (`tenancy.cache_utils.get_or_build_single_flight`) prevents
cache-miss stampedes on marketplace and menu endpoints. If a slow rebuild is causing
queuing, check whether Redis is healthy (cache misses degrade to in-process
rebuilds under Redis failure).

### Common fixes

- **CPU spike from migrations:** if a deploy with many tenant schemas is running
  `migrate_schemas --tenant` concurrently with live traffic, it will CPU-spike.
  Schedule heavy deploys in off-peak hours.
- **Uvicorn worker OOM:** increase VPS RAM or reduce `GUNICORN_WORKERS`.
- **Slow DB queries:** check `pg_stat_activity` above; add index if missing (follow
  `backend/MIGRATIONS.md` convention for hot tables).

### Post-incident
- Record p95 latency before/after in the post-incident write-up.
- If workers were increased, document the new value and why.

---

## Playbook 8 — Disk full on VPS

### Symptoms
- `docker logs` shows `No space left on device`
- Postgres writes fail; media uploads fail silently (or container restart fails)
- Backup script fails: `No space left on device` in `/var/log/kepoli-backup.log`

### Key volumes and paths

| Volume / path | Contents | Docker volume name |
|---------------|----------|-------------------|
| `postgres_data` | All DB data (Postgres 16) | `<stack>_postgres_data` |
| `media_data` | User-uploaded images/files | `<stack>_media_data` |
| `redis_data` | Redis AOF (append-only log) | `<stack>_redis_data` |
| `/var/backups/ibnbatoutaweb` | Postgres dump files | host path |
| `/var/log/kepoli-backup.log` | Backup + freshness cron log | host path |

### Diagnose

```bash
# VPS disk overall
df -h /

# Docker volume disk usage
docker system df -v

# Backup dump sizes
du -sh /var/backups/ibnbatoutaweb/
ls -lth /var/backups/ibnbatoutaweb/*.dump | head -10

# Postgres container data dir size
docker exec <postgres-container> du -sh /var/lib/postgresql/data
```

### Fix — free space fast

```bash
# 1. Prune old backup dumps (adjust --retention-days to 7 temporarily)
bash /opt/resto/infra/coolify/backup_postgres.sh \
  --resource-uuid <RESOURCE_UUID> \
  --db-name ibnbatoutaweb_platform \
  --db-user ibnbatoutaweb_user \
  --output-dir /var/backups/ibnbatoutaweb \
  --retention-days 7

# 2. Prune stopped containers and dangling images (safe — does not touch running containers)
docker system prune -f

# 3. Prune Docker build cache
docker builder prune -f

# 4. Truncate backup log if bloated
truncate -s 0 /var/log/kepoli-backup.log
```

**Prune DB rows (via Coolify Scheduled Task or manual exec):**

```bash
# Prune NotificationLog (default 180 days retention)
docker exec <api-container> python manage.py prune_notification_logs

# Prune admin audit logs
docker exec <api-container> python manage.py prune_admin_audit_logs --days 180

# Prune analytics events
docker exec <api-container> python manage.py prune_analytics_events

# Prune staff messages
docker exec <api-container> python manage.py prune_staff_messages
```

### Post-incident
- If backup dumps were the culprit, confirm the `--retention-days` value in the
  installed cron is appropriate.
- If media volume is filling: consider migrating to S3-compatible storage
  (`DJANGO_MEDIA_STORAGE_BACKEND=s3`) — see `DEPLOY_REAL_APP_COOLIFY.md`.
- Add a disk-full alert to the uptime probe if not already configured.

---

## Appendix A — Useful commands

### Health check

```bash
# From outside (public)
curl -s https://menu.ibnbatoutaweb.com/api/health/ | python3 -m json.tool

# From inside VPS (bypasses TLS, useful when Traefik is broken)
docker exec <api-container> \
  python -c "import urllib.request,sys; r=urllib.request.urlopen('http://127.0.0.1:8000/api/health/'); print(r.read().decode())"
```

### Schema health

```bash
# Standard (exit 1 on drift, fails a deploy)
docker exec <api-container> python manage.py check_schema_health

# Warn-only (report drift but exit 0 — for manual inspection)
docker exec <api-container> python manage.py check_schema_health --warn-only
```

### Container logs

```bash
# API (most useful for incidents)
docker logs --tail 200 -f $(docker ps -qf name=api)

# Worker
docker logs --tail 100 -f $(docker ps -qf name=worker)

# Beat
docker logs --tail 100 -f $(docker ps -qf name=beat)

# Postgres
docker logs --tail 100 $(docker ps -qf name=postgres)
```

### Backup and restore scripts

```bash
# Manual backup
bash /opt/resto/infra/coolify/backup_postgres.sh \
  --resource-uuid <RESOURCE_UUID> \
  --db-name ibnbatoutaweb_platform \
  --db-user ibnbatoutaweb_user \
  --output-dir /var/backups/ibnbatoutaweb \
  --retention-days 14

# Freshness probe (exit 1 = stale or missing)
bash /opt/resto/infra/coolify/backup_freshness_probe.sh \
  --output-dir /var/backups/ibnbatoutaweb \
  --db-name ibnbatoutaweb_platform

# Restore into throwaway (never live DB first)
bash /opt/resto/infra/coolify/restore_postgres.sh \
  --resource-uuid <RESOURCE_UUID> \
  --backup-file /var/backups/ibnbatoutaweb/<DUMP>.dump \
  --db-name ibnbatoutaweb_restore_drill \
  --db-user ibnbatoutaweb_user \
  --admin-user ibnbatoutaweb_user
```

### Uptime probe

```bash
bash /opt/resto/infra/coolify/uptime_probe.sh \
  --check "https://menu.ibnbatoutaweb.com/api/health/|200"
```

Full uptime monitoring setup: **[infra/COOLIFY_UPTIME_MONITORING.md](COOLIFY_UPTIME_MONITORING.md)**

### Django management (exec inside api container)

```bash
# Open Django shell
docker exec -it <api-container> python manage.py shell

# Ensure platform admin exists (reads PLATFORM_ADMIN_PASSWORD env)
docker exec <api-container> python manage.py ensure_platform_admin \
  --email <DJANGO_SUPERADMIN_EMAIL>

# Seed subscription plans
docker exec <api-container> python manage.py seed_plans

# Run deploy check manually
docker exec <api-container> python manage.py check --deploy --fail-level ERROR
```

---

## Appendix B — Post-incident write-up template

After every SEV1 and SEV2, complete this template and commit it to
`infra/incidents/YYYY-MM-DD-short-title.md`:

```markdown
## Incident: <short title>
**Date/time:** YYYY-MM-DD HH:MM UTC
**Duration:** X min
**Severity:** SEV1 / SEV2
**Detected by:** uptime probe / Sentry alert / user report

### Timeline
- HH:MM — <event>
- HH:MM — <diagnosis step>
- HH:MM — <fix applied>
- HH:MM — <service restored>

### Root cause
<one paragraph>

### Impact
- Tenants affected: <list or "all">
- Payments lost/delayed: yes/no — <detail>
- Data loss: yes/no — <detail>

### Fix applied
<steps taken>

### Follow-up actions
- [ ] <action> (owner: @..., due: YYYY-MM-DD)

### Runbook gap
<!-- If this incident exposed a gap in the runbook, add a step here -->
```

**What to add to this runbook after each incident:**
- New `check_schema_health` patterns observed
- New failure modes in the entrypoint
- New env vars that caused `check --deploy` to fail
- New disk consumers discovered
