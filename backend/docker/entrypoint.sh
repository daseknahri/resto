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

exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout "${GUNICORN_TIMEOUT:-60}" \
  --access-logfile - \
  --error-logfile -
