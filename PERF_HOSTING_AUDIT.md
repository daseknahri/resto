# Performance & Hosting Efficiency Backlog
_Generated: 2026-06-07 — based on verified source-code audit of `accounts/views.py`, `menu/views.py`, `menu/models.py`, `tenancy/models.py`, `config/settings.py`, `backend/Dockerfile`, `docker-compose.coolify.yml`_

---

## 1. Executive Summary

**The five biggest wins — do these first:**

1. **Cache `MarketplaceView` and `DirectoryView` responses in Redis (60–120 s TTL).** Both views execute O(N_tenants) synchronous Postgres schema-context switches per request, fully uncached, on public/unauthenticated endpoints. At 50 tenants a single marketplace page load fires 150–300+ SQL statements. At mealtimes with 10 concurrent visitors this saturates the 3-worker uvicorn pool. A `cache.get/set` wrapper keyed on query-param hash costs ~10 lines of code and drops median response time from seconds to milliseconds. This is the single highest ROI change in the codebase.

2. **Denormalize `rating_avg` + `rating_count` into `tenancy.Profile` (public schema).** The per-tenant `schema_context` loop in both marketplace views exists almost entirely to compute `Rating.aggregate()` per restaurant. Move that aggregation to a Django signal (or cheap Celery task) that writes `rating_avg`/`rating_count` onto the public-schema `Profile` record on every new `Rating` save. The inner loop then needs zero schema hops for rating data, collapsing hundreds of round-trips to one bulk `Profile` query.

3. **Batch `PlatformFlashSaleOptIn` and `PlatformFlashSale` lookups before the marketplace loop.** Currently these are two separate public-schema queries fired inside the per-tenant `for` loop (lines ~2261-2269 in `accounts/views.py`). One `filter(is_active=True).values(...)` call before the loop eliminates up to 2×N_tenants queries at zero schema-switch cost.

4. **Replace `AdminCustomerOrdersView`'s brute-force cross-schema scan with `CustomerOrderRef`.** The view already has a `MAX_TENANTS = 500` guard — but 500 schema switches per admin page load is unacceptable. `CustomerMarketplaceOrdersView` already does this right via the denormalized `CustomerOrderRef` table. Wire `AdminCustomerOrdersView` to the same path. Effort: S.

5. **Multi-stage Docker build for the backend image (drop `build-essential` from the final layer).** The `backend/Dockerfile` installs `build-essential` into the running image, adding ~180–220 MB. Switching to a two-stage build (or purging the toolchain in the same `RUN` layer) reduces image size, speeds up Coolify redeploys, and shrinks the attack surface. Effort: M.

---

## 2. Speed Backlog

### 2A. Backend — Queries & Indexes

Items marked **[VERIFIED]** were confirmed by direct source inspection. Remaining items were reported by the audit tool and are likely correct but not individually line-traced.

