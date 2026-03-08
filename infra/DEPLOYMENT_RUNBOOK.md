# Deployment Runbook (VPS Production)

## Scope
This runbook deploys the multi-tenant restaurant menu SaaS on a VPS using:
- PostgreSQL
- Django + Gunicorn
- Vue static build served by Nginx
- Wildcard subdomains for tenant routing

## 1. Prerequisites
- Ubuntu 22.04+ VPS
- Domain configured with:
  - `A` record for root (for example `example.com`) -> VPS IP
  - `A` or `CNAME` wildcard for tenants (`*.example.com`) -> VPS IP
- SSH access with sudo user
- Python 3.12, Node 20, Nginx, PostgreSQL 16 installed

## 2. Release Inputs
- Git revision/tag to deploy
- Backend env file (production secrets)
- Frontend env file (production API URL)
- Database backup before migration

## 3. Initial Server Setup
1. Create app user and directories.
2. Clone repository into `/srv/resto`.
3. Create Python virtualenv in `/srv/resto/backend/.venv`.
4. Install backend dependencies:
   - `pip install -r backend/requirements.txt`
5. Install frontend dependencies:
   - `cd frontend && npm ci`
6. Build frontend:
   - `npm run build`
7. Configure PostgreSQL user/database and set `DATABASE_URL`.

## 4. Required Production Environment
Set in backend `.env`:
- `DJANGO_DEBUG=False`
- `DJANGO_SECRET_KEY=<strong-secret>`
- `DATABASE_URL=postgres://...`
- `DJANGO_ALLOWED_HOSTS=.example.com,example.com`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://example.com,https://*.example.com`
- `DJANGO_CORS_ALLOWED_ORIGINS=https://example.com`
- `DJANGO_SESSION_COOKIE_SECURE=True`
- `DJANGO_CSRF_COOKIE_SECURE=True`
- `DJANGO_SESSION_COOKIE_DOMAIN=.example.com`
- `DJANGO_CSRF_COOKIE_DOMAIN=.example.com`
- `DJANGO_SESSION_COOKIE_SAMESITE=Lax`
- `DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`
- `DJANGO_EMAIL_HOST=<provider-host>`
- `DJANGO_EMAIL_PORT=587`
- `DJANGO_EMAIL_HOST_USER=<provider-user>`
- `DJANGO_EMAIL_HOST_PASSWORD=<provider-password>`
- `DJANGO_EMAIL_USE_TLS=True`
- `DJANGO_DEFAULT_FROM_EMAIL=noreply@example.com`
- `DJANGO_SECURITY_LOG_FILE=/var/log/resto/security.log`

Set in frontend `.env.production`:
- `VITE_API_BASE_URL=auto`
- `VITE_ADMIN_API_BASE_URL=auto`

## 5. Systemd Services
Create backend service `resto-backend.service`:
- Working directory: `/srv/resto/backend`
- ExecStart: `/srv/resto/backend/.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3 --timeout 60`
- EnvironmentFile: backend `.env`
- Restart: always

Enable/start:
- `sudo systemctl daemon-reload`
- `sudo systemctl enable --now resto-backend`

## 6. Nginx Configuration
Use one server block that handles root + wildcard:
- `server_name example.com *.example.com;`
- Serve frontend static build from `/srv/resto/frontend/dist`
- Proxy `/api/` and `/admin/` to `http://127.0.0.1:8000`
- Forward host headers so tenant resolution works:
  - `proxy_set_header Host $host;`
  - `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`
  - `proxy_set_header X-Forwarded-Proto $scheme;`

Enable HTTPS:
- `sudo certbot --nginx -d example.com -d '*.example.com'`

## 7. Deploy Procedure (Each Release)
1. `git fetch --all && git checkout <tag-or-commit>`
2. Backend deps update:
   - `pip install -r backend/requirements.txt`
3. Run migrations:
   - `python backend/manage.py migrate_schemas --shared`
   - `python backend/manage.py migrate_schemas --tenant`
4. Build frontend:
   - `cd frontend && npm ci && npm run build`
5. Restart services:
   - `sudo systemctl restart resto-backend`
   - `sudo systemctl reload nginx`
6. Run smoke checks:
   - `powershell -ExecutionPolicy Bypass -File .\infra\pre_release_smoke.ps1 -TenantHost demo.example.com -BackendPort 443 -FrontendPort 443 -AllowMenuLocked`
   - Or equivalent `curl` checks from server.

## 8. Rollback Procedure
1. Identify previous stable git tag.
2. Checkout previous tag:
   - `git checkout <previous-stable-tag>`
3. Reinstall backend dependencies if changed:
   - `pip install -r backend/requirements.txt`
4. Rebuild frontend:
   - `cd frontend && npm ci && npm run build`
5. Restart backend and reload Nginx.
6. Validate with smoke checks.
7. If failure is migration-related and irreversible:
   - Restore database from pre-release backup.
   - Redeploy previous stable tag.

## 9. Post-Deploy Verification
- Open tenant home (`https://demo.example.com`)
- Verify `/api/health/` returns `status: ok`
- Sign in as platform admin and open `/admin-console`
- Provision test lead and verify onboarding package links
- Complete onboarding and publish menu
- Verify published menu accessible publicly
- Check `/var/log/resto/security.log` for throttle/security entries

## 10. Incident Notes
- Keep incident log with:
  - Deploy timestamp
  - Commit/tag
  - Operator
  - Smoke test result
  - Rollback steps taken (if any)
