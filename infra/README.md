# Infra notes

## Local tenant host bootstrap
- Script: `infra/bootstrap-local-tenants.ps1`
- Dry run:
  - `powershell -ExecutionPolicy Bypass -File .\infra\bootstrap-local-tenants.ps1 -TenantSlugs demo,dede`
- Apply missing hosts entries (Administrator shell required):
  - `powershell -ExecutionPolicy Bypass -File .\infra\bootstrap-local-tenants.ps1 -TenantSlugs demo,dede -Apply`

## Pre-release smoke checks
- Script: `infra/pre_release_smoke.ps1`
- Local example:
  - `powershell -ExecutionPolicy Bypass -File .\infra\pre_release_smoke.ps1 -TenantHost demo.localhost -BackendScheme http -FrontendScheme http -BackendPort 8000 -FrontendPort 5173`
- Production example:
  - `powershell -ExecutionPolicy Bypass -File .\infra\pre_release_smoke.ps1 -TenantHost demo.example.com -BackendScheme https -FrontendScheme https -BackendPort 443 -FrontendPort 443 -AllowMenuLocked`

## Customer-flow regression smoke
- Script: `infra/customer_flow_smoke.ps1`
- Verifies core customer routes and table-context carryover into order handoff:
  - `/menu`, `/browse`, `/cart`, `/reserve`, `/t/<tableSlug>`
  - `/api/table-context/<tableSlug>/`
  - `/api/order-handoff/` with `table_slug`
- Local example:
  - `powershell -ExecutionPolicy Bypass -File .\infra\customer_flow_smoke.ps1 -TenantHost demo.localhost -ApiPort 8000 -WebPort 5173 -TableSlug table-1`
- Production example:
  - `powershell -ExecutionPolicy Bypass -File .\infra\customer_flow_smoke.ps1 -FrontendBaseUrl https://demo.kepoli.com -ApiBaseUrl https://demo.kepoli.com/api -TableSlug table-1`

## Production tenant smoke wrapper
- Script: `infra/production_tenant_smoke.ps1`
- Purpose:
  - checks public/admin/tenant health
  - runs tenant pre-release smoke
  - runs customer-flow smoke
- Dry run example:
  - `powershell -ExecutionPolicy Bypass -File .\infra\production_tenant_smoke.ps1 -TenantSlug smoke-20260310 -BaseDomain kepoli.com -TableSlug table-1 -DryRun`
- Live example:
  - `powershell -ExecutionPolicy Bypass -File .\infra\production_tenant_smoke.ps1 -TenantSlug smoke-20260310 -BaseDomain kepoli.com -TableSlug table-1`

## Browser E2E (Critical + mobile regression)
- Prepare deterministic E2E admin + demo seed:
  - Windows: `powershell -ExecutionPolicy Bypass -File .\infra\prepare_e2e.ps1`
  - Linux/macOS: `bash ./infra/prepare_e2e.sh`
  - Script also ensures demo owner credentials: `test_resto_user@demo.local / admin123`
  - If backend is already running, restart it after preparation so throttle cache is reset in the live process.
- Start local app stack:
  - `powershell -ExecutionPolicy Bypass -File .\infra\run_local.ps1 -TenantHost demo.localhost -ApiPort 8000 -WebPort 5173`
- Run Playwright suite:
  - `cd frontend`
  - `npm run e2e:install` (first run only)
  - `npm run e2e:critical`
  - `npm run e2e:mobile`
  - `npm run e2e`
- Optional env overrides for test execution:
  - `E2E_FRONTEND_URL` (default: `http://demo.localhost:5173`)
  - `E2E_PUBLIC_FRONTEND_URL` (default: `http://localhost:5173`)
  - `E2E_API_URL` (default: `http://demo.localhost:8000`)
  - `E2E_ADMIN_EMAIL` (default: `e2e-admin@example.com`)
  - `E2E_ADMIN_PASSWORD` (default: `E2E_Admin_123!`)
  - `E2E_OWNER_EMAIL` (default: `test_resto_user@demo.local`)
  - `E2E_OWNER_PASSWORD` (default: `admin123`)

## Deployment runbook
- See: `infra/DEPLOYMENT_RUNBOOK.md`
- Env separation strategy: `infra/COOLIFY_ENV_SEPARATION.md`
- Env hardening checklist: `infra/COOLIFY_ENV_SECURITY_CHECKLIST.md`
- Env validator (Windows): `powershell -ExecutionPolicy Bypass -File .\infra\validate_coolify_env.ps1 -EnvFile .\coolify.env.example`
  - If `DJANGO_MEDIA_STORAGE_BACKEND=s3`, validator enforces required object-storage keys.
  - If SMTP backend is selected, validator enforces host/port/TLS-SSL rules.

## API contract export (OpenAPI)
- Windows:
  - `powershell -ExecutionPolicy Bypass -File .\infra\export_openapi.ps1`
- Linux/macOS:
  - `bash ./infra/export_openapi.sh`
- Default output: `backend/openapi.json`
- CI also exports and uploads `openapi.json` as workflow artifact `openapi-schema`.

## Coolify DB backup/restore
- Runbook: `infra/COOLIFY_DB_BACKUP_RUNBOOK.md`
- Scripts:
  - `infra/coolify/backup_postgres.sh`
  - `infra/coolify/restore_postgres.sh`

## Coolify full-stack backup + wildcard verification
- Runbook: `infra/COOLIFY_FULL_STACK_BACKUP.md`
- Scripts:
  - `infra/coolify/backup_full_stack.sh`
  - `infra/coolify/check_live_wildcard.sh`

## Coolify email verification
- Runbook: `infra/COOLIFY_EMAIL_VERIFICATION.md`
- DNS deliverability check: `infra/COOLIFY_EMAIL_DNS_CHECK.md`
- Script:
  - `infra/coolify/check_email_dns.sh`
  - `infra/coolify/verify_email_delivery.sh`

## Coolify uptime monitoring
- Runbook: `infra/COOLIFY_UPTIME_MONITORING.md`
- Scripts:
  - `infra/coolify/uptime_probe.sh`
  - `infra/coolify/install_uptime_cron.sh`
  - `infra/coolify/verify_uptime_alerts.sh`

## Coolify throttle security verification
- Runbook: `infra/COOLIFY_THROTTLE_ALERT_VERIFICATION.md`
- Script:
  - `infra/coolify/verify_throttle_alerts.sh`

## Coolify tenant wildcard proxy
- Runbook: `infra/COOLIFY_TENANT_WILDCARD_PROXY.md`
- Dynamic config:
  - `infra/coolify/traefik-kepoli-tenant-wildcard.yml`

## Coolify S3 media lifecycle template
- Template: `infra/coolify/s3_media_lifecycle_policy.example.json`
- Use when `DJANGO_MEDIA_STORAGE_BACKEND=s3` to set bucket retention/transition rules.
