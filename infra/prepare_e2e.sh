#!/usr/bin/env bash
set -euo pipefail

ADMIN_EMAIL="${ADMIN_EMAIL:-e2e-admin@example.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-E2E_Admin_123!}"
DEMO_DOMAIN="${DEMO_DOMAIN:-demo.localhost}"
OWNER_EMAIL="${OWNER_EMAIL:-test_resto_user@demo.local}"
OWNER_PASSWORD="${OWNER_PASSWORD:-admin123}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"

PYTHON_BIN="${PYTHON_BIN:-$BACKEND_DIR/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3 || command -v python)"
fi

if [[ -z "${PYTHON_BIN:-}" ]]; then
  echo "Python executable not found. Ensure backend virtualenv exists." >&2
  exit 1
fi

cd "$BACKEND_DIR"
"$PYTHON_BIN" manage.py migrate
"$PYTHON_BIN" manage.py shell -c "from django.core.cache import cache; cache.clear(); print('Cache cleared')"
"$PYTHON_BIN" manage.py seed_plans --with-demo --domain "$DEMO_DOMAIN" --email "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD"
"$PYTHON_BIN" manage.py ensure_platform_admin --email "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD"
"$PYTHON_BIN" manage.py shell -c "from accounts.models import User; from tenancy.models import Tenant; t = Tenant.objects.get(slug='demo'); u, _ = User.objects.get_or_create(email='$OWNER_EMAIL', defaults={'username': '$OWNER_EMAIL', 'role': 'tenant_owner', 'tenant': t}); u.username = '$OWNER_EMAIL'; u.role = 'tenant_owner'; u.tenant = t; u.is_active = True; u.set_password('$OWNER_PASSWORD'); u.save(); print('Demo owner ensured:', u.email)"

echo "E2E preparation complete."
echo "Admin credentials: $ADMIN_EMAIL / $ADMIN_PASSWORD"
echo "Owner credentials: $OWNER_EMAIL / $OWNER_PASSWORD"
