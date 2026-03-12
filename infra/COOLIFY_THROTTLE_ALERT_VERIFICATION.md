# Coolify Throttle Alert Verification

Use this runbook to verify auth throttle protection and security monitoring in production.

## What this validates
- API throttle returns `429` after repeated bad login attempts.
- Backend logs throttle security events (`security.throttle` / `throttle.blocked`).
- Optional Sentry throttle capture flags are visible in runtime env.

## Prerequisites
- You can run commands on the VPS/Coolify host.
- `docker` and `curl` are available.
- The stack is healthy (`api`, `frontend`, `admin`, `postgres`, `redis` running).

## 1) Run throttle verification
From repo root on VPS (example: `/opt/resto`):

```bash
bash infra/coolify/verify_throttle_alerts.sh \
  --resource-uuid <RESOURCE_UUID> \
  --login-url api.kepoli.com \
  --attempts 12
```

Expected output:
- status trace includes at least one `429`
- printed log lines containing `throttle.blocked`
- runtime values for:
  - `DJANGO_SENTRY_CAPTURE_THROTTLE`
  - `DJANGO_SENTRY_THROTTLE_MIN_WAIT_SECONDS`

## 2) If log check fails
- Confirm API container name:
  - `docker ps --format '{{.Names}}' | grep '^api-'`
- Re-run using explicit container:

```bash
bash infra/coolify/verify_throttle_alerts.sh \
  --container api-<uuid>-<id> \
  --login-url https://api.kepoli.com/api/login/
```

## 3) If no `429` is observed
- Increase attempts:
  - `--attempts 20`
- Check throttle rates in backend:
  - `auth_login_burst`
  - `auth_login_sustained`

## 4) Sentry capture guidance (optional)
To emit Sentry events on throttle:
- `DJANGO_SENTRY_CAPTURE_THROTTLE=True`
- `DJANGO_SENTRY_THROTTLE_MIN_WAIT_SECONDS=0` (for drill) or higher for noise control

Then rerun the script and confirm a new warning event in Sentry with:
- tag `security_event=throttle_blocked`
- tag `throttle_scope=auth_login_burst` (or matching scope)

## 5) Recommended cadence
- Run once after each production deploy.
- Run monthly as part of security operations checks.
