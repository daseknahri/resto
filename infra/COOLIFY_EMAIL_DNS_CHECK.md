# Coolify Email DNS Deliverability Check

Verify sender-domain authentication before production traffic.

## Why this matters

SMTP credentials alone are not enough.  
Mailbox providers score your domain using:
- SPF
- DKIM
- DMARC

Missing or broken records reduce inbox placement.

## Script

- `infra/coolify/check_email_dns.sh`
- Requires `dig` or `nslookup` on VPS host (`dnsutils`/`bind-tools` package).

## Basic usage

From VPS host:

```bash
bash infra/coolify/check_email_dns.sh --domain kepoli.com
```

This checks:
- exactly one SPF record (`v=spf1`) at root domain
- DMARC record (`v=DMARC1`) at `_dmarc.<domain>`

## DKIM checks

Use selectors provided by your SMTP provider:

```bash
bash infra/coolify/check_email_dns.sh \
  --domain kepoli.com \
  --dkim-selector s1 \
  --dkim-selector s2
```

If any provided selector has no `v=DKIM1` TXT, script exits non-zero.

## JSON output (automation)

```bash
bash infra/coolify/check_email_dns.sh --domain kepoli.com --json
```

## Typical provider notes

- SendGrid: usually 2 DKIM selectors (`s1`, `s2`).
- Amazon SES: typically 3 selector CNAME/TXT entries (names are generated per domain).
- Mailgun: selector depends on domain setup shown in provider dashboard.

Always copy exact selector names from provider dashboard.

## Recommended workflow

1. Configure DNS records in Hostinger.
2. Run DNS check script until all required records pass.
3. Run SMTP runtime checks:
   - `bash infra/coolify/verify_email_delivery.sh --resource-uuid <RESOURCE_UUID> --to ops@yourdomain.com --base-url menu.yourdomain.com`
4. Send a real owner-flow drill email and confirm inbox delivery.
