#!/bin/sh
set -eu

python manage.py migrate_schemas --shared --noinput
python manage.py migrate_schemas --tenant --noinput
python manage.py collectstatic --noinput
python manage.py seed_plans

if [ -n "${DJANGO_SUPERADMIN_EMAIL:-}" ] && [ -n "${DJANGO_SUPERADMIN_PASSWORD:-}" ]; then
  python manage.py ensure_platform_admin \
    --email "${DJANGO_SUPERADMIN_EMAIL}" \
    --password "${DJANGO_SUPERADMIN_PASSWORD}"
fi

# Serve under ASGI (uvicorn) so WebSockets work. HTTP behaves identically under
# both servers — only WebSockets require ASGI. Instant rollback: set USE_ASGI=0
# in the environment to return to the previous gunicorn/WSGI server (no code change).
if [ "${USE_ASGI:-1}" = "1" ]; then
  exec uvicorn config.asgi:application \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --proxy-headers \
    --forwarded-allow-ips='*'
else
  exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-60}" \
    --access-logfile - \
    --error-logfile -
fi