| Pri | Issue | Files | Fix | Impact | Effort |
|-----|-------|-------|-----|--------|--------|
| **C** [VERIFIED] | `MarketplaceView`: 2–3 DB round-trips per tenant in Python loop (up to 200 tenants); `PlatformFlashSaleOptIn` queried inside loop per tenant | `accounts/views.py` L2239–2271 | Pre-build `opted_map` and `live_flash_sales` set once before the loop with a single `filter(is_active=True).values(...)` bulk query; no schema-context needed | At 50 tenants: 100+ extra public-schema queries per request eliminated | S |
| **C** [VERIFIED] | `MarketplaceView` + `DirectoryView`: per-tenant `schema_context()` + `Rating.aggregate()` inside Python loop — fully uncached public endpoints | `accounts/views.py` L2107–2116, L2239–2257 | Cache full response in Redis with 60–120 s TTL, key = hash of query params (excluding lat/lng); invalidate on `Profile.save()` via post_save signal | At 50 tenants: 150–300+ SQL statements per request, 800–2000 ms response time; concurrent mealtime traffic saturates DB and uvicorn pool | M |
| **C** [VERIFIED] | `DirectoryView`: 2 additional full-table `Profile` scans after main loop to extract `cities` / `cuisines` | `accounts/views.py` L2131–2133 | Accumulate cities/cuisines from already-fetched `qs` rows in memory (or call `.values_list('city','cuisine_type')` once on the pre-sliced queryset before the loop) | Eliminates 2 full-table scans per directory request | S |
| **C** [VERIFIED] | `MarketplaceView`: same redundant `all_opted` full-table scan × 3 (cities, cuisines, tags) | `accounts/views.py` L2308–2314 | Same fix — iterate `results` already in memory or do a single `values_list('city','cuisine_type','tags')` pre-slice | Eliminates 3 full-table scans per marketplace request | S |
| **H** [VERIFIED] | `AdminCustomerOrdersView`: iterates up to 500 tenant schemas per admin customer detail page | `accounts/views.py` L1777–1800 | Use `CustomerOrderRef.objects.filter(customer_id=customer_id).order_by('-order_created_at')[:50]` — same pattern as `CustomerMarketplaceOrdersView` | At 50+ tenants: 50+ schema switches per admin load; blocks a uvicorn worker for seconds | S |
| **H** [VERIFIED] | `DriverJobListView`: `_job_order_summary()` does 1 `Tenant` lookup + 1 `schema_context` switch per job in loop | `accounts/views.py` L3826–3836 | Pre-fetch all unique `tenant_id`s in one query; for each schema switch once and batch-fetch all `order_number`s for that schema in a single `Order.objects.filter(order_number__in=[...])` call | Driver job list polled by every online driver; each poll can fire 20+ schema switches | M |
| **M** [VERIFIED] | `tenancy.Profile.directory_opt_in` and `is_menu_published` are unindexed despite being the primary marketplace filter predicates | `tenancy/models.py` L273–325 | Add partial composite index: `Index(fields=['directory_opt_in','is_menu_published'], condition=Q(directory_opt_in=True, is_menu_published=True), name='profile_marketplace_idx')` in a new migration | Full Profile seq-scan on every marketplace request; degrades linearly with tenant count | S |
| **M** [VERIFIED] | `MarketplaceView`: `?open=1` filter and `?q=` full-text search applied in Python after fetching 200 rows | `accounts/views.py` L2217–2228 | Push `q` filter into SQL: `qs.filter(Q(tenant__name__icontains=q) | Q(tagline__icontains=q) | Q(cuisine_type__icontains=q))`; for `open_only`, materialize `is_open` as a periodically-updated boolean on Profile | A `?q=steak&open=1` request fetches 200 profiles to return 5 results | M |
| **M** [VERIFIED] | `AdminPlatformAnalyticsView`: 4 separate `Tenant.count()` calls that can be folded into one aggregate | `accounts/views.py` L4834–4838 | `Tenant.objects.aggregate(total=Count('id'), active=Count('id', filter=Q(lifecycle_status='active')), suspended=..., canceled=...)` — then same for `Customer`; cache response 60 s | Admin-only but wastes DB cycles; reduces ~11 queries to ~6 | S |
| **M** [VERIFIED] | `OwnerOrderListView`: separate `count()` + slice fires two queries every owner poll cycle | `menu/views.py` L3410–3411 | Fetch `all_orders = list(qs[:201])`; `has_more = len(all_orders) > 200`; `all_orders = all_orders[:200]` — one query instead of two | Saves one `COUNT(*)` per owner poll on potentially thousands of orders | S |
| **M** [VERIFIED] | `StaffShiftSummaryView`: average prep time computed in Python via full row fetch instead of DB aggregate | `menu/views.py` L3115–3125 | `qs.aggregate(avg_prep=Avg(ExpressionWrapper(F('status_updated_at') - F('created_at'), output_field=DurationField())))` | Reduces 3 queries to 1–2; avoids transferring full row set over the wire | S |
| **M** [VERIFIED] | `Order.updated_at` has no index; `StaffOrderListView` `?since=` delta-poll filters on it at 300 req/min from staff tablets | `menu/models.py` L433 | Add `Index(fields=('status','updated_at'))` to `Order.Meta.indexes` (composite covers the active-order delta-poll pattern) | Without index: full active-row scan on every staff poll tick | S |

