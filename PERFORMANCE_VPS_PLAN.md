# Kepoli Performance + VPS Plan — load fast, run robustly

_Generated from the kepoli-ux-perf-audit workflow (11 agents). Track: performance/infra engineer_

## Headline lever

> Stop shipping uncompressed/over-bloated bytes from the edge: enable gzip level 6 + Traefik compress middleware + lazy-load the EN locale catalog. These three alone cut cold-load wire bytes 30-40% and remove the single biggest parse-blocker, with near-zero risk and S effort each.

## Quick wins (13) — high-impact, low-risk, no device needed → ship first

### QW1. nginx gzip: level 6 + gzip_proxied any + add text/javascript & font/woff2  _(impact: high (30-40% fewer wire bytes every page, every visitor) · effort: S)_
- **Change:** In the http block add `gzip_comp_level 6;` and `gzip_proxied any;` after `gzip_vary on;`, and extend `gzip_types` to include `text/javascript application/wasm font/woff2`. Apply identically to the standalone frontend/nginx.conf AND the heredoc nginx.conf baked into frontend/Dockerfile so dev and prod match. nginx defaults to level 1 (~60% ratio); level 6 is ~70% with negligible CPU on static files — 30-40% fewer wire bytes per response, and gzip_proxied any is what lets nginx compress upstream /api JSON it currently passes through raw.
- **Files:** `frontend/nginx.conf:62-65, frontend/Dockerfile (nginx.conf heredoc)`

