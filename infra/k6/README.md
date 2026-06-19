# k6 Load & Stress Harness — Kepoli / Resto

## Install k6

```bash
# macOS
brew install k6

# Linux (Debian/Ubuntu)
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
     --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
     | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6

# Windows (winget)
winget install k6 --source winget

# Docker (no install needed)
docker run --rm -i grafana/k6 run - < infra/k6/load.js
```

## Quick Start

```bash
# Smoke test against local dev (starts uvicorn first in another terminal)
k6 run infra/k6/load.js

# Full ramp against a staging server
BASE_URL=https://staging.kepoli.com \
TENANT_URL=https://demo.staging.kepoli.com \
MENU_SLUG=demo-resto \
VUS_RAMP=100 \
SOAK_DURATION=30m \
k6 run infra/k6/load.js

# Smoke only (bypass ramp + soak)
k6 run --duration 2m --vus 2 infra/k6/load.js
```

## Scenarios

| Scenario | VUs | Duration | Purpose |
|----------|-----|----------|---------|
| `smoke`  | 2   | 2 min    | Confirm all routes return 200; catch obvious breakage |
| `ramp`   | 0 → `VUS_RAMP` → 0 | ~11 min | Find saturation: p95 latency, error rate, CPU, DB pool |
| `soak`   | `VUS_SOAK` | `SOAK_DURATION` | Memory leaks, connection exhaustion, cache drift |

Run order: smoke → ramp → soak (sequential in one `k6 run`).

## Environment Variables

| Variable        | Default                    | Description |
|----------------|----------------------------|-------------|
| `BASE_URL`     | `http://localhost:8000`    | Public/marketplace origin |
| `TENANT_URL`   | `BASE_URL`                 | One tenant subdomain (e.g. `https://demo.kepoli.com`) |
| `MENU_SLUG`    | `demo`                     | Restaurant slug for `/api/marketplace/menu/<slug>/` |
| `VUS_RAMP`     | `50`                       | Peak VU count for the ramp scenario |
| `VUS_SOAK`     | `20`                       | Constant VUs for the soak scenario |
| `SOAK_DURATION`| `10m`                      | k6 duration string; use `60m` for overnight soak |

## Traffic Mix

The default VU loop mirrors realistic traffic:

| Group | Weight | Endpoints |
|-------|--------|-----------|
| Health | 15 % | `GET /api/health/` |
| Marketplace browse | 35 % | `GET /api/marketplace/` → `GET /api/marketplace/menu/<slug>/` |
| Directory browse | 15 % | `GET /api/directory/` |
| Tenant menu load | 35 % | `GET /api/meta/` → `/api/categories/` → `/api/dishes/` |

## Thresholds

k6 exits non-zero if any threshold is breached:

| Metric | Threshold |
|--------|-----------|
| HTTP error rate | < 1 % |
| Overall p95 | < 2 s |
| `health` p95 | < 200 ms |
| `meta` p95 | < 500 ms |
| `categories` / `dishes` p95 | < 800 ms / 1 000 ms |
| `marketplace` / `directory` / `mkt_menu` p95 | < 1 500 ms |

## Reading the Output

```
✓ GET /api/health/ → 200
✓ GET /api/marketplace/ → 200
...
http_req_duration............: avg=120ms  min=42ms  med=89ms  max=3s    p(90)=290ms p(95)=450ms
http_req_failed..............: 0.00%
```

Key numbers to watch:
- **p95 per route** (tagged columns) — the per-SLO signal; spikes here map to a specific backend
- **http_req_failed** — any non-zero value during ramp suggests connection pool exhaustion or OOM
- **iteration_duration** — if this grows monotonically during soak, you have a leak

## What to Scale When

| Symptom | Likely cause | Lever |
|---------|-------------|-------|
| `dishes` / `categories` p95 spikes, `health` stays fast | Django worker saturation | Add Gunicorn workers (`WEB_CONCURRENCY`) |
| All routes degrade together | DB connection pool exhausted | Tune PgBouncer `pool_size`; reduce `CONN_MAX_AGE` |
| Latency grows during soak but recovers on restart | Memory / connection leak in long-lived threads | Check `_inline_executor` thread pool; upgrade to Celery |
| `marketplace` slow, `health` fast | Cache cold or Redis bottleneck | Verify `REDIS_URL` is set; check `CACHE_TTL` |
| Error rate > 0 only at peak VUs | Request queue overflow | Add `--timeout` to Gunicorn or raise `ulimit -n` |

## CI Integration

```yaml
# .github/workflows/load.yml  (run weekly or on release tags)
jobs:
  load:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run k6 smoke
        uses: grafana/k6-action@v0.3.1
        with:
          filename: infra/k6/load.js
        env:
          BASE_URL: ${{ secrets.STAGING_URL }}
          TENANT_URL: ${{ secrets.STAGING_TENANT_URL }}
          MENU_SLUG: ${{ secrets.STAGING_MENU_SLUG }}
          VUS_RAMP: "30"
          SOAK_DURATION: "5m"
```