### 2B. Backend — Caching & Async (Structural)

| Pri | Issue | Files | Fix | Impact | Effort |
|-----|-------|-------|-----|--------|--------|
| **C** [VERIFIED] | No response cache on the two highest-traffic public endpoints; marketplace data is static for 60–120 s between restaurant updates | `accounts/views.py` | At top of `MarketplaceView.get()` and `DirectoryView.get()`: compute `cache_key = f'marketplace:v1:{hashlib.md5(param_str.encode()).hexdigest()}'`; `hit = cache.get(cache_key)`; if hit return `Response(hit)`; after computation `cache.set(cache_key, data, 90)`; bust via `post_save` signal on `tenancy.Profile` | Transforms O(N_tenants) DB work into a single Redis GET for all but the first requester in any 90-second window | M |
| **C** [VERIFIED] | Rating aggregates computed live in the hot path — should be denormalized | `tenancy/models.py`, `menu/models.py` | Add `rating_avg` (FloatField, null) and `rating_count` (IntegerField, default=0) to `tenancy.Profile`; write a `post_save` signal on `menu.Rating` that calls `schema_context` once and updates the profile fields; the marketplace loop then reads them from the already-fetched queryset with zero extra queries | The inner loop does zero schema switches for rating data; whole-view speedup is multiplicative with the caching fix | M |
| **H** | Per-tenant `schema_context` loop in driver job enrichment should be batched | `accounts/views.py` | Group jobs by `tenant_id`; for each unique tenant: switch context once, `Order.objects.filter(order_number__in=[...])` — eliminates N schema switches for N jobs | Polled by every active driver; scales with fleet size | M |

### 2C. Frontend — Bundle

| Pri | Issue | Files | Fix | Impact | Effort |
|-----|-------|-------|-----|--------|--------|
| **M** | `leaflet` (~150 kB gzip) bundled into every page including non-map pages (used only on delivery tracker / driver map) | `frontend/package.json`, map-using Vue files | Dynamic `import('leaflet')` inside the component that needs it; mark as a separate Rollup chunk in `vite.config.js` | Removes ~150 kB from the initial JS payload for all non-map pages | S |
| **M** | `qrcode` (~60 kB) bundled globally; used only on the QR export feature | `frontend/package.json` | Dynamic import on the QR-generation code path only | Removes ~60 kB from initial bundle | S |
| **L** | `chunkSizeWarningLimit` raised to 600 kB masks oversized chunks rather than fixing them | `frontend/vite.config.js` | Address the two above dynamic imports first; then restore the limit to 500 or 400 kB to keep early warning | No runtime impact, but keeps chunk discipline | S |
| **L** | Sentry SDK (`@sentry/vue`) loaded synchronously in main bundle; replays and profiling add significant weight | `frontend/package.json` | Enable lazy initialization: `Sentry.lazyLoadIntegration(...)` for replay/profiling; tree-shake unused integrations | Reduces first-load parse time | M |

### 2D. Frontend — Runtime

| Pri | Issue | Files | Fix | Impact | Effort |
|-----|-------|-------|-----|--------|--------|
| **M** | `MarketplaceOrderStatus.vue` (and similar) polls at 15-second intervals over HTTP — confirmed in `MarketplaceOrderStatusThrottle`; meanwhile WebSocket infrastructure already exists | Frontend polling pages | Subscribe to the existing Django Channels `order_{order_number}` group for live status instead of polling; fall back to polling only if WS unavailable | Eliminates background HTTP load from all active order-status pages; reduces server load at mealtimes | M |
| **L** | No HTTP caching headers on API responses (ETag / `Cache-Control: max-age`) for stable public data (menu, directory) | Django response layer | Add `@condition` decorator or manually set `ETag`/`Last-Modified` on `MarketplaceMenuView`, `DirectoryView`; browsers and CDN skip requests on cache hit | Reduces API calls from returning visitors; enables future CDN layer | M |

---

## 3. Hosting Efficiency Backlog