### QW2. Traefik compress middleware on api/frontend/admin routers  _(impact: high (gzip+brotli on the entire API edge, currently uncompressed) · effort: S)_
- **Change:** Add label `traefik.http.middlewares.kepoli-compress.compress=true` and append `@kepoli-compress` to the middlewares list of every api router (menu, admin, tenant + ws mirrors) and the frontend/admin routers in docker-compose.coolify.yml. Today zero compress middleware exists, so all /api/* JSON, /static/*, /sitemap.xml and manifests cross Traefik->browser uncompressed. Env/label-only change, no code, no rebuild.
- **Files:** `docker-compose.coolify.yml (all traefik router labels)`

### QW3. uvicorn: nproc-based workers + uvloop + httptools + tuned timeouts/backlog  _(impact: high (3-5x faster async I/O, cores no longer idle) · effort: S)_
- **Change:** Replace the hard-coded `--workers 3` exec line with `--workers "${GUNICORN_WORKERS:-$(( $(nproc) * 2 + 1 ))}" --loop uvloop --http httptools --proxy-headers --forwarded-allow-ips='172.16.0.0/12' --timeout-keep-alive 75 --timeout-graceful-shutdown 30 --backlog 256`. uvicorn[standard]==0.30.6 already ships uvloop+httptools but they are only used when explicitly requested; without uvloop each async op is 3-5x slower. nproc fallback auto-sizes a 2-core VPS to 5 workers with no operator action.
- **Files:** `backend/docker/entrypoint.sh:91-98`

### QW4. Docker resource limits on every service (protect Postgres from OOM)  _(impact: high (prevents whole-VPS OOM cascade) · effort: S)_
- **Change:** Add `deploy.resources.limits` (memory + cpus) to each service in docker-compose.coolify.yml. Example for 4GB VPS: api 800m/1.5, worker 400m/0.5, beat 200m/0.25, frontend/admin 128m/0.25, postgres 1g/1.0, redis 256m/0.25. Currently zero limits exist, so a Celery PDF job or an api memory spike can trigger the Linux OOM killer on Postgres. Pure compose change, no code.
- **Files:** `docker-compose.coolify.yml (all service definitions)`

### QW5. Marketplace restaurant detail: read denormalized Profile.rating_avg instead of per-request cross-schema aggregate  _(impact: high (removes a schema switch + aggregate from the hottest detail page) · effort: S)_
- **Change:** In MarketplaceRestaurantDetailView replace the `schema_context` + `_Rating.objects.aggregate(...)` block with `rating_average = float(profile.rating_avg) if profile.rating_avg is not None else None; rating_count = profile.rating_count or 0`. The listing endpoints already read these denormalized fields (kept in sync by menu.Rating post_save/post_delete signals); the detail view is the lone path still doing a cross-schema aggregate on every load.
- **Files:** `backend/accounts/views.py:3951-3954`

### QW6. Postgres server-parameter tuning via command override  _(impact: high (sorts/aggregates stop spilling to disk; right-sized memory) · effort: S)_
- **Change:** Add to the postgres service: `command: postgres -c shared_buffers=512MB -c effective_cache_size=1536MB -c work_mem=13MB -c maintenance_work_mem=128MB -c max_connections=25 -c checkpoint_completion_target=0.9 -c wal_buffers=16MB -c random_page_cost=1.1 -c log_min_duration_statement=500`. Runs at 128MB defaults today; tune shared_buffers to ~25% of actual VPS RAM. log_min_duration_statement=500 surfaces slow queries in Coolify logs for free.
- **Files:** `docker-compose.coolify.yml (postgres service)`

### QW7. Collapse three combo_components iterations in DishSerializer into one pass  _(impact: medium (cuts combo Python overhead by ~66% per menu render) · effort: S)_
- **Change:** Merge get_is_combo, get_combo_unavailable, and get_combo_components into a single pass inside to_representation: `_comps = list(instance.combo_components.all())` then derive all three flags from `_comps`. Eliminates 2xN_dishes redundant in-memory traversals on every menu response (the hottest read path).
- **Files:** `backend/menu/serializers.py:394-438`

### QW8. manifest-loader.js: add defer (un-block the HTML parser)  _(impact: medium (removes a render-blocking script from <head>) · effort: S)_
- **Change:** Change `<script src="/manifest-loader.js">` to `<script src="/manifest-loader.js" defer>`. The PWA manifest link is only consumed at install time, not for paint, so blocking the parser + an extra round-trip on every load is wasted. Unlike locale-boot.js it does not need to run pre-paint.
- **Files:** `frontend/index.html:13`

### QW9. SecuritySettings.vue: dynamic-import qrcode (~60KB out of OwnerProfile chunk)  _(impact: medium (~60KB off the owner profile chunk) · effort: S)_
- **Change:** Remove `import QRCode from 'qrcode'` and inside the QR-generation function use `const QRCode = (await import('qrcode')).default;` — mirroring the existing pattern in OwnerTables.vue:556 and CustomerAccount.vue:2650. qrcode is only needed during one-time TOTP 2FA setup but currently rides in OwnerProfile unconditionally.
- **Files:** `frontend/src/components/SecuritySettings.vue:230`

### QW10. psycopg2-binary -> psycopg2 (source build) for production  _(impact: medium (system libpq + security patches, safer under uvicorn workers) · effort: S)_
- **Change:** Change requirements.txt line 2 from `psycopg2-binary==2.9.9` to `psycopg2==2.9.9`. libpq-dev is already installed and kept in the runtime image (only build-essential is purged), so the source build works with no Dockerfile change. Binary wheel freezes its own bundled libpq/OpenSSL and is documented as not recommended for production / multi-threaded use.
- **Files:** `backend/requirements.txt:2`

### QW11. Remove dead @vueuse/core dependency  _(impact: low (dependency hygiene, faster CI install) · effort: S)_
- **Change:** `npm uninstall @vueuse/core` and drop it from package.json. Zero imports exist in frontend/src; tree-shaking already keeps it out of the bundle, but removing it shrinks node_modules (~4MB), speeds npm ci, and removes a misleading dependency surface. Re-run build to confirm bundle sizes are unchanged.
- **Files:** `frontend/package.json:28`

### QW12. nginx server_tokens off  _(impact: low (security header hygiene) · effort: S)_
- **Change:** Add `server_tokens off;` to the http block in both frontend/nginx.conf and the Dockerfile heredoc. Stops leaking the exact nginx version in Server headers and error pages (CIS/OWASP baseline).
- **Files:** `frontend/nginx.conf, frontend/Dockerfile (nginx.conf heredoc)`

### QW13. HSTS max-age 3600 -> 86400 via Coolify env  _(impact: low (closes the hourly HTTPS-strip window) · effort: S)_
- **Change:** Set `DJANGO_SECURE_HSTS_SECONDS=86400` in the docker-compose environment (1 day is safe for any live HTTPS deployment). Document the ramp 86400 -> 2592000 -> 31536000 -> include-subdomains -> preload in the deployment runbook. Env-only, zero code.
- **Files:** `docker-compose.coolify.yml (DJANGO_SECURE_HSTS_SECONDS env)`

## Waves (4)

### Wave 1 — Bundle & initial-load (frontend critical path)

_Goal:_ Shrink and de-block what every visitor parses before first paint. These items concentrate in the i18n/index.html/vite.config bottleneck files, so they MUST run as one wave to avoid edit collisions on those shared files.

- **Lazy-load the EN locale catalog (currently static-imported into main entry)** _(impact high (~150KB off the parse-before-paint entry chunk) · effort M · risk medium)_
  - In localeLoader.js:13 replace `import enMessages from './messages-en.js'` with a dynamic import routed through the same ensureLocale() path used for AR/FR. Seed an empty reactive `catalog.en = {}` so the catalog object exists before first render, then fill it from the lazy chunk; OR split messages-en.js into a small synchronous critical stub (auth/nav/common labels) + a full catalog loaded post-mount. messages-en.js is 216KB source (~150KB min) and is folded into index entry chunk today, so even AR/FR visitors download the full English catalog before boot. Note verify-i18n scripts import messages.js directly via Node and are unaffected.
  - `frontend/src/i18n/localeLoader.js:13, frontend/src/i18n/messages-en.js`
- **Self-host (or non-block) Google Fonts + preload the LCP-path woff2** _(impact high (removes render-blocking font CSS chain; 0.5-1.5s LCP on 4G) · effort M · risk low)_
  - Option A (preferred): add @fontsource/space-grotesk, /fraunces, /noto-naskh-arabic, /noto-sans-arabic as devDeps and `@import` only the needed weight subsets in tailwind.css — removes the third-party request, the blocking stylesheet, and serves woff2 same-origin with immutable cache. Option B (quick): change the Google Fonts `<link rel=stylesheet>` to `media=print onload="this.media='all'"` with a <noscript> fallback, and add `<link rel=preload as=font type=font/woff2 crossorigin>` for the Space Grotesk 400 (LCP-path) file. display=swap does NOT make the stylesheet itself non-blocking.
  - `frontend/index.html:21-29, frontend/src/styles/tailwind.css`
- **manualChunks: isolate vendor-sentry (336KB) and vendor-leaflet for cache stability** _(impact medium (336KB stays cached across deploys) · effort S · risk low)_
  - Convert the manualChunks object form to a function: `if (id.includes('/node_modules/@sentry/')) return 'vendor-sentry'; if (id.includes('/node_modules/leaflet/')) return 'vendor-leaflet';` then keep the existing vendor-vue (vue/pinia/vue-router) and vendor-http (axios) buckets. Today Sentry's 336KB rides a chunk hashed off the main entry, so every app-code deploy busts Sentry's cache for all returning users.
  - `frontend/vite.config.js:32-35`

### Wave 2 — DB indexes & query shape (backend, additive migrations)

_Goal:_ Add compound indexes and kill per-tick redundant queries so hot poll/read paths stay O(log N) under load. All index migrations are additive and must be run CONCURRENTLY (atomic=False) to avoid table locks.

- **CustomerOrderRef compound index (customer, status, -order_created_at)** _(impact high (active-orders lookup -> single index range scan) · effort S · risk low)_
  - Add `models.Index(fields=['customer','status','-order_created_at'], name='order_ref_cust_status_created_idx')` to CustomerOrderRef.Meta.indexes. CustomerActiveItemsView filters on (customer_id, status__in) ordered by -order_created_at; the current (customer,-created) index forces a post-filter on status. CONCURRENTLY migration.
  - `backend/accounts/models.py:336-343`
- **DeliveryJob compound index (driver, status)** _(impact high (driver-pool poll -> O(log N)) · effort S · risk low)_
  - Add `models.Index(fields=['driver','status'], name='deliveryjob_driver_status_idx')`; consider a partial index `WHERE status NOT IN ('delivered','failed','cancelled')` to keep it small as the table grows. The driver active-jobs query (60/min poll) currently hits an unindexed driver FK column and scans. CONCURRENTLY.
  - `backend/accounts/models.py:933-938`
- **RideRequest compound index (rider, kind, status)** _(impact medium (two active-trip lookups -> index range scans) · effort S · risk low)_
  - Add `models.Index(fields=['rider','kind','status'], name='riderequest_rider_kind_status_idx')`; optional partial `WHERE status NOT IN ('completed','cancelled')`. CustomerActiveItemsView runs the rider+kind+status active-trip lookup twice per call (RIDE + PACKAGE) with only single-column indexes today. CONCURRENTLY.
  - `backend/accounts/models.py:1108-1113`
- **Cache section_name_by_slug per tenant; add TableLink(section,slug) index** _(impact high (removes ~300 JOIN queries/min per active staff tab) · effort M · risk low)_
  - Cache the `section_name_by_slug` dict under `section_names:{tenant_id}` TTL 60s and bust it in TableSection/TableLink save signals — StaffOrderListView currently rebuilds this JOIN on every poll tick (300/min throttle), so 300 JOIN round-trips/min/tab collapse to <=1/min/tenant. Also add `models.Index(fields=['section','slug'], name='tablelink_section_slug_idx')`.
  - `backend/menu/views.py:4102-4104, backend/menu/models.py (TableLink)`

### Wave 3 — nginx & Docker edge tuning (infra config)

_Goal:_ Tune the network edge and serve static directly from nginx. These all touch nginx.conf / Dockerfile / docker-compose.coolify.yml — keep them in one wave so the gzip quick-win and these edits don't collide on the same config blocks.

- **nginx throughput directives: tcp_nopush/nodelay, open_file_cache, keepalive_requests** _(impact medium (fewer syscalls/packets per static request) · effort S · risk low)_
  - Add to the http block (both frontend/nginx.conf and the Dockerfile heredoc): `tcp_nopush on; tcp_nodelay on; open_file_cache max=1000 inactive=60s; open_file_cache_valid 30s; open_file_cache_min_uses 2; keepalive_requests 1000;`. Standard nginx static-serving throughput wins (the gzip_comp_level part of this set is already shipped in the quick-win wave).
  - `frontend/nginx.conf (server/http block), frontend/Dockerfile (heredoc)`
- **Serve /static/ directly from nginx via shared volume (drop the Django/WhiteNoise proxy hop)** _(impact medium (no uvicorn worker time per static file) · effort M · risk medium)_
  - Add a `static_data` named volume; mount `static_data:/app/staticfiles` on api and `:ro` on frontend/admin. Replace the `location ^~ /static/ { proxy_pass http://api:8000; }` block with `alias /app/staticfiles/; expires 365d; add_header Cache-Control "public, max-age=31536000, immutable" always; try_files $uri =404;`. entrypoint.sh already runs collectstatic, so the volume is populated on first start. Test in dev/staging first since it changes the static topology and needs the volume present before nginx starts.
  - `docker-compose.coolify.yml (volumes), frontend/nginx.conf:181-194`
- **API proxy buffering tuning + dedicated unbuffered SSE location** _(impact medium (large JSON stops spilling to disk; SSE delivers live) · effort S · risk low)_
  - Add `proxy_buffer_size 4k; proxy_buffers 8 16k; proxy_busy_buffers_size 32k;` to the `location ^~ /api/` block. Add a dedicated `location = /api/marketplace/track/` BEFORE the general /api/ block with `proxy_buffering off; proxy_cache off; proxy_read_timeout 120s; chunked_transfer_encoding on; add_header X-Accel-Buffering "no";` (same upstream headers) so SSE events are not buffered/delayed. 120s matches HTTP_REQUEST_TIMEOUT.
  - `frontend/nginx.conf (location ^~ /api/ block ~107-117)`
- **De-duplicate frontend+admin Docker builds (YAML anchor / shared image)** _(impact medium (halves deploy build minutes) · effort S · risk low)_
  - Add an `x-frontend-build: &frontend-build` anchor with the full build block; reference it with `<<: *frontend-build` on frontend, and on admin either reuse `image: resto-frontend-build:latest` or `build.cache_from: [resto-frontend-build:latest]`. Both services build the byte-identical image today, doubling 2-4 min build time per deploy for no benefit.
  - `docker-compose.coolify.yml:1-74`
- **Exclude tests/, docs, *.md from the backend Docker build context** _(impact low (smaller image + build context) · effort S · risk low)_
  - Add `tests/`, `docs/`, `*.md`, `*.rst`, and non-requirements `*.txt` (re-include `!requirements.txt`) plus `.git/` to backend/.dockerignore. `COPY . .` currently bakes the full test suite and docs into the production layer.
  - `backend/.dockerignore`

### Wave 4 — PWA service worker & DRF pagination (behavior changes, validate before merge)

_Goal:_ Turn repeat visits instant and bound unbounded list responses. These two change runtime behavior (cache strategy, API envelope) and carry real regression surface, so they ship after the safe waves and the PWA item gets device validation.

- **Workbox service worker via vite-plugin-pwa (precache + runtime caching), merge existing push handler** _(impact medium (instant repeat-load + offline menu) · effort M · risk medium) · **[device-validate]**_
  - Add vite-plugin-pwa configured with registerType:'autoUpdate', workbox.globPatterns for js/css/html/ico/png/svg, runtimeCaching NetworkFirst (5s timeout) for /api, and manifest fields mirroring the static manifest.json. The current public/sw.js handles ONLY push/notificationclick and explicitly implements no cache strategy, so every navigation hits the origin cold (index.html is no-store). Merge the existing push handler in via injectManifest mode so notifications keep working. Repeat visits become instant (assets from cache) and the customer menu works offline.
  - `frontend/public/sw.js, frontend/vite.config.js`
- **Global DRF pagination (PageNumberPagination, PAGE_SIZE 50) + opt-outs** _(impact high (bounds unbounded responses; safer default for all future endpoints) · effort M · risk medium)_
  - Add `DEFAULT_PAGINATION_CLASS = 'rest_framework.pagination.PageNumberPagination'`, `PAGE_SIZE = 50` to REST_FRAMEWORK. This bounds the admin DeliveryJob list and the staff order view (currently manual qs[:100]) but is a breaking envelope change for SPA consumers: audit every ViewSet the frontend calls and set `pagination_class = None` on those that intentionally return all rows (e.g. cached menu categories) OR update the frontend caller to read the paginated envelope. Owner order-history already has bespoke correct paging — leave it or migrate it deliberately. Verify against the frontend before merge.
  - `backend/config/rest_framework.py:18-98`

## Deferred

- Critical-CSS inlining (vite-plugin-critical/critters) — L effort, medium risk: extraction misses Vue-binding dynamic class names; the 259KB CSS is ~65KB gzipped after Wave-1 compression, so revisit only after the high-impact items land.
- Marketplace city/cuisine pg_trgm GIN indexes — icontains seq-scans are negligible below ~500 tenants and the listing is cached; defer until tenant count or marketplace search latency actually warrants the CREATE EXTENSION pg_trgm + GIN index.
- SESSION_SAVE_EVERY_REQUEST sliding-save optimization — L effort, medium risk for a ~0.1ms Redis SETEX; the current setting is semantically correct for the 90-day sliding window. Do not act until profiling shows it in the hot path.
- PgBouncer connection pooling — peak ~8 persistent connections today is well within Postgres limits after the max_connections=25 tuning; add only when worker/celery scale-out pushes connection count toward the cap.
