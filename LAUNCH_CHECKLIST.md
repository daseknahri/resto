# Launch Checklist

> Complete before going live. All code changes are already committed to `main`.
> Coolify does NOT auto-deploy on push — trigger manually each time.

---

## 1 — Trigger the deploy in Coolify
Coolify dashboard → your project → **Deploy**

---

## 2 — Set environment variables in Coolify
Go to **Coolify → your service → Environment Variables** and add/update:

| Variable | Value |
|---|---|
| `DJANGO_SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(50))"` |
| `DJANGO_ADMIN_URL` | Something unguessable, e.g. `internal-mgmt-abc123/` |
| `DJANGO_SECURE_HSTS_SECONDS` | `3600` for first week → bump to `31536000` after confirming HTTPS is stable |
| `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` | `True` |
| `DJANGO_EMAIL_HOST` | Your SMTP host (e.g. `smtp.sendgrid.net`) |
| `DJANGO_EMAIL_PORT` | `587` |
| `DJANGO_EMAIL_USE_TLS` | `True` |
| `DJANGO_EMAIL_HOST_USER` | Your SMTP username |
| `DJANGO_EMAIL_HOST_PASSWORD` | Your SMTP password |
| `DJANGO_DEFAULT_FROM_EMAIL` | `noreply@yourdomain.com` |
| `DJANGO_SENTRY_DSN` | From sentry.io (create a Django project if not done) |
| `VAPID_PUBLIC_KEY` | Web-push public key (URL-safe base64). **Without it, all web push silently no-ops** — drivers get no new-job alerts, owners no new-order alerts, customers no review nudge. |
| `VAPID_PRIVATE_KEY` | Web-push private key (PEM). Generate the pair with `python -c "from py_vapid import Vapid01; v=Vapid01(); v.generate_keys(); v.save_key('private.pem')"` (or any VAPID keygen) and paste both. |
| `VAPID_ADMIN_EMAIL` | Contact `mailto:` for push (e.g. `admin@yourdomain.com`). |
| `OPENROUTER_API_KEY` | Optional — only needed for the AI translation feature |
| `DELIVERY_ROAD_FACTOR` | Optional (default `1.3`). Multiplier turning straight-line distance into an estimated road distance for delivery fees. Leave default unless you tune it. |
| `DELIVERY_OSRM_URL` | Optional. Point at a self-hosted OSRM instance (e.g. `http://osrm:5000`) for **real** driving distances + map route lines + ETAs (cached, falls back to the road factor on any error). Unset = use the road factor. **Copy-paste setup: see `OSRM_SELF_HOST.md`.** |
| `VITE_MAP_TILE_URL` / `VITE_MAP_TILE_ATTRIBUTION` | Optional **build-time** (frontend) vars for the map image tiles. Default = OpenStreetMap public tiles (dev only — not licensed for heavy production). Set a MapTiler/Mapbox/Stadia free-tier URL+key before real volume. Must be present when the frontend image is built. See `frontend/src/lib/mapTiles.js`. |

> **Channel layer (real-time):** set `REDIS_URL` in prod — the backend automatically uses
> `channels_redis` when it is set, so WebSocket broadcasts reach every gunicorn/daphne worker.
> Without it, the channel layer is process-scoped (InMemoryChannelLayer) and a broadcast from
> worker A never reaches clients connected to worker B, making real-time kitchen/waiter updates
> unreliable in a multi-worker deployment.  Verify: `REDIS_URL=redis://... python manage.py shell
> -c "from channels.layers import get_channel_layer; cl=get_channel_layer(); print(type(cl).__name__)"` should print `RedisChannelLayer`.
>
> **A7 — this is now ENFORCED at deploy.** The entrypoint runs `python manage.py check --deploy
> --fail-level ERROR`; the `kepoli.E001` deploy check (config/checks.py) HARD-FAILS startup when
> `DEBUG=False` and `REDIS_URL` is unset, so a misconfigured deploy keeps the old healthy container
> instead of coming up with a broken in-memory cache/channel layer. A missing `CELERY_BROKER_URL`
> is a Warning (`kepoli.W001`), not a hard-fail (inline-thread mode is a supported fallback — see §2b).
> Emergency single-process bypass: set `SKIP_DEPLOY_CHECK=1` on the container.

> **Note on CSRF:** leave `DJANGO_CSRF_COOKIE_HTTPONLY` unset/`False`. The SPA reads the
> `csrftoken` cookie in JS and echoes it in the `X-CSRFToken` header (Django double-submit) —
> setting it `True` would 403 every POST/PATCH/DELETE. See the comment in `config/settings.py`.

---

## 2b — Background jobs (cron + notification durability) — pick ONE mode