### 3A. Docker / Image

| Pri | Issue | Files | Fix | Impact | Effort |
|-----|-------|-------|-----|--------|--------|
| **M** [VERIFIED] | `backend/Dockerfile` installs `build-essential` in the final image — adds ~180–220 MB to the deployed layer | `backend/Dockerfile` L9–11 | Two-stage build: `builder` stage installs `build-essential` + compiles wheels via `pip wheel --no-deps -r requirements.txt -w /wheels`; `runner` stage copies wheels and installs without build tools. Alternatively: purge in the same `RUN` layer (`&& apt-get purge -y build-essential && apt-get autoremove -y`) | Faster Coolify redeploy pulls; less disk on VPS; smaller attack surface | M |
| **L** | `frontend` and `admin` services in `docker-compose.coolify.yml` build the same Dockerfile and produce identical images — doubling build time and storage | `docker-compose.coolify.yml` L1–68 | Build the image once and reference it by name in both services (`image: resto-frontend:latest`); use a single `build:` block and reference via `image:` in the second service; or collapse into one service if routing allows | Halves frontend build time per deploy; halves image storage | S |
| **L** | `tests/` directory is not excluded by `.dockerignore` — ends up in the production image via `COPY . .` | `backend/.dockerignore` (if it exists) or `backend/Dockerfile` | Add `tests/` and `*.md` and `*.txt` (except `requirements.txt`) to `.dockerignore` | Slightly smaller context; no test code in prod image | S |

### 3B. Server Runtime & Static / Media

| Pri | Issue | Files | Fix | Impact | Effort |
|-----|-------|-------|-----|--------|--------|
| **M** [VERIFIED] | `CONN_HEALTH_CHECKS` not set — stale pooled connections silently 500 after any Postgres restart or network event; with `conn_max_age=600` and 3 workers this can affect users for up to 10 minutes | `config/settings.py` L186–191 | In `DATABASES['default']` add `'CONN_HEALTH_CHECKS': True` (Django 4.1+); one lightweight ping per reused connection | Transparent recovery from Postgres restarts; eliminates unexplained 500s on stale connections | S |
| **M** | `REDIS_URL` is not set by default in Coolify .env template — site runs on `LocMemCache` in "production" if the operator forgets, making the cache a per-worker in-process silo that does nothing for concurrent requests | `config/settings.py` L202, `docker-compose.coolify.yml` | Document `REDIS_URL` as required in Coolify deploy checklist; add a startup `check_settings` that warns (or refuses to start in non-DEBUG) if Redis is absent | Without Redis, all cache calls are per-process no-ops; marketplace caching fix has zero effect | S |
| **L** | `uvicorn` worker count is controlled by `GUNICORN_WORKERS` env var but the entrypoint.sh default is likely 3 — on a 4-core VPS this leaves one core idle during peak; memory usage per worker (~80–120 MB) limits horizontal scale | `docker/entrypoint.sh` | Tune workers to `2 × CPU_cores + 1` via the env var in Coolify; document the formula; consider `--worker-class uvicorn.workers.UvicornWorker` under gunicorn for signal-safe restarts | Better CPU utilization; zero-downtime hot reload | S |

### 3C. Dependencies

| Pri | Issue | Files | Fix | Impact | Effort |
|-----|-------|-------|-----|--------|--------|
| **L** | `reportlab` (PDF generation) and `qrcode` are runtime dependencies pulled into every API container start, adding ~30 MB and increasing import time | `backend/requirements.txt` | These are used only for receipt/QR export paths; they cannot be fully lazy-loaded in Python but confirm they are not imported at module level (currently they are imported inside view methods — good); no action needed unless image size becomes critical | Low | N/A |
| **L** | `leaflet` is a production dependency (`dependencies`, not `devDependencies`) — it is bundled even if the dynamic-import fix above is applied, because Vite still resolves it at build time | `frontend/package.json` | Move to `dependencies` but ensure it is only imported dynamically; Rollup will code-split it correctly | Correct — no change needed if dynamic import is done properly | N/A |

### 3D. Multi-Tenant Scale

