# Launch Checklist

> Complete before going live. All code changes are already committed to `main`.
> Coolify does NOT auto-deploy on push — trigger manually each time.

---

## 1 — Trigger the deploy in Coolify
Coolify dashboard → your project → **Deploy**

---

## 2 — Set environment variables in Coolify
Go to **Coolify → your service → Environment Variables** and add/update:

| Variable | Value |
|---|---|
| `DJANGO_SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(50))"` |
| `DJANGO_ADMIN_URL` | Something unguessable, e.g. `internal-mgmt-abc123/` |
| `DJANGO_SECURE_HSTS_SECONDS` | `3600` for first week → bump to `31536000` after confirming HTTPS is stable |
| `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` | `True` |
| `DJANGO_EMAIL_HOST` | Your SMTP host (e.g. `smtp.sendgrid.net`) |
| `DJANGO_EMAIL_PORT` | `587` |
| `DJANGO_EMAIL_USE_TLS` | `True` |
| `DJANGO_EMAIL_HOST_USER` | Your SMTP username |
| `DJANGO_EMAIL_HOST_PASSWORD` | Your SMTP password |
| `DJANGO_DEFAULT_FROM_EMAIL` | `noreply@yourdomain.com` |
| `DJANGO_SENTRY_DSN` | From sentry.io (create a Django project if not done) |
| `OPENROUTER_API_KEY` | Optional — only needed for the AI translation feature |

---

## 3 — Update `nginx.conf` to match your new admin URL
If you set `DJANGO_ADMIN_URL=internal-mgmt-abc123/`, also update
`frontend/nginx.conf`:

```nginx
# Change this block's location to match:
location ^~ /internal-mgmt-abc123/ {
  proxy_pass http://api:8000;
  ...
}
```

Then redeploy.

---

## 4 — Run the superadmin setup command (first deploy only)
```bash
# Coolify → api service → Terminal, or via docker exec
python manage.py ensure_platform_admin \
  --email your@email.com \
  --password "a-strong-password-here"
```

---

## 5 — Seed the plans (if not already done)
```bash
python manage.py seed_plans
```

---

## 6 — Verify security headers
Test with https://securityheaders.com — paste your domain.
Expected green ratings:
- `Content-Security-Policy`
- `X-Frame-Options`
- `X-Content-Type-Options`
- `Referrer-Policy`
- `Permissions-Policy`
- `Strict-Transport-Security`

---

## 7 — Complete Arabic translations (deferred)
The spawned task chip fills in the 33 missing AR sections.
App falls back to English gracefully in the meantime.

---

## 8 — Monitor first 24 hours after launch
- Check **Sentry** for runtime errors
- Check **Coolify logs** for Django startup warnings
- Verify OTP emails arrive (test phone/email sign-in flows)
- Place a test order through the marketplace
- Test the owner dashboard on mobile
