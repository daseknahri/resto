# Coolify Environment Separation (Dev / Staging / Production)

Use this strategy so updates are safe and repeatable.

## 1) Files and purpose
- `backend/.env.example` + `frontend/.env.example`
  - local development references
- `coolify.env.staging.sample`
  - template for staging/pre-production resource
- `coolify.env.production.sample`
  - template for production resource

All three are templates only. Never commit real secrets.

## 2) Coolify variable placement
- Production app resource:
  - set real values in **Production Environment Variables**
- Staging app resource (or preview resource):
  - set staging values in **Production Environment Variables** for that staging resource
  - or use **Preview Deployments Environment Variables** when using preview builds
- Global shared credentials (optional):
  - keep them in Coolify **Shared Variables** and reference from each resource

## 3) Domain separation
- Production:
  - `menu.yourdomain.com`, `admin.menu.yourdomain.com`, optional `api.menu.yourdomain.com`
  - wildcard tenant: `*.menu.yourdomain.com`
- Staging:
  - `staging.yourdomain.com`, `admin.staging.yourdomain.com`, optional `api.staging.yourdomain.com`
  - wildcard tenant: `*.staging.yourdomain.com`

Never let staging and production share the same tenant wildcard.

## 4) Database and Redis separation
- Use separate DB names/users per environment.
- Use separate backups per environment path/bucket.
- Do not point staging `DATABASE_URL` to production database.

## 5) Validation before save/redeploy
- Validate template or exported env file:

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\validate_coolify_env.ps1 -EnvFile .\coolify.env.staging.sample
powershell -ExecutionPolicy Bypass -File .\infra\validate_coolify_env.ps1 -EnvFile .\coolify.env.production.sample -ExpectProductionValues
```

## 6) Secrets management baseline
- Keep secrets only in Coolify variables, never in git.
- Rotate any secret that was ever exposed (chat/screenshot/terminal history).
- Use unique secrets for each environment:
  - `DJANGO_SECRET_KEY`
  - `POSTGRES_PASSWORD`
  - `DJANGO_SUPERADMIN_PASSWORD`
  - `DJANGO_EMAIL_HOST_PASSWORD`
  - Sentry DSNs if separated per environment

## 7) Promotion flow
1. Merge code to `main`.
2. Deploy to staging.
3. Run smoke/E2E + email/throttle checks on staging.
4. Promote same commit SHA to production.
5. Run production smoke + uptime + email + throttle verification scripts.