| Pri | Issue | Files | Fix | Impact | Effort |
|-----|-------|-------|-----|--------|--------|
| **C** [VERIFIED] | `MarketplaceView` response time grows O(N_tenants): at 200 tenants = ~800 DB queries/request; Postgres connection pool saturates under concurrent load | `accounts/views.py` | Cache (see 2B) + denormalize ratings (see 2B) — these together collapse the loop to zero schema hops; add partial index on `Profile` (see 2A) | Platform growth currently makes the homepage linearly slower | M |
| **H** [VERIFIED] | `DirectoryView` same O(N) problem; also fires 2 extra full-table scans for filter lists | `accounts/views.py` | Same cache + deduplicate filter extraction from in-memory results | Every unauthenticated directory visitor causes N synchronous Postgres round-trips | M |
| **M** | No rate limiting on `MarketplaceView` / `DirectoryView` (both `AllowAny`, no throttle class) — open to cheap amplification | `accounts/views.py` L2077, L2153 | Add `throttle_classes = [AnonRateThrottle]` (e.g. `100/min` per IP); the Redis cache means throttled users still get fast responses on cache hits | With Redis cache, the real risk is cache-busting attacks via unique param combos — add `throttle_classes` now | S |

### 3E. Ops Cost

| Pri | Issue | Files | Fix | Impact | Effort |
|-----|-------|-------|-----|--------|--------|
| **M** | Two separate `frontend` + `admin` Docker builds on every Coolify redeploy (identical Dockerfile, ~2–3 min each) doubles CI cost with no benefit | `docker-compose.coolify.yml` | Build once, reuse image (see 3A) | ~50% reduction in build minutes per deploy | S |
| **L** | Redis runs with `appendonly yes` (AOF persistence) which is correct for durability, but cache data does not need AOF — separate cache Redis from session/channel-layer Redis, or use `--save ""` for the cache instance if durability is not needed | `docker-compose.coolify.yml` L244 | If splitting is not practical: AOF is cheap on the data volumes involved; accept current config | Minor disk I/O reduction | L |

---

## 4. Recommended Sequencing

### Phase 1 — Quick Wins (high impact, low effort; 1–3 days each)

1. **Enable `CONN_HEALTH_CHECKS`** (`config/settings.py`) — one line, prevents silent 500s. Deploy immediately.
2. **Batch `PlatformFlashSale` / `PlatformFlashSaleOptIn` before the marketplace loop** (`accounts/views.py`) — ~10 lines, eliminates 2×N public-schema queries per request with no structural change.
3. **Deduplicate `cities`/`cuisines`/`tags` extraction** in both `MarketplaceView` and `DirectoryView` — eliminates 3–5 extra full-table scans; iterate in-memory results already computed.
4. **Replace `AdminCustomerOrdersView` with `CustomerOrderRef` lookup** — same pattern as `CustomerMarketplaceOrdersView` already in the codebase; ~15 lines; eliminates 500 schema switches per admin load.
5. **Add composite partial index on `Profile(directory_opt_in, is_menu_published)`** — one migration file, covers every marketplace/directory query.
6. **Add `Index(fields=('status','updated_at'))` to `Order.Meta.indexes`** — one migration file; fixes the 300 req/min staff delta-poll.
7. **Fix `OwnerOrderListView` double-query** (count + slice) — 3-line change in `menu/views.py`.
8. **Add `throttle_classes` to `MarketplaceView` / `DirectoryView`** — 1-line change per view; apply `AnonRateThrottle` at 100/min.

### Phase 2 — Structural (high impact, medium effort; 2–5 days each)

9. **Redis response cache for `MarketplaceView` + `DirectoryView`** — implement `cache.get/set` wrapper, post_save invalidation signal on `tenancy.Profile`. Requires Redis in production (verify `REDIS_URL` is set in Coolify).
10. **Denormalize `rating_avg` + `rating_count` into `tenancy.Profile`** — migration + `post_save` signal on `menu.Rating` via `schema_context`. After this, the inner loop is zero schema hops for rating data.
11. **Batch driver job enrichment in `DriverJobListView`** — group by `tenant_id`, one schema switch per tenant.
12. **Multi-stage backend Dockerfile** — eliminates `build-essential` from the production image.
13. **`StaffShiftSummaryView` aggregate in DB** — replace Python-iteration with `Avg(ExpressionWrapper(...))`.

