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

Recommended pattern (so other apps can run on the same root domain):

- Tenant namespace on a subdomain zone:
  - frontend base: `menu.kepoli.com`
  - tenant wildcard: `*.menu.kepoli.com`
  - admin app: `admin.menu.kepoli.com`

Important:

- In this Coolify version, Docker Compose domain fields must be entered as full URLs.
- Include scheme and internal service port, for example `https://menu.kepoli.com:3000`.
- A bare hostname like `menu.kepoli.com` can be misparsed as a path prefix, producing `Host(\`\`) && PathPrefix(...)` errors.

The frontend/admin Nginx now proxies these paths internally to Django:

- `/api/`
- `/api-auth/`
- `/admin/`
- `/media/`
- `/static/`

That means Coolify only needs host-based routing, not path-based `/api` rules.

Important:

- tenant requests still reach Django with the original host preserved
- `slug.kepoli.com/api/...` arrives at Django as `Host: slug.kepoli.com`
- this is required because tenant resolution is host-based

## Exact Coolify UI Setup

### Frontend service

Enter in `Domains for frontend`:

- `https://menu.kepoli.com:3000`

### Admin service

Enter in `Domains for admin`:

- `https://admin.menu.kepoli.com:3000`

### API service

Leave `Domains for api` empty.

The frontend/admin Nginx already proxies:

- `/api/`
- `/api-auth/`
- `/admin/`
- `/media/`
- `/static/`

So a public API hostname is not needed for the recommended production setup.

Do not add the tenant wildcard to the Coolify app domain field on this stack.

Use a separate server-level Traefik dynamic configuration for `*.menu.kepoli.com` instead:

- [infra/COOLIFY_TENANT_WILDCARD_PROXY.md](infra/COOLIFY_TENANT_WILDCARD_PROXY.md)
- [infra/coolify/traefik-kepoli-tenant-wildcard.yml](infra/coolify/traefik-kepoli-tenant-wildcard.yml)

## DNS

At Hostinger:

- `A` record for `menu` -> VPS IP
- `A` record for `admin.menu` -> VPS IP
- `A` record for `*.menu` -> VPS IP
- keep `@` and other app subdomains free for other projects

## Environment variables

Copy values from `coolify.env.example` and replace secrets.

Set:

- `PUBLIC_MENU_BASE_URL=https://menu.kepoli.com`
- `TENANT_DOMAIN_SUFFIX=menu.kepoli.com`
- `DJANGO_PUBLIC_SCHEMA_HOSTS=menu.kepoli.com,admin.menu.kepoli.com,localhost,127.0.0.1`
- `DJANGO_ALLOWED_HOSTS=menu.kepoli.com,admin.menu.kepoli.com,.menu.kepoli.com,localhost,127.0.0.1`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://menu.kepoli.com,https://admin.menu.kepoli.com,https://*.menu.kepoli.com`
- `DJANGO_CORS_ALLOWED_ORIGINS=https://menu.kepoli.com,https://admin.menu.kepoli.com`
- `DJANGO_SESSION_COOKIE_DOMAIN=.menu.kepoli.com`
- `DJANGO_CSRF_COOKIE_DOMAIN=.menu.kepoli.com`
- `VITE_API_BASE_URL=auto`
- `VITE_ADMIN_API_BASE_URL=auto`
- `VITE_PLATFORM_PUBLIC_HOSTS=menu.kepoli.com,admin.menu.kepoli.com`

### Transactional email (activation + password reset)

Use SMTP backend in production and set all related keys:

- `DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`
- `DJANGO_EMAIL_HOST`
- `DJANGO_EMAIL_PORT`
- `DJANGO_EMAIL_HOST_USER`
- `DJANGO_EMAIL_HOST_PASSWORD`
- `DJANGO_EMAIL_USE_TLS` or `DJANGO_EMAIL_USE_SSL` (not both `True`)
- `DJANGO_DEFAULT_FROM_EMAIL`
- `DJANGO_SERVER_EMAIL`
- `DJANGO_EMAIL_FAIL_SILENTLY=False`

Verify after deploy:

- `bash infra/coolify/check_email_dns.sh --domain kepoli.com --dkim-selector <selector1> --dkim-selector <selector2>`
- `python manage.py check_email_delivery --expect-smtp --expect-no-fail-silently`
- `python manage.py check_email_delivery --expect-smtp --expect-no-fail-silently --send-test --to you@yourdomain.com`
- `python manage.py email_delivery_drill --to you@yourdomain.com --base-url menu.kepoli.com`
- VPS shortcut: `bash infra/coolify/verify_email_delivery.sh --resource-uuid <RESOURCE_UUID> --to you@yourdomain.com --base-url menu.kepoli.com`

### Optional: S3-Compatible media storage

Default is local disk (`DJANGO_MEDIA_STORAGE_BACKEND=local`) using the `media_data` Docker volume.

To switch uploads to object storage:

1. Set `DJANGO_MEDIA_STORAGE_BACKEND=s3`
2. Fill at minimum:
   - `AWS_STORAGE_BUCKET_NAME`
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
3. Set either:
   - `AWS_S3_CUSTOM_DOMAIN` (recommended when behind CDN), or
   - `AWS_S3_ENDPOINT_URL` (for S3-compatible providers), or
   - `AWS_S3_REGION_NAME` (AWS default host pattern)
4. Optional tuning:
   - `AWS_MEDIA_LOCATION=media`
   - `AWS_QUERYSTRING_AUTH=True|False`
   - `AWS_QUERYSTRING_EXPIRE=900`
   - `AWS_S3_OBJECT_CACHE_CONTROL=public, max-age=31536000`
   - Apply bucket lifecycle policy template: `infra/coolify/s3_media_lifecycle_policy.example.json`

