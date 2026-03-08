# Real App Coolify Deployment

Use this stack to deploy the actual Django + Vue restaurant SaaS.

## What it deploys

- `frontend`: the real Vue application for customer browsing and public landing
- `admin`: the same Vue build on a separate domain for owner/admin access
- `api`: the real Django API
- `postgres`: production database
- `redis`: cache / future queue support

## Coolify configuration

- Repository: `daseknahri/resto`
- Branch: `main`
- Build Pack: `Docker Compose`
- Base Directory: `/`
- Docker Compose Location: `/docker-compose.coolify.yml`

## Domains

- `Domains for frontend`: `https://kepoli.com:3000`
- `Domains for admin`: `https://admin.kepoli.com:3000`
- `Domains for api`: `https://api.kepoli.com:8000`

## Environment variables

Copy values from `coolify.env.example` and replace secrets.

### Logging defaults (recommended)

- `DJANGO_LOG_FORMAT=json`
- `DJANGO_REQUEST_LOG_LEVEL=INFO`
- `DJANGO_PROVISIONING_LOG_LEVEL=INFO`
- `DJANGO_SECURITY_LOG_LEVEL=WARNING`

This enables structured JSON logs for request traces and provisioning actions, which makes Coolify log streams easier to ship to monitoring tools.

## Notes

- The current `/platform` stack is a placeholder scaffold. Do not use it for the live product.
- This real stack serves the actual app under `frontend/` and `backend/`.
- Add wildcard DNS `*.kepoli.com` later when tenant subdomains are enabled in production.
- If you switch an existing Coolify resource from the placeholder stack to this real stack, the old `postgres_data` volume may keep previous credentials. In that case, either reuse the original database password or delete the old Postgres volume and redeploy before first production launch.
- Database backup + restore drill: `infra/COOLIFY_DB_BACKUP_RUNBOOK.md`.
