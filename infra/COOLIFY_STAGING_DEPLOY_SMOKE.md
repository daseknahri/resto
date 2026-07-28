# Staging deploy smoke — validating image / base-image changes before prod

> **Status: owner-run procedure.** Run this on a **Coolify staging** environment before promoting
> any Docker base-image bump (python / node / nginx) — or any Dockerfile / entrypoint / compose
> change — to production. It's the "suspenders" to CI's "belt": CI proves the images build and boot;
> this proves they deploy and serve on your **real topology**.

## Why staging, when CI already smokes the images?

The CI `docker` job (`.github/workflows/ci.yml`) builds both images and boots them through a
**synthetic single-container** smoke (backend entrypoint + `/api/health/`, nginx + `/health`). That
catches build breakage and boot breakage on the new base. It deliberately does **not** cover what
only a real deploy exercises:

| Covered by CI `docker` job | Only covered by a staging deploy |
|---|---|
| `pip install` / `npm build` on the new base | Coolify's own build + deploy pipeline |
| Backend boots (migrate → collectstatic → uvicorn) | The **full compose stack** (api + worker + beat + frontend + admin + postgres + redis) starting together |
| `/api/health/`, nginx `/health` | **Traefik wildcard routing** + TLS to `*.<domain>` |
| — | nginx → api proxy over the **real compose network** (CI stubs the `api` host with `--add-host`) |
| — | Persistent **named volumes** (media/static/postgres) + non-root UID ownership |
| — | Real env/secrets, cross-subdomain session cookies, WebSockets end-to-end |

So a base bump can pass CI and still fail in prod on, e.g., a Traefik/TLS quirk or a
volume-permission issue. This procedure closes that.

## Prerequisites

- A Coolify **staging** environment separate from prod — see
  [`COOLIFY_ENV_SEPARATION.md`](COOLIFY_ENV_SEPARATION.md). It needs its own DB, domain
  (`*.staging.<yourdomain>` or similar), and env file (from `coolify.env.production.sample`).
- The change is already merged to `main` (or on a branch Coolify can deploy) and **green in CI**
  (build + runtime-smoke `docker` job passed).

## Procedure