Before deploy, validate env:

- `powershell -ExecutionPolicy Bypass -File .\infra\validate_coolify_env.ps1 -EnvFile .\coolify.env.example`

### Logging defaults (recommended)

- `DJANGO_LOG_FORMAT=json`
- `DJANGO_REQUEST_LOG_LEVEL=INFO`
- `DJANGO_PROVISIONING_LOG_LEVEL=INFO`
- `DJANGO_SECURITY_LOG_LEVEL=WARNING`
- `ADMIN_AUDIT_RETENTION_DAYS=180`

This enables structured JSON logs for request traces and provisioning actions, which makes Coolify log streams easier to ship to monitoring tools.

For audit-log retention, run periodically (for example daily via Coolify scheduled task):

- `python manage.py prune_admin_audit_logs --days 180`

### Sentry (optional but recommended)

- Backend:
  - `DJANGO_SENTRY_DSN`
  - `DJANGO_SENTRY_ENVIRONMENT` (for example `production`)
  - `DJANGO_SENTRY_RELEASE` (for example commit SHA)
  - `DJANGO_SENTRY_TRACES_SAMPLE_RATE` (start with `0`)
  - `DJANGO_SENTRY_SEND_PII` (`False` by default)
  - `DJANGO_SENTRY_CAPTURE_THROTTLE` (`False` by default; captures security throttle events)
  - `DJANGO_SENTRY_THROTTLE_MIN_WAIT_SECONDS` (`30` by default; ignore low-wait noise)
- Frontend:
  - `VITE_SENTRY_DSN`
  - `VITE_SENTRY_ENVIRONMENT`
  - `VITE_SENTRY_RELEASE`
  - `VITE_SENTRY_TRACES_SAMPLE_RATE` (start with `0`)

Sentry remains disabled until DSN values are provided.

### Verify auth throttle security monitoring

Run after each production deploy:

- `bash infra/coolify/verify_throttle_alerts.sh --resource-uuid <RESOURCE_UUID> --login-url https://admin.menu.kepoli.com/api/login/ --attempts 12`

This confirms:
- login throttling returns `429`
- API logs include `throttle.blocked` events
- Sentry throttle flags are visible in runtime env

## Notes

- The current `/platform` stack is a placeholder scaffold. Do not use it for the live product.
- This real stack serves the actual app under `frontend/` and `backend/`.
- Add wildcard DNS for your tenant namespace before tenant onboarding (for example `*.menu.kepoli.com`).
- Apply the wildcard tenant router through Coolify Server -> Proxy -> Dynamic Configurations rather than the app domain field.
- Set `VITE_API_BASE_URL=auto` and `VITE_ADMIN_API_BASE_URL=auto` so frontend uses same-host `/api`.
- Set `DJANGO_PUBLIC_SCHEMA_HOSTS` to your non-tenant hosts, for example `kepoli.com,admin.kepoli.com,localhost,127.0.0.1`.
- If using namespace domains, use values like `menu.kepoli.com,admin.menu.kepoli.com,localhost,127.0.0.1`.
- Set `TENANT_DOMAIN_SUFFIX` explicitly (for example `menu.kepoli.com`) to avoid accidental provisioning on the wrong domain.
- If you switch an existing Coolify resource from the placeholder stack to this real stack, the old `postgres_data` volume may keep previous credentials. In that case, either reuse the original database password or delete the old Postgres volume and redeploy before first production launch.
- Database backup + restore drill: `infra/COOLIFY_DB_BACKUP_RUNBOOK.md`.
- Uptime monitoring + webhook alerts: `infra/COOLIFY_UPTIME_MONITORING.md`.

## Future Update Deployments

After the first correct production setup, the normal update flow should be:

1. Push code to `main`
2. Open Coolify resource
3. Redeploy
4. Run smoke checks

You should not need to touch:

- DNS
- Coolify domain entries
- wildcard routing
- host-based tenant setup

unless you introduce a new public hostname or change the deployment topology.

## Why Coolify blocked `*.kepoli.com`

Coolify treats wildcard domains as exclusive ownership on that DNS zone.  
If one resource owns `*.kepoli.com`, another resource cannot claim `anything.kepoli.com`.

Use a tenant namespace wildcard instead (`*.menu.kepoli.com`) so you can deploy other apps on:

- `kepoli.com`
- `admin.kepoli.com`
- `blog.kepoli.com`

## Troubleshooting: `Host(\`\`) && PathPrefix(...)` in Traefik logs

This means Coolify parsed an invalid domain entry.

Fix:

1. In each `Domains for ...` field, use full URL values with the service port, for example `https://menu.kepoli.com:3000`.
2. Avoid blank items and malformed commas in comma-separated values.
3. Click `Save`, then `Redeploy`.

## Troubleshooting: wildcard entry rejected by Traefik / ACME

If you see errors such as:

- `HostSNI('*.menu.kepoli.com') is not a valid hostname`
- `Unable to obtain ACME certificate for domains ["*.menu.kepoli.com"]`

that means the wildcard was added to the normal app domain field.

Fix:

1. Remove `https://*.menu.kepoli.com:3000` from `Domains for frontend`.
2. Keep only:
   - `https://menu.kepoli.com:3000`
   - `https://admin.menu.kepoli.com:3000`
3. Save and redeploy the resource.
4. Configure the wildcard at the server proxy layer using:
   - [infra/COOLIFY_TENANT_WILDCARD_PROXY.md](infra/COOLIFY_TENANT_WILDCARD_PROXY.md)