These periodic commands are idempotent and safe; **nothing runs them automatically** — you
must enable one of the two modes below. `release_scheduled_orders` in particular is REQUIRED
or advance/scheduled orders never reach the kitchen.

| Command | Cadence | Purpose |
|---|---|---|
| `python manage.py release_scheduled_orders` | every ~5 min | Release advance/scheduled orders into the live kitchen flow ~45 min before their time. |
| `python manage.py expire_charge_requests` | every ~10 min | Expire stale wallet-charge approvals. |
| `python manage.py sweep_ride_requests` | **every ~120 s** | Ride-hailing heartbeat: re-push unclaimed ride requests to online car drivers, auto-cancel after 15 min with a rider notification, release rides whose driver went offline/stale pre-pickup. **Required for reliable rides.** |
| `python manage.py sweep_delivery_jobs` | **every ~60 s** | Advance ranked-offer cascades (60 s offer window), re-broadcast unclaimed open-pool jobs, alert the restaurant when none accept, release jobs abandoned by an offline driver, expire stale cash-out codes. **Required for reliable delivery** — the dispatch heartbeat. |
| `python manage.py send_review_prompts` | every ~15 min | Push the ~30-min post-order review nudge. |
| `python manage.py send_reservation_reminders` | hourly | Reservation reminders. |
| `python manage.py enforce_subscriptions --apply` | daily | Grace-period → mark lapsed tenants suspended (drop out of the marketplace). |
| `python manage.py fetch_currency_rates` | daily | Refresh MAD exchange rates used for multi-currency display. |
| `python manage.py send_daily_summary` | daily at 23:30 UTC | End-of-day owner digest: order count, total revenue, cash/wallet split, top 3 dishes. Idempotent (skips zero-order tenants and re-runs on same day). |
| `python manage.py prune_analytics_events` | daily | Delete analytics events older than 90 days — bounds tenant table growth. |
| `python manage.py prune_admin_audit_logs` | daily | Delete admin audit logs past `ADMIN_AUDIT_RETENTION_DAYS` (default 180) — bounds growth. |
| `python manage.py prune_notification_logs` | daily | Delete NotificationLog rows older than 180 days — bounds shared-schema table growth (OPS-4). |
| `python manage.py prune_winback_nudges` | daily | Delete WinbackNudge rows older than 120 days — beyond the 90-day dedupe window + margin (OPS-4). |
| `python manage.py prune_staff_messages` | daily | Delete StaffMessage rows older than 90 days per tenant — bounds per-tenant table growth (OPS-4). |
| `python manage.py prune_auth_tokens` | daily | Delete consumed/expired PasswordResetToken + ActivationToken rows older than 30 days — bounds shared-schema table growth (OPS-5c). |
| `python manage.py send_winback_nudges` | hourly | Win-back push to lapsed customers at ~11:00 local time for opted-in tenants (at most 1 nudge/customer/90 days). |

> `sweep_unverified_wallets` is a **manual one-off**, not a recurring cron — new unverified
> credits are already blocked at the service layer, so run it once with `--apply` only if you
> need to clear legacy balances.

### Mode A — Simple (no Celery). Good for launch / first test.
- Leave `CELERY_BROKER_URL` **unset**. Notifications send in-process (works fine, no worker).
- The `worker` + `beat` compose services stay **idle** (they no-op when the broker is unset).
- Add each command above as a **Coolify Scheduled Task**: open the **`api`** resource →
  *Scheduled Tasks* → container `api`, command `python manage.py <command>`, cron as in the table
  (`*/5 * * * *`, `*/10 * * * *`, `*/15 * * * *`, `0 * * * *`, `0 3 * * *`).

### Mode B — Durable queue (Celery). Recommended at volume.
The `worker` and `beat` services are **already defined** in `docker-compose.coolify.yml`
(idle until enabled). To switch on:
1. Set env **`CELERY_BROKER_URL`** = the same value as your `REDIS_URL` (optionally
   `CELERY_RESULT_BACKEND` too), then **redeploy**.
2. The `worker` starts consuming the notification queue; `beat` starts running every command
   in the table on the `CELERY_BEAT_SCHEDULE`.
3. **Remove the Mode-A Scheduled Tasks** — otherwise the cron jobs run twice.

> ⚠️ It's broker-set ⇔ worker-running, **together**. The compose ships both, so a redeploy with
> `CELERY_BROKER_URL` set turns the whole thing on atomically; unset turns it back off.

Also enable Coolify's **Postgres backup schedule** (daily, ≥30-day retention) and test a restore.

---

## 3 — Update `nginx.conf` to match your new admin URL
If you set `DJANGO_ADMIN_URL=internal-mgmt-abc123/`, also update
`frontend/nginx.conf`:

```nginx
# Change this block's location to match:
location ^~ /internal-mgmt-abc123/ {
  proxy_pass http://api:8000;
  ...
}
```

