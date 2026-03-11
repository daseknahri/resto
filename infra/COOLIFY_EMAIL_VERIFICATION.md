# Coolify Email Verification Runbook

Use this after setting real SMTP environment variables in Coolify.

## Goal

Verify:
- SMTP config is valid in runtime container
- A direct test email can be sent
- Business templates (activation + password reset) are deliverable
- Sender DNS auth is configured (SPF/DKIM/DMARC)

## Prerequisites

- API container is running and healthy.
- SMTP env vars are configured in Coolify (`DJANGO_EMAIL_*`).
- You know your resource UUID (or API container name).

## One-command verification (recommended)

From VPS host:

```bash
bash infra/coolify/verify_email_delivery.sh \
  --resource-uuid <RESOURCE_UUID> \
  --to ops@yourdomain.com \
  --base-url menu.yourdomain.com
```

This runs inside the API container:
- `python manage.py check_email_delivery --expect-smtp --expect-no-fail-silently --send-test`
- `python manage.py email_delivery_drill --to ... --base-url ...`

## DNS authentication check (run first)

From VPS host:

```bash
bash infra/coolify/check_email_dns.sh --domain yourdomain.com --dkim-selector s1 --dkim-selector s2
```

For details: `infra/COOLIFY_EMAIL_DNS_CHECK.md`

## Dry-run

```bash
bash infra/coolify/verify_email_delivery.sh \
  --resource-uuid <RESOURCE_UUID> \
  --to ops@yourdomain.com \
  --base-url menu.yourdomain.com \
  --dry-run
```

## Troubleshooting

- If SMTP check fails:
  - verify `DJANGO_EMAIL_BACKEND`, host/port, TLS/SSL flags, credentials.
  - redeploy after env changes.
- If drill fails but check passes:
  - inspect mail provider suppression/spam logs.
  - verify sender domain/authentication (SPF/DKIM/DMARC).
