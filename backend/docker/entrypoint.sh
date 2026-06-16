#!/bin/sh
set -eu

echo "[entrypoint] migrate_schemas --shared"
python manage.py migrate_schemas --shared --noinput
echo "[entrypoint] migrate_schemas --tenant"
python manage.py migrate_schemas --tenant --noinput

# Assert the DB physically matches the models for critical tables. Catches the
# "migration recorded as applied but column never created" case that `set -e`
# can't (migrate exits 0). On drift this exits non-zero and -- thanks to set -e --
# halts startup, so Coolify keeps the old healthy container instead of serving
# 500s. Bypass only in an emergency with SKIP_SCHEMA_HEALTHCHECK=1.
if [ "${SKIP_SCHEMA_HEALTHCHECK:-0}" = "1" ]; then
  echo "[entrypoint] SKIP_SCHEMA_HEALTHCHECK=1 -> skipping schema health check"
else
  echo "[entrypoint] check_schema_health"
  python manage.py check_schema_health
fi

echo "[entrypoint] collectstatic"
python manage.py collectstatic --noinput
echo "[entrypoint] seed_plans"
python manage.py seed_plans

# A7: fail a misconfigured prod deploy loudly. The deploy check (config/checks.py)
# ERRORs when REDIS_URL is unset in production -- without it the cache + channel
# layer fall back to in-process backends, so cross-worker broadcasts (live order/
# paid updates) are lost and the shared cache (idempotency mutexes/throttles) is
# not shared. --fail-level ERROR halts startup (set -e), so Coolify keeps the old
# healthy container instead of serving a broken one. A missing CELERY_BROKER_URL is
# only a Warning (inline-thread mode), so it does NOT block. Bypass in an emergency
# single-process deploy with SKIP_DEPLOY_CHECK=1.
if [ "${SKIP_DEPLOY_CHECK:-0}" = "1" ]; then
  echo "[entrypoint] SKIP_DEPLOY_CHECK=1 -> skipping deploy config check"
else
  echo "[entrypoint] check --deploy"
  python manage.py check --deploy --fail-level ERROR
fi

# OPS-5d D: never pass the admin password via --password — a CLI arg is visible
# in /proc, `docker inspect` and deploy logs.  ensure_platform_admin already
# prefers the PLATFORM_ADMIN_PASSWORD env var, so export it (mapping from the
# existing DJANGO_SUPERADMIN_PASSWORD secret for backward compatibility) and call
# the command WITHOUT --password.
if [ -n "${DJANGO_SUPERADMIN_EMAIL:-}" ] && [ -n "${DJANGO_SUPERADMIN_PASSWORD:-}" ]; then
  export PLATFORM_ADMIN_PASSWORD="${PLATFORM_ADMIN_PASSWORD:-$DJANGO_SUPERADMIN_PASSWORD}"
  python manage.py ensure_platform_admin \
    --email "${DJANGO_SUPERADMIN_EMAIL}"
fi

# R13: warn loudly (do NOT block boot) if local-disk media is not writable by this
# non-root (UID 10001) container. Image uploads would fail until the media volume is
# chowned, but the core flows (orders/menus/payments) do not touch /app/media — so a
# non-writable media dir is a DEGRADED state, not a reason to refuse to serve the whole
# app (unlike schema-health / check --deploy above, which fail closed because they would
# serve 500s / lose money events). Skipped when media is on object storage (S3).
# Fix uploads with: docker run --rm -v <media_volume>:/d alpine chown -R 10001:10001 /d
# Silence the warning with SKIP_MEDIA_WRITABLE_CHECK=1.
_media_backend="$(printf '%s' "${DJANGO_MEDIA_STORAGE_BACKEND:-local}" | tr '[:upper:]' '[:lower:]')"
if [ "${SKIP_MEDIA_WRITABLE_CHECK:-0}" = "1" ]; then
  echo "[entrypoint] SKIP_MEDIA_WRITABLE_CHECK=1 -> skipping media writability check"
elif [ "$_media_backend" = "s3" ] || [ "$_media_backend" = "s3boto3" ] || [ "$_media_backend" = "object" ]; then
  echo "[entrypoint] media on object storage ($_media_backend) -> skipping local media writability check"
else
  _media_dir="/app/media"
  if ( touch "$_media_dir/.writable-probe" && rm -f "$_media_dir/.writable-probe" ) 2>/dev/null; then
    echo "[entrypoint] media dir $_media_dir is writable"
  else
    echo "[entrypoint] WARNING: $_media_dir is not writable by UID $(id -u) — image uploads will FAIL until the media volume is chowned: docker run --rm -v <media_volume>:/d alpine chown -R 10001:10001 /d . Serving anyway (core flows do not need media writes)." >&2
  fi
fi

# Serve under ASGI (uvicorn) so WebSockets work. HTTP behaves identically under
# both servers — only WebSockets require ASGI. Instant rollback: set USE_ASGI=0
# in the environment to return to the previous gunicorn/WSGI server (no code change).
if [ "${USE_ASGI:-1}" = "1" ]; then
  # OPS-5d D: trust X-Forwarded-* only from the docker bridge subnet (where our
  # nginx proxy lives), NOT from '*'.  With '*', uvicorn forwards any attacker-
  # injected XFF straight through to DRF; restricting it to 172.16.0.0/12 means
  # uvicorn strips spoofed XFF before DRF/get_request_ip ever see it — defense in
  # depth complementing the trusted-proxy throttle ident fix (OPS-5d C).
  # R13/Goal-B: --timeout-keep-alive 75 keeps idle HTTP/1.1 keep-alive
  # connections open slightly past the default nginx proxy_read_timeout (60 s)
  # so the proxy closes first rather than uvicorn — avoids spurious 502s.
  # --timeout-graceful-shutdown 30 gives in-flight requests 30 s to drain when
  # a worker is being replaced (SIGTERM from a rolling restart).
  # Per-request HTTP timeout lives in BoundedHTTPMiddleware (config/asgi.py);
  # uvicorn has no --timeout-request flag and we must NOT apply asyncio.wait_for
  # at the ProtocolTypeRouter level because that would also kill websockets.
  exec uvicorn config.asgi:application \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --proxy-headers \
    --forwarded-allow-ips='172.16.0.0/12' \
    --timeout-keep-alive 75 \
    --timeout-graceful-shutdown 30
else
  exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-60}" \
    --access-logfile - \
    --error-logfile -
fi
