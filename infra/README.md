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

## Deployment runbook
- See: `infra/DEPLOYMENT_RUNBOOK.md`

## Coolify DB backup/restore
- Runbook: `infra/COOLIFY_DB_BACKUP_RUNBOOK.md`
- Scripts:
  - `infra/coolify/backup_postgres.sh`
  - `infra/coolify/restore_postgres.sh`

## Coolify uptime monitoring
- Runbook: `infra/COOLIFY_UPTIME_MONITORING.md`
- Scripts:
  - `infra/coolify/uptime_probe.sh`
  - `infra/coolify/install_uptime_cron.sh`
  - `infra/coolify/verify_uptime_alerts.sh`
