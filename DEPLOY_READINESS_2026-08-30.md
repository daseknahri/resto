# Deploy Readiness — 2026-08-30 performance batch (#296–#309)

**Scope:** ship the merged-but-undeployed backlog to prod (Coolify). This is an **incremental**
deploy on top of the already-live app — no data model rewrites, no breaking API changes. The
headline is the **performance pass** (11 CI-gated fixes, #297–#304, #306–#308) plus the recent
hardening work merged since the last deploy.

> This is a **batch-specific** checklist. For the mechanics of a Coolify deploy, use the existing
> runbooks — don't restate them here:
> [`infra/DEPLOYMENT_RUNBOOK.md`](infra/DEPLOYMENT_RUNBOOK.md),
> [`infra/COOLIFY_STAGING_DEPLOY_SMOKE.md`](infra/COOLIFY_STAGING_DEPLOY_SMOKE.md),
> [`infra/INCIDENT_RUNBOOK.md`](infra/INCIDENT_RUNBOOK.md),
> [`Pre_Deployment_QA_Checklist.md`](Pre_Deployment_QA_Checklist.md).
> Full changelog of what's in this batch: [`docs/SESSION_LOG.md`](docs/SESSION_LOG.md).

---

## 0. What this batch changes (deploy-relevant summary)

| Area | Change | Deploy sensitivity |
|---|---|---|
| **Notifications (#302)** | Bulk order-confirm + 8 other sync email/SMS sends now go through `enqueue()` / Celery | **Requires a running Celery worker + broker** — see §2 (the win is only realized if Celery is on) |
| **Indexes (#297/#298/#307)** | 3 new **concurrent-index** migrations on shared/public tables | **Needs the staging-migration rehearsal** — see §1 |
| Query/caching (#299/#300/#303/#304) | Query folds, analytics caching, `bulk_create` | Code-only; no special handling |
| Frontend (#301/#306/#308) | Cold-load, formatter cache, flash-sale re-render, debounce | Static build; Sentry-Replay CSP caveat only if replay is enabled later — see §2 |

Everything is behavior-preserving. No feature flags to flip. No consumer-facing API contract changes.

---

## 1. Pre-deploy — DB migrations (the one thing to rehearse)

`makemigrations --check` is green on `main` (no unmade migrations). The deploy runs
`migrate_schemas --shared` then `migrate_schemas --tenant` (per the entrypoint) and applies all
pending migrations idempotently. **Three of the pending migrations build indexes CONCURRENTLY**
(`AddIndexConcurrently` + `atomic = False`), and per [`backend/MIGRATIONS.md`](backend/MIGRATIONS.md)
those are **gated on a one-time staging rehearsal** before they touch prod:

| Migration | Table / app | Index | Schema scope |
|---|---|---|---|
| `accounts/0071_deliveryjob_deliveryjob_declined_gin` | `DeliveryJob` (accounts) | GIN on `declined_by` | `SHARED_APPS` → public, **×1** |
| `accounts/0072_deliveryjob_deliveryjob_status_deliv_idx` | `DeliveryJob` (accounts) | btree `(status, delivered_at)` | `SHARED_APPS` → public, **×1** |
| `sales/0024_adminauditlog_indexes` | `AdminAuditLog` (sales) | btree `-created_at`, `(tenant,-created_at)` | `SHARED_APPS` → public, **×1** |

**Why these are the safer case:** all three tables live in `SHARED_APPS`, so each index builds
**once** via `migrate_schemas --shared` on the public schema — **not** the per-tenant loop, and
**not** the `auto_create_schema` tenant-provisioning path that `MIGRATIONS.md`'s gate warns about
(that risk is specific to tenant-app CONCURRENTLY inside a provisioning transaction; these aren't
tenant apps).

- [ ] **Run the staging rehearsal** on a staging DB with ≥2 real tenant schemas (mirrors the prod
      loop) per [`infra/COOLIFY_STAGING_DEPLOY_SMOKE.md`](infra/COOLIFY_STAGING_DEPLOY_SMOKE.md) +
      `MIGRATIONS.md`. The one thing to confirm: **`migrate_schemas --shared` runs the
      `atomic = False` migrations OUTSIDE any wrapping transaction** (CREATE INDEX CONCURRENTLY
      aborts hard inside an open transaction). Include any *other* concurrent migrations not yet
      applied in prod (e.g. `menu/0060`, `0062`, `0066`) in the same rehearsal.
- [ ] Confirm the rehearsal migrate step completes with **no `CREATE INDEX CONCURRENTLY cannot run
      inside a transaction block`** error and the indexes exist (`\d+ deliveryjob` / `\d+ sales_adminauditlog`).
- [ ] **Take a DB backup** before the prod migrate ([`infra/COOLIFY_DB_BACKUP_RUNBOOK.md`](infra/COOLIFY_DB_BACKUP_RUNBOOK.md)).

> Rollback for a mid-build concurrent index is clean: an interrupted `CREATE INDEX CONCURRENTLY`
> leaves an `INVALID` index that Postgres ignores; drop it (`DROP INDEX CONCURRENTLY <name>`) and
> re-run. It never blocks reads/writes, so a failure here does not cause an outage.

---

## 2. Pre-deploy — required config / env

The perf win from **#302 is only real if Celery is actually running.** `enqueue()` sends via
`task.delay()` when `CELERY_BROKER_URL` is set; otherwise it runs the work **inline** on a bounded
thread pool (dev/degraded) and, in prod, persists it to a durable `OutboxMessage` that `relay_outbox`
(run at boot) recovers — so **a notification is never silently lost**, but without a broker it's no
longer *off the request thread* (the whole point of #302).

- [ ] **`CELERY_BROKER_URL`** is set (Redis) — **this is the gate** for both the #302 async
      notifications and every `CELERY_BEAT_SCHEDULE` cron (§3). Good news: this is **self-enforcing**
      — `config.checks.celery_broker_configured_for_durability` is a `deploy=True` check, so a
      broker-less image **fails `check --deploy` and won't boot** (the entrypoint runs it at
      `--fail-level ERROR`). So the main risk isn't a broker-less deploy (blocked) but the broker
      **dying after boot** — the `/api/health/` beat-heartbeat going STALE (§3) is the signal.
- [ ] **`REDIS_URL`** is set — boot **halts** without it in prod (`config/checks.py` ERRORs at
      `check --deploy`); also backs `SESSION_ENGINE=cache` and the Channels layer.
- [ ] `DJANGO_SECRET_KEY` set (real), `DJANGO_DEBUG=False` — standard, unchanged.
- [ ] SMTP / Twilio creds present (unchanged) — the notifications moved to async still need the same
      delivery credentials; async just moves the send off the request thread.
- [ ] **Sentry Replay CSP (only if you enable replay later):** #301 lazy-loads the Replay recorder
      from `browser.sentry-cdn.com`. Replay is **dormant** (sample rate 0) so nothing is needed for
      this deploy. If you ever raise the replay sample rate, first add `browser.sentry-cdn.com` to
      the `script-src` CSP allow-list in [`frontend/nginx.conf`](frontend/nginx.conf), or the
      recorder load is blocked. No action required now.

---

## 3. Pre-deploy — runtime services (NOT cron scheduling)

**Correction to the old "schedule the two sweep crons" note:** the sweeps are **already wired** in
`CELERY_BEAT_SCHEDULE` (`backend/config/settings.py`) — `sweep_delivery_jobs` (60s),
`reconcile_driver_earnings` (15 min), `sweep_ride_requests` (120s), `enforce_subscriptions` (daily),
`prune_admin_audit_logs` (uses #298's new index), plus ~20 others. There is nothing to schedule.
The requirement is that the **worker + beat containers run**:

- [ ] The **`worker`** service is up (`celery -A config worker -Q notifications,cron`) — processes
      the #302 notification queue **and** the `cron.*` sweep/reconcile/prune tasks.
- [ ] The **`beat`** service is up (`celery -A config beat`) — fires the schedule.
- [ ] `/api/health/` shows the beat heartbeat **fresh** (not STALE > 180s) — this is the built-in
      signal that beat+worker are actually processing (`write-beat-heartbeat`, every 60s).
- [ ] Postgres `max_connections` still has headroom for 3 uvicorn workers + worker + beat
      (compose comment targets 50; unchanged by this batch).

---

## 4. Pre-deploy gate (verify green)

- [x] All PRs merged to `main` (#296–#309); `main` is green on every CI job (backend, frontend,
      docker, e2e, Trivy). `main` @ `e4fc6b8`.
- [x] Backend suite: **5042 passed, 0 new failures** (local baseline: 1 Django-pin + ~82 DB-conn
      errors, both known/expected without a local Postgres).
- [ ] Confirm the exact release commit and that nothing merged after your last review.

---

## 5. Deploy + smoke (per the Coolify runbook)

Follow [`infra/COOLIFY_STAGING_DEPLOY_SMOKE.md`](infra/COOLIFY_STAGING_DEPLOY_SMOKE.md) then promote.
Beyond the standard smoke, spot-check the paths this batch touched:

- [ ] **Async notifications (#302):** place an order and mark it through statuses (and do a **bulk
      confirm** of several orders) → the owner UI returns **fast** (no multi-second stall), and the
      customer status **email/SMS still arrives** (now via the worker). Confirm the worker log shows
      `order_status_email` / `send_transactional_email` tasks running.
- [ ] **Customer OTP (#302):** request a login OTP → SMS arrives; the request returns immediately.
- [ ] **Driver poll (#297):** a driver's active-jobs/earnings poll returns normally (GIN index live).
- [ ] **Admin analytics (#303):** the platform analytics dashboard loads and numbers are correct
      (first load builds; a reload within 45s is a cache hit).
- [ ] **Marketplace menu (#306/#308):** open a storefront menu, type in search (smooth, debounced),
      and — if a flash sale is active — confirm prices/countdown render correctly and the page isn't
      janky.
- [ ] **Reservations (#300):** owner reservations list + counts render with correct totals.

---

## 6. Rollback triggers

Roll back (Coolify → previous deployment) if, within the first ~15 min:

- Error rate on `/api/**` climbs materially above the pre-deploy baseline (watch Sentry / logs).
- **Notifications stop arriving** (status emails/SMS, OTP) — most likely a Celery worker/broker
  issue (§2/§3), not the app code; check the worker service + `CELERY_BROKER_URL` first before
  rolling back the whole release.
- Any **500** on the order-status, bulk-confirm, driver-poll, or admin-analytics endpoints.
- A migration step errors (see §1 rollback note — a concurrent-index failure is self-contained and
  does **not** require a full rollback; drop the `INVALID` index and re-run).

**Migrations are additive** (new indexes + a serializer/query change) — rolling back the app image
does **not** require dropping the new indexes (they're inert to the old code). Leave them; they only
help.

---

## 7. Post-deploy

- [ ] Beat heartbeat fresh; a full `sweep_delivery_jobs` + `reconcile_driver_earnings` cycle runs
      without errors in the worker log.
- [ ] Confirm metrics nominal (latency on the order-status + menu endpoints should be **flat or
      better** — that's the point of this batch).
- [ ] Note the deployed commit for the next batch's "since last deploy" diff.
- [ ] (Owner backlog, unrelated to this deploy) the remaining items still need you: Stripe PSP
      account, first non-MAD tenant, rides go-live, the deferred Dependabot majors, and the
      Python-3.14-vs-3.12 CI test-parity call (see [`docs/SESSION_LOG.md`](docs/SESSION_LOG.md)).
