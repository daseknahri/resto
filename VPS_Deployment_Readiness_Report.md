# VPS Deployment Readiness Report
## Snapshot
- Date: 2026-03-07
- Project: Restaurant SaaS (Basic tier first)
- Target host type: Hostinger VPS (Ubuntu/Nginx/PostgreSQL)

## Automated Validation Status
- [x] Backend tests passed (`121` tests, `0` failures, `0` skips)
  - Command used: `cd backend && .\.venv\Scripts\python.exe manage.py test tests -v 2`
- [x] Frontend production build passed
  - Command used: `cd frontend && npm run build`
- [x] Pre-release smoke checks passed
  - Command used: `powershell -ExecutionPolicy Bypass -File .\infra\pre_release_smoke.ps1 -TenantHost demo.localhost -BackendScheme http -FrontendScheme http -BackendPort 8000 -FrontendPort 5173`
- [x] Customer-flow smoke checks passed
  - Command used: `powershell -ExecutionPolicy Bypass -File .\infra\customer_flow_smoke.ps1 -TenantHost demo.localhost -ApiPort 8000 -WebPort 5173 -TableSlug table-1`

## Readiness by Area
### Application quality
- [x] Core customer flow stable (restaurant landing -> menu browse -> cart -> reserve)
- [x] Owner workspace stable (dashboard, onboarding, tables, reservations)
- [x] Admin console stable with mobile card-mode for dense data sections

### Production deployment foundation
- [x] Deployment runbook exists: `infra/DEPLOYMENT_RUNBOOK.md`
- [x] Local run/stop scripts exist: `infra/run_local.ps1`, `infra/stop_local.ps1`
- [x] Smoke script exists and now supports PowerShell 5/7 JSON parsing compatibility

### Must-configure items before public launch
- [ ] Production DNS for root + wildcard tenant subdomains
  - `example.com` -> VPS IP
  - `*.example.com` -> VPS IP
- [ ] HTTPS certificates for root + wildcard domain
  - Recommended: Let's Encrypt DNS challenge for wildcard
- [ ] Production env values configured on VPS
  - `DJANGO_DEBUG=False`
  - `DJANGO_SECRET_KEY=<strong_random>`
  - `DATABASE_URL=postgres://...`
  - `DJANGO_ALLOWED_HOSTS=.example.com,example.com`
  - `DJANGO_CSRF_TRUSTED_ORIGINS=https://example.com,https://*.example.com`
  - `DJANGO_CORS_ALLOWED_ORIGINS=https://example.com` (and any required trusted frontend origins)
  - `DJANGO_SESSION_COOKIE_SECURE=True`
  - `DJANGO_CSRF_COOKIE_SECURE=True`
  - `DJANGO_SESSION_COOKIE_DOMAIN=.example.com`
  - `DJANGO_CSRF_COOKIE_DOMAIN=.example.com`
  - `DJANGO_SESSION_COOKIE_SAMESITE=Lax` (or `None` only if needed)
  - SMTP settings (`DJANGO_EMAIL_*`) with real provider creds
  - `DJANGO_SECURITY_LOG_FILE=/var/log/resto/security.log`
- [ ] Gunicorn + systemd service configured and enabled
- [ ] Nginx server block configured for `example.com` and `*.example.com`
- [ ] PostgreSQL backups scheduled and restore tested
- [ ] External monitoring/alerts wired (health endpoint + logs)

## Go/No-Go Assessment
- Current codebase quality: **GO for staging**
- Current infrastructure state in this local environment: **NOT GO for internet production** until all `Must-configure` items above are completed on VPS.

## Recommended Final Sequence on VPS
1. Provision DNS + wildcard SSL.
2. Deploy code and configure env.
3. Run migrations (`migrate_schemas --shared`, then `--tenant`).
4. Build frontend and restart backend/nginx services.
5. Run smoke checks on public tenant domain.
6. Run manual role-based QA from `Pre_Deployment_QA_Checklist.md`.
7. Launch.
