# ADR-0007: Single-VPS Coolify deployment (uvicorn ASGI, one Postgres, one Redis, manual deploy)

- **Status:** Accepted for launch scale — the DR gaps are business-ending and must be fixed
- **Date:** documented 2026-07-10
- **Related risk:** [OPS-1](../RISK_REGISTER.md) (critical), [OPS-2](../RISK_REGISTER.md) (critical), [OPS-3](../RISK_REGISTER.md), [OPS-4](../RISK_REGISTER.md)

## Context
A small team needs a low-cost, low-ops way to run the whole stack with TLS, wildcard subdomain
routing (for per-tenant domains), WebSockets, and background jobs.

## Decision
Deploy on **one VPS via Coolify** (Docker Compose). Services: web (**uvicorn ASGI**, `nproc*2+1`
workers, with `USE_ASGI=0` → gunicorn/WSGI escape hatch), Celery worker, Celery beat, **one
Postgres**, **one Redis**, Traefik (TLS + wildcard + WS upgrade). `docker/entrypoint.sh` is
**fail-closed** (hard-fails in prod without `DJANGO_SECRET_KEY`, refuses `DEBUG=True`).
`/api/health/` is SSL-exempt and reports beat liveness. **Deploys are manual** — `git push` does
not deploy; the owner triggers Coolify in its dashboard.

## Consequences

### Good
- **Excellent ops hygiene for a single node** — fail-closed boot, health probe with beat liveness,
  an 8-playbook runbook under `infra/`. Better than most funded startups.
- One box is cheap and simple; Coolify handles TLS + routing.
- The ASGI middleware is surgical (bounded HTTP timeout that correctly exempts WS/SSE).

### Bad / honest tradeoffs
- **OPS-1 (critical): single Postgres, no replica, no PITR/WAL archiving.** A disk/host failure
  loses every wallet transaction since the last dump (RPO up to ~24h). For a money app this is
  business-ending.
- **OPS-2 (critical): backups are written on-host, not shipped off-box.** Lose the VPS → lose the
  DB *and* the backups together.
- **OPS-3: one Redis backs cache + sessions + Channels + broker.** A stall or the 256 MB ceiling
  degrades four subsystems at once — an eviction storm logs users out mid-shift.
- Single-node = a SPOF for compute too; a bad deploy has no standby.
- **OPS-4: `daphne` is pinned but never invoked** (dead weight; uvicorn is the real server).
- **Manual deploy** is a deliberate safety choice, but means there is no deploy API — automation
  and rollback are hands-on.

## Alternatives considered
- **Managed Postgres with PITR + a managed Redis**, or a second node for standby. Higher cost, but
  directly resolves OPS-1/OPS-3. The money workload justifies at least managed-Postgres-with-PITR.

## When to revisit
**Immediately for the two criticals** — they are not "scale later," they are "one disk away from
gone": ship backups off-box (OPS-2, hours of work) and enable PITR/replication (OPS-1). Split
sessions off Redis (OPS-3) and drop `daphne` (OPS-4) opportunistically. Reconsider single-node
compute when a second paying region/tenant cohort justifies HA.

## Operational notes
- Prod requires a real `DJANGO_SECRET_KEY` and `DEBUG=False` (see `infra/`).
- After deploying, **schedule the sweep commands** in Coolify: `sweep_delivery_jobs` (~60s) and
  `reconcile_driver_earnings` (~15 min). See also [ADR-0009](0009-async-realtime.md).
- Deep infra docs live under `infra/` and `platform/` (DNS/TLS, backups, email, runbook).