Then redeploy.

---

## 4 — Run the superadmin setup command (first deploy only)
```bash
# Coolify → api service → Terminal, or via docker exec
python manage.py ensure_platform_admin \
  --email your@email.com \
  --password "a-strong-password-here"
```

---

## 5 — Seed the plans (if not already done)
```bash
python manage.py seed_plans
```

---

## 6 — Verify security headers
Test with https://securityheaders.com — paste your domain.
Expected green ratings:
- `Content-Security-Policy`
- `X-Frame-Options`
- `X-Content-Type-Options`
- `Referrer-Policy`
- `Permissions-Policy`
- `Strict-Transport-Security`

---

## 7 — Complete Arabic translations (deferred)
The spawned task chip fills in the 33 missing AR sections.
App falls back to English gracefully in the meantime.

---

## 8 — Monitor first 24 hours after launch
- Check **Sentry** for runtime errors
- Check **Coolify logs** for Django startup warnings
- Verify OTP emails arrive (test phone/email sign-in flows)
- Place a test order through the marketplace
- Test the owner dashboard on mobile

---

## 9 — Backups, restore, and deploy rollback (OPS-5 H)

### 9a — Automated PostgreSQL backups

Coolify exposes a **Backup** tab on the Postgres resource. Enable it:

- Frequency: daily (0 2 * * * recommended — 2 AM UTC, before the daily digest).
- Retention: at least 30 days.
- Test: after the first automated backup completes, use Coolify's restore UI or run the
  manual restore procedure below to confirm the dump is valid.

Alternatively, add a Coolify **Scheduled Task** on the `api` container:

```
pg_dump $DATABASE_URL -Fc -f /app/backups/kepoli_$(date +%Y%m%d).dump
```

(Mount a persistent volume at `/app/backups` so dumps survive container restarts.)

### 9b — Per-tenant-schema restore (django-tenants)

django-tenants stores each restaurant in its own Postgres schema (e.g. `tenant_abc`).
To restore one tenant without touching others:

1. Dump the individual schema from a full backup:
   ```bash
   pg_restore -Fc --schema=tenant_abc --no-owner -d $DATABASE_URL kepoli_YYYYMMDD.dump
   ```
   This overwrites only the `tenant_abc` schema. All other schemas are untouched.

2. If the schema does not yet exist (e.g. re-provisioning a deleted tenant), create it first:
   ```bash
   psql $DATABASE_URL -c "CREATE SCHEMA IF NOT EXISTS tenant_abc;"
   pg_restore -Fc --schema=tenant_abc --no-owner -d $DATABASE_URL kepoli_YYYYMMDD.dump
   ```

3. Verify with a sanity check:
   ```bash
   python manage.py shell -c "
   from django_tenants.utils import schema_context
   with schema_context('tenant_abc'):
       from menu.models import Order; print(Order.objects.count(), 'orders')
   "
   ```

The public schema (shared tables: accounts, tenancy, sales) is separate. Only restore it
from a backup if the shared data is corrupted — doing so overwrites ALL tenant references.

### 9c — Deploy rollback (migrations auto-run on deploy)

`docker/entrypoint.sh` runs `python manage.py migrate` on every deploy. If a migration
ships a breaking schema change you need to roll back:

1. **Revert the code** in Coolify by deploying the previous Git commit (Coolify keeps
   deployment history). The entrypoint will not re-run the migration (Django skips
   already-applied migrations). The schema and the old code are now in sync.

2. **If you also need to unapply the migration** (the schema change is incompatible with
   the running code), unapply it before reverting the code:
   ```bash
   # In the Coolify api container terminal:
   python manage.py migrate <app_label> <previous_migration_number>
   # Example: python manage.py migrate menu 0057_orderpayment_idempotency_key
   ```
   Then deploy the previous commit. Django will skip the already-unapplied migration.

3. **Data-loss risk**: `RunPython` migrations that delete or transform data are
   irreversible without a backup. Always take a manual pg_dump before deploying a
   migration that drops columns or rewrites rows, and test the rollback procedure in a
   staging environment first.

4. **Zero-downtime**: Coolify deploys with a rolling restart; there is a brief window
   during which both the old and new code run against the new schema. Design migrations
   to be backward-compatible (add-only) before a subsequent cleanup migration removes
   old columns.

---

## Social link previews (OG)
After each deploy, verify WhatsApp unfurls work — the nginx bot branch must route
crawler user-agents to the backend OG view:
```
curl -s -A "WhatsApp/2.23" https://<tenant-host>/ | grep og:title     # tenant name
curl -s -A "facebookexternalhit/1.1" https://<platform-host>/order/<slug> | grep og:image
```
Humans must still get the SPA: `curl -s -A "Mozilla/5.0" https://<tenant-host>/ | grep '<div id="app">'`
