# Coolify orphan-container cleanup (incident fix #1)

Durable fix **#1** for the [2026-09-18 connection-exhaustion outage](../docs/INCIDENT_2026-09-18_db_connection_exhaustion.md).
This is the **real recurrence fix**; PR #379 (Postgres headroom) is only the margin behind it.

## What happened

Coolify deploys this stack with the **Docker Compose build pack** on `docker-compose.coolify.yml`
(`DEPLOY_REAL_APP_COOLIFY.md`). Across ~4 months of redeploys, **8 superseded `admin-*` containers
were never removed** — each stayed `Up` and held persistent Postgres connections (`CONN_MAX_AGE=600`)
until `max_connections` was exhausted (`FATAL: sorry, too many clients already`) and every `/api/*`
returned a bare 500. A plain Coolify **Restart/Stop** did not help — it only touches the *current*
deployment, not the orphans.

`admin` is a genuine long-lived compose service (the same Vue image as `frontend`, on the admin
domain), so its stale copies are true **orphans** — containers Compose should have replaced but didn't,
most likely because the container/project name changes across deploy hashes so `docker compose up`
doesn't recognise them as replaceable.

> Note: ordinary `docker container prune` would **not** have fixed this — the orphans were *running*,
> and prune only removes *stopped* containers.

## Fix — two layers

### Layer 1 (root cause): make the deploy reap orphans

Configure Coolify so its `docker compose up` includes **`--remove-orphans`**, which stops and removes
any container in the project that is no longer part of the current compose file. Depending on your
Coolify version, one of:

- **Compose build-pack option:** in the resource's **Configuration → Docker Compose** settings, enable
  the "remove orphans on deploy" / `--remove-orphans` toggle if present.
- **Custom deploy command:** if your Coolify version exposes a compose-up command/flags field, add
  `--remove-orphans` there.
- **Stabilise the project name:** ensure the Compose **project name** is pinned across deploys (a fixed
  `-p <project>` / `COMPOSE_PROJECT_NAME`), so Compose sees old containers as the same project and
  replaces them instead of leaving orphans.

After enabling, do one redeploy and confirm on the host that each service has **exactly one** running
container:

```bash
docker ps --format '{{.Names}}' | sort
```

### Layer 2 (safety net): scheduled prune

Until Layer 1 is proven across a few deploys — and as belt-and-suspenders after — run
[`prune_stale_stack_containers.sh`](coolify/prune_stale_stack_containers.sh). It keeps only the newest
running container per **stateless** service (`api,admin,frontend,worker,beat`) and removes older
duplicates. It **never** touches `postgres`/`redis`, and it is **dry-run by default**.

```bash
# 1. Find a stable substring for THIS stack's containers:
docker ps --format '{{.Names}}' | sort

# 2. Dry-run (shows what it WOULD remove):
infra/coolify/prune_stale_stack_containers.sh --prefix ibnbatoutaweb

# 3. Apply once you trust the output:
infra/coolify/prune_stale_stack_containers.sh --prefix ibnbatoutaweb --apply
```

Schedule it as a host cron or a Coolify **server-level Scheduled Task** (every ~15 min):

```cron
*/15 * * * * /path/to/repo/infra/coolify/prune_stale_stack_containers.sh --prefix ibnbatoutaweb --apply >> /var/log/kepoli-prune.log 2>&1
```

## Verify recovery

After a prune, if the pool was exhausted the freed connections may linger until Postgres reaps them:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://menu.ibnbatoutaweb.com/api/health/
# expect 200; if still 503 {db: down}, restart postgres to drop idle sessions:
docker restart "$(docker ps --format '{{.Names}}' | grep '^postgres-')"
```

## Related
- Headroom behind this fix: PR #379 (`PG_MAX_CONNECTIONS` 50→100).
- Reserve emergency slots so this is diagnosable next time: [`sql/least_privilege_app_role.sql`](sql/least_privilege_app_role.sql) (fix #3) — a non-superuser app role stops the app consuming `superuser_reserved_connections`.
