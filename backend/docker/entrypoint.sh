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

# Serve under ASGI (uvicorn) so WebSockets work. HTTP behaves identically under
# both servers — only WebSockets require ASGI. Instant rollback: set USE_ASGI=0
# in the environment to return to the previous gunicorn/WSGI server (no code change).
if [ "${USE_ASGI:-1}" = "1" ]; then
  # OPS-5d D: trust X-Forwarded-* only from the docker bridge subnet (where our
  # nginx proxy lives), NOT from '*'.  With '*', uvicorn forwards any attacker-
  # injected XFF straight through to DRF; restricting it to 172.16.0.0/12 means
  # uvicorn strips spoofed XFF before DRF/get_request_ip ever see it — defense in
  # depth complementing the trusted-proxy throttle ident fix (OPS-5d C).
  exec uvicorn config.asgi:application \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --proxy-headers \
    --forwarded-allow-ips='172.16.0.0/12'
else
  exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-60}" \
    --access-logfile - \
    --error-logfile -
fi