### 1. Deploy to staging
- In Coolify, point the **staging** resource at the branch/commit with the bump and **Redeploy**.
- Watch the **build logs**: confirm the images build on the new bases (you'll see the `FROM
  python:3.14-slim` / `node:26-alpine` / `nginx:1.31-alpine` pulls and a clean `pip install` /
  `npm run build`). A base bump that lacks a wheel or breaks the toolchain fails **here**.

### 2. Confirm the stack came up healthy
- All services report healthy in Coolify (api, frontend, worker, beat, postgres, redis).
- The api container passed its entrypoint gates (they **fail closed**, so an unhealthy api means one
  tripped): check its logs for
  `migrate_schemas … / check_schema_health / collectstatic / seed_plans / check --deploy`, then the
  `uvicorn … running` line.
- Confirm the **running versions** are what you bumped to:
  ```bash
  docker exec <api-container>      python --version     # -> Python 3.14.x
  docker exec <frontend-container> nginx -v             # -> nginx/1.31.x
  ```

### 3. Run the smoke suites against staging
Point the existing scripts at the staging domain (replace with your staging hosts):
```powershell
# Live-domain platform + tenant smoke (health, lead capture, provisioning, tenant pages)
./infra/production_tenant_smoke.ps1 -BaseDomain menu.staging.yourdomain.com `
    -PublicHost menu.staging.yourdomain.com -AdminHost admin.menu.staging.yourdomain.com

# Per-tenant flows (point -TenantHost at a seeded staging tenant)
./infra/customer_flow_smoke.ps1  -TenantHost demo.staging.yourdomain.com
./infra/order_flow_api_smoke.ps1 -TenantHost demo.staging.yourdomain.com
./infra/pre_release_smoke.ps1    -TenantHost demo.staging.yourdomain.com
```
All must pass. These exercise the real HTTP path through Traefik → nginx → uvicorn.

### 4. Base-bump-specific checks (what the generic smokes don't target)
These runtime behaviors depend on the bumped bases specifically — verify them by hand:

- **python 3.14 → Pillow:** upload a menu-item image and confirm the thumbnail/processing works
  (Pillow is the C-extension most sensitive to a Python bump).
- **python 3.14 → uvicorn WebSockets:** open a tenant order screen and confirm live order-status
  updates arrive over the WS (ASGI on the new interpreter).
- **python 3.14 → reportlab/qrcode:** generate a receipt/QR if your tenants use them.
**nginx 1.31 (runtime — the base the frontend container *runs* on):**
- **Config still parses:** the container is healthy, so nginx started — but skim its logs for any
  `[warn]`/`[emerg]` about a deprecated/changed directive (a minor nginx bump occasionally changes
  directive behaviour). `docker exec <frontend> nginx -t` should say `syntax is ok / test is successful`.
- **api proxy works for real:** this is the big one CI can't cover — CI stubbed the literal `api`
  upstream with `--add-host`, so `/api/…` was never actually proxied. On staging the `api` host
  resolves to the real backend over the compose network. Hit an API route **through** the frontend
  origin (e.g. `https://<tenant>.staging.<domain>/api/health/`) and confirm 200 from the backend, not
  a 502 — proves nginx→uvicorn proxying survived the bump.
- **WebSocket upgrade proxying:** live order updates travel WS *through* nginx. Open a tenant order
  screen and confirm updates arrive (nginx must still pass `Upgrade`/`Connection` headers — a config
  or base change that drops them silently breaks realtime while HTTP still works).
- **SPA deep-link fallback:** open a deep client-route URL directly and **refresh** it — nginx must
  serve `index.html` (SPA fallback), not a 404.
- **Static/media + caching:** `/static/` and `/media/` serve; assets carry the immutable
  `Cache-Control` headers; the security headers (CSP, X-Frame-Options, etc.) are present.
- **Still non-root:** `docker exec <frontend> id` → `uid=101`, and the `/tmp` temp/cache paths (R13)
  work (no permission errors in logs).

**node 26 (build-time only — it produces the assets nginx serves; verify the *output*):**
- **SPA loads clean:** the app renders with **no console errors** and no 404'd/garbled chunks (a
  subtly broken toolchain build shows as a blank page or missing lazy chunks, not a build failure).
- **Code-split + lazy chunks resolve:** navigate across routes so the lazily-loaded chunks (FE-3
  code-split locale catalogs, lazy Sentry) actually fetch and execute — a bad rollup/esbuild output
  can 404 a chunk only on a specific route.
- **PWA / service worker:** the `vite-plugin-pwa` service worker registers and the precache manifest
  is present (DevTools → Application → Service Workers); an offline reload still serves the shell.
- **i18n all three locales:** switch EN / FR / **AR** and confirm strings resolve and Arabic renders
  **RTL** (locale handling is baked at build time).
- **Bundle sanity:** the built bundle size is in the same ballpark as before — a major toolchain bump
  can regress minification/tree-shaking (compare Coolify build log sizes or `dist/` output).

### 5. Soak
Leave staging running for a short soak (15–30 min) and watch logs / Sentry for any new errors,
memory growth, or restart loops that a cold smoke wouldn't surface.

## Acceptance criteria (promote to prod only if ALL hold)
- [ ] Images built on the new bases in Coolify's own pipeline.
- [ ] All services healthy; api entrypoint gates passed; versions confirmed.
- [ ] All four smoke suites pass against staging.
- [ ] Pillow image processing, WS live updates, and static/media serving all verified by hand.
- [ ] No new errors in a 15–30 min soak.

## Rollback
If any step fails: in Coolify, **redeploy the previous (known-good) commit/image** on staging — do
**not** promote to prod. If the bump itself is at fault, revert the base-image commit on `main`
(e.g. `git revert <sha>`), let CI go green, and re-run this procedure. Because the CI `docker` gate
now build- and boot-tests every image change, a base bump should rarely get this far broken — but the
staging deploy is the last check before real customer traffic.

## What an agent can't do here
Deploying to your Coolify staging, running the PowerShell smokes against a live domain, and the
hands-on base-specific checks are owner/ops actions (no Coolify access, no staging infra, no live
domain). This runbook is the exact sequence; the deploy + smoke are yours.
