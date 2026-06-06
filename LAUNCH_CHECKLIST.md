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
| `python manage.py sweep_delivery_jobs` | every ~3 min | Re-dispatch unclaimed delivery jobs, alert the restaurant when none accept, release jobs abandoned by an offline driver, expire stale cash-out codes. **Required for reliable delivery.** |
| `python manage.py send_review_prompts` | every ~15 min | Push the ~30-min post-order review nudge. |
| `python manage.py send_reservation_reminders` | hourly | Reservation reminders. |
| `python manage.py enforce_subscriptions --apply` | daily | Grace-period → mark lapsed tenants suspended (drop out of the marketplace). |

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
