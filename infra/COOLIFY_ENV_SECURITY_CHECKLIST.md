# Coolify Env Security Checklist

Use this before every production deploy.

## 1. Source of truth
- Keep `coolify.env.example` and `coolify.env.production.sample` as templates only.
- Never store real secrets in git.
- Store real production values only in Coolify Environment Variables.

## 2. Secret quality
- `DJANGO_SECRET_KEY`: long random value (64+ chars).
- `POSTGRES_PASSWORD`: long random value (20+ chars).
- `DJANGO_SUPERADMIN_PASSWORD`: strong random value.
- Rotate any secret that was ever shown in screenshots/chat.

## 3. Production safety flags
- `DJANGO_DEBUG=False`
- `DJANGO_SESSION_COOKIE_SECURE=True`
- `DJANGO_CSRF_COOKIE_SECURE=True`
- `DJANGO_SESSION_COOKIE_DOMAIN=.yourdomain.com`
- `DJANGO_CSRF_COOKIE_DOMAIN=.yourdomain.com`
- `DJANGO_USE_X_FORWARDED_HOST=True`
- `DJANGO_SECURE_PROXY_SSL_HEADER=True`

## 4. Domain and routing correctness
- `DJANGO_ALLOWED_HOSTS` includes root, admin, api, and wildcard subdomain.
- `DJANGO_CSRF_TRUSTED_ORIGINS` includes root/admin and wildcard https subdomains.
- `DJANGO_CORS_ALLOWED_ORIGINS` includes root/admin app origins.
- `DJANGO_PUBLIC_SCHEMA_HOSTS` includes root/admin/public hosts (and localhost only for local testing).
- `PUBLIC_MENU_BASE_URL` is your production root URL (`https://...`).
- `TENANT_DOMAIN_SUFFIX` is explicitly set to tenant wildcard base (recommended: `menu.yourdomain.com`).
- `VITE_API_BASE_URL` and `VITE_ADMIN_API_BASE_URL` point to the production API.
- `VITE_PLATFORM_PUBLIC_HOSTS` lists platform domains (root/admin/api).

## 5. Email and monitoring
- Use real SMTP provider in production:
  - `DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`
  - `DJANGO_EMAIL_HOST`
  - `DJANGO_EMAIL_PORT`
  - `DJANGO_EMAIL_HOST_USER`
  - `DJANGO_EMAIL_HOST_PASSWORD`
  - `DJANGO_EMAIL_USE_TLS` or `DJANGO_EMAIL_USE_SSL` (not both `True`)
  - `DJANGO_EMAIL_FAIL_SILENTLY=False`
- Set Sentry DSNs when ready:
  - `DJANGO_SENTRY_DSN`
  - `VITE_SENTRY_DSN`
- Verify delivery from app runtime:
  - `bash infra/coolify/check_email_dns.sh --domain yourdomain.com --dkim-selector <selector1> --dkim-selector <selector2>`
  - `python backend/manage.py check_email_delivery --expect-smtp --expect-no-fail-silently --send-test --to ops@yourdomain.com`
  - `python backend/manage.py email_delivery_drill --to ops@yourdomain.com --base-url menu.yourdomain.com`
  - `bash infra/coolify/verify_email_delivery.sh --resource-uuid <RESOURCE_UUID> --to ops@yourdomain.com --base-url menu.yourdomain.com`
- Verify auth throttle security monitoring:
  - `bash infra/coolify/verify_throttle_alerts.sh --resource-uuid <RESOURCE_UUID> --login-url api.yourdomain.com --attempts 12`

## 6. Media storage mode
- Keep `DJANGO_MEDIA_STORAGE_BACKEND=local` for simple disk-backed uploads (Docker volume).
- If using object storage, set `DJANGO_MEDIA_STORAGE_BACKEND=s3` and provide:
  - `AWS_STORAGE_BUCKET_NAME`
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
- Add one of:
  - `AWS_S3_CUSTOM_DOMAIN` (CDN/custom host), or
  - `AWS_S3_ENDPOINT_URL` (S3-compatible vendor), or
  - `AWS_S3_REGION_NAME` (AWS host pattern).
- Set signed URL expiry:
  - `AWS_QUERYSTRING_EXPIRE=900` (or your preferred TTL seconds).
- Apply lifecycle policy:
  - `infra/coolify/s3_media_lifecycle_policy.example.json`

## 7. Validate before saving in Coolify
- Run local validator:
  - `powershell -ExecutionPolicy Bypass -File .\infra\validate_coolify_env.ps1 -EnvFile .\coolify.env.example`
- For real production export file:
  - `powershell -ExecutionPolicy Bypass -File .\infra\validate_coolify_env.ps1 -EnvFile .\your-prod-vars.env -ExpectProductionValues`

## 8. After clicking Save
- Redeploy.
- Verify health endpoints:
  - `https://yourdomain.com/health`
  - `https://admin.yourdomain.com/health`
  - `https://api.yourdomain.com/api/health/`
- Verify login + tenant menu load from a fresh browser/private window.