### Phase 3 — Architecture (lower urgency; revisit at 100+ tenants)

14. **Replace HTTP polling with WebSocket subscriptions** in `MarketplaceOrderStatus.vue` and similar order-tracking pages.
15. **Dynamic import for `leaflet` and `qrcode`** in frontend bundle.
16. **Collapse duplicate frontend Docker builds** into a single image reused by both `frontend` and `admin` services.
17. **HTTP caching headers** (`ETag`, `Cache-Control`) on stable public API responses.
18. **`AdminPlatformAnalyticsView` query consolidation** + 60 s cache.

---

## 5. Verification Status

### Verified (confirmed by direct source inspection in this audit session)

- `MarketplaceView` O(N) schema-context loop with inline `Rating.aggregate()` per tenant — confirmed at `accounts/views.py` L2239–2257
- `DirectoryView` same pattern — confirmed at `accounts/views.py` L2107–2116
- `PlatformFlashSaleOptIn` queried inside loop per tenant — confirmed at `accounts/views.py` L2261–2269
- Redundant `all_opted` full-table scans after main loop in both views — confirmed at `accounts/views.py` L2308–2314, L2131–2133
- `AdminCustomerOrdersView` brute-force cross-schema scan (MAX_TENANTS=500) — confirmed at `accounts/views.py` L1777–1800
- `DriverJobListView` per-job schema switch in `_job_order_summary` — confirmed at `accounts/views.py` L3826–3836
- `OwnerOrderListView` separate `count()` + slice — confirmed at `menu/views.py` L3410–3411
- `StaffShiftSummaryView` Python-iteration for avg prep time — confirmed at `menu/views.py` L3115–3125
- `Order.updated_at` has no index; `Order.Meta.indexes` only covers `(status, created_at)` — confirmed at `menu/models.py` L441–443
- `tenancy.Profile.directory_opt_in` and `is_menu_published` have no `db_index` — confirmed at `tenancy/models.py` L273–325
- `CONN_HEALTH_CHECKS` absent from `DATABASES` config — confirmed at `config/settings.py` L186–191
- `backend/Dockerfile` has `build-essential` in the final image with no purge — confirmed at `backend/Dockerfile` L9–11
- `AdminPlatformAnalyticsView` 4 separate Tenant count queries — confirmed at `accounts/views.py` L4834–4838
- Frontend `leaflet` and `qrcode` are eagerly bundled production dependencies — confirmed at `frontend/package.json`
- Frontend `vite.config.js` has raised `chunkSizeWarningLimit: 600` — confirmed at `frontend/vite.config.js` L27

### Not individually verified (reported by audit tool; likely correct)

- Full-text search / open-filter applied in Python post-fetch (medium finding)
- Frontend Sentry lazy-loading opportunity (low finding)
- Duplicate frontend Docker build cost (low finding)

### Dismissed False Positives

Two findings from the original audit were investigated and refuted:

1. **"migrate_schemas --tenant runs on EVERY container start, creating a multi-process migration race"** — Refuted. The `entrypoint.sh` runs exactly once per container. `exec uvicorn --workers 3` replaces the shell; the forked uvicorn worker subprocesses never re-execute the entrypoint. No race exists. The startup latency concern is real but intentional (fast when no migrations are pending; `SKIP_SCHEMA_HEALTHCHECK=1` escape hatch exists).

2. **"worker and beat containers run the full entrypoint.sh (migrate + collectstatic + seed_plans) on every restart"** — Refuted. When `docker-compose.coolify.yml` specifies `command:`, it replaces `CMD`; the `entrypoint.sh` is never invoked in `worker` or `beat` containers. They start directly with the `celery` command. The sub-claim that `tests/` lands in the image is accurate (`.dockerignore` should exclude it) but is low severity.
