# Coolify Uptime Monitoring (Host Script + Webhook Alerts)

This guide adds lightweight uptime checks for:

- `https://kepoli.com/health`
- `https://admin.kepoli.com/health`
- `https://api.kepoli.com/api/health/`

Scripts:

- `infra/coolify/uptime_probe.sh`
- `infra/coolify/install_uptime_cron.sh`
- `infra/coolify/verify_uptime_alerts.sh`

## 1. Prepare on VPS host

```bash
cd /opt/resto
chmod +x infra/coolify/uptime_probe.sh
chmod +x infra/coolify/install_uptime_cron.sh
chmod +x infra/coolify/verify_uptime_alerts.sh
```

## 2. Run manual probe

```bash
./infra/coolify/uptime_probe.sh \
  --check "https://kepoli.com/health|200" \
  --check "https://admin.kepoli.com/health|200" \
  --check "https://api.kepoli.com/api/health/|200"
```

Expected:

- Exit code `0` when all checks pass.
- Exit code `1` if any endpoint fails.

## 3. Optional webhook alerts

Set webhook URL (Slack/Discord/custom endpoint):

```bash
export UPTIME_ALERT_WEBHOOK="https://example-webhook-url"
```

Then run:

```bash
./infra/coolify/uptime_probe.sh \
  --check "https://kepoli.com/health|200" \
  --check "https://admin.kepoli.com/health|200" \
  --check "https://api.kepoli.com/api/health/|200" \
  --cooldown-minutes 20
```

Notes:

- Repeated down alerts are throttled by cooldown.
- Recovery event is sent once when checks return to normal.

## 4. Install recurring cron job (recommended)

Install default 5-minute cron with Kepoli checks:

```bash
sudo /bin/bash /opt/resto/infra/coolify/install_uptime_cron.sh
```

Install with webhook:

```bash
sudo /bin/bash /opt/resto/infra/coolify/install_uptime_cron.sh \
  --webhook-url "https://example-webhook-url"
```

Verify:

```bash
crontab -l | grep resto_uptime_probe
```

Remove job:

```bash
sudo /bin/bash /opt/resto/infra/coolify/install_uptime_cron.sh --remove
```

## 5. Verify down/recovered webhook alerts

Run the dedicated drill script (safe temp state file):

```bash
sudo /bin/bash /opt/resto/infra/coolify/verify_uptime_alerts.sh \
  --webhook-url "https://example-webhook-url"
```

Dry-run without webhook delivery:

```bash
sudo /bin/bash /opt/resto/infra/coolify/verify_uptime_alerts.sh --dry-run
```

Expected:

1. First probe fails and emits `uptime_down`.
2. Second probe passes and emits `uptime_recovered`.
3. Your webhook destination receives both events (unless dry-run).
