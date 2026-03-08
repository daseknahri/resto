# Coolify Uptime Monitoring (Host Script + Webhook Alerts)

This guide adds lightweight uptime checks for:

- `https://kepoli.com/health`
- `https://admin.kepoli.com/health`
- `https://api.kepoli.com/api/health/`

Script:

- `infra/coolify/uptime_probe.sh`

## 1. Prepare on VPS host

```bash
cd /opt/resto
chmod +x infra/coolify/uptime_probe.sh
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

## 4. Schedule with cron

Every 5 minutes:

```cron
*/5 * * * * /bin/bash /opt/resto/infra/coolify/uptime_probe.sh --check "https://kepoli.com/health|200" --check "https://admin.kepoli.com/health|200" --check "https://api.kepoli.com/api/health/|200" --cooldown-minutes 20 >> /var/log/resto-uptime.log 2>&1
```

With webhook:

```cron
*/5 * * * * UPTIME_ALERT_WEBHOOK="https://example-webhook-url" /bin/bash /opt/resto/infra/coolify/uptime_probe.sh --check "https://kepoli.com/health|200" --check "https://admin.kepoli.com/health|200" --check "https://api.kepoli.com/api/health/|200" --cooldown-minutes 20 >> /var/log/resto-uptime.log 2>&1
```

## 5. Verify alert flow

1. Temporarily point one check to invalid path (`/health-bad`) and run probe.
2. Confirm webhook received a `uptime_down` event.
3. Restore valid checks and run again.
4. Confirm webhook received `uptime_recovered`.
