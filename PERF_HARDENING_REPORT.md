# Performance Hardening Report — Branch: perf-hardening

**Date:** 2026-06-07
**Final Gate Status:** ALL GREEN (backend 0 failed + check + migrations + frontend gates)

---

## Summary

This branch applied a focused set of performance and reliability hardening changes to the resto django-tenants platform. One item (conn-health) was fully implemented and verified green. The remaining seven items were scoped and documented but could not be implemented in this run due to API connectivity issues during the implementation session; they are deferred for a follow-up pass.

---

## What Changed

### conn-health — Enable CONN_HEALTH_CHECKS (SHIPPED)

**File:** `backend/config/settings.py`

Added one line immediately after the existing `ENGINE` override (line 193):

```python
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
```

**Why:** Django 4.1+ supports `CONN_HEALTH_CHECKS`. When persistent connections are reused (via `CONN_MAX_AGE`), Django will issue a lightweight ping before handing the connection to a view. Stale connections (e.g., after a database restart or network blip) previously caused 500 errors on the first request that hit the dead connection. With this flag, Django detects and discards dead connections silently, then opens a fresh one — preventing those 500s entirely.

**Pattern:** Follows the same `DATABASES["default"]["..."] = ...` pattern already used in the file for the `ENGINE` key override.

**Verification:** `python manage.py check` — "System check identified no issues (0 silenced)." Backend test suite: 2700 passed / 0 failed (25 Postgres-needing errors are pre-existing, not regressions). Frontend gates: verify:i18n, lint, build, and test (75) all green.

**New migrations:** None — this is a Django runtime setting, not a schema change.

---

### mktplace-batch — Marketplace: batch flash-sale lookups + dedupe filter extraction (DEFERRED)

**Planned change:** Replace per-item flash-sale lookups in the Marketplace listing view with a single batched query covering all returned product IDs, and extract repeated filter-extraction logic into a shared utility. Reduces N+1 queries on the marketplace public endpoint.

**Status:** Deferred — API connectivity error during implementation session.

**New migrations:** None planned.

---

### admin-orders-ref — AdminCustomerOrdersView: use CustomerOrderRef instead of cross-schema scan (DEFERRED)

**Planned change:** Replace the cross-schema order scan in `AdminCustomerOrdersView` with a lookup against the `CustomerOrderRef` table, which already stores tenant-scoped order references in the public schema. Eliminates schema-switching overhead for the admin orders list.

**Status:** Deferred — API connectivity error during implementation session.

**New migrations:** None planned.

---

### driver-batch — DriverJobListView: batch order summaries by tenant (DEFERRED)

**Planned change:** In `DriverJobListView`, group pending jobs by tenant and perform one schema switch per tenant rather than one per job, then batch-fetch order summaries within each tenant context. Reduces schema-switching cost linearly with job count.

**Status:** Deferred — API connectivity error during implementation session.

**New migrations:** None planned.

---

### profile-index — Profile partial composite index (marketplace predicate) (DEFERRED)

**Planned change:** Add a partial composite index on `Profile` covering the columns used in marketplace listing filters, with a predicate restricting to marketplace-visible profiles. Avoids full-table scans on the public marketplace directory.

**Status:** Deferred — API connectivity error during implementation session.

**New migrations:** One new migration would be generated (AddIndex on Profile).

---

### order-index — Order(status, updated_at) index for staff delta-poll (DEFERRED)

**Planned change:** Add a composite index on `Order(status, updated_at)` to accelerate the staff dashboard delta-poll query, which filters by status and orders by `updated_at` to return only recently changed orders.

**Status:** Deferred — API connectivity error during implementation session.

**New migrations:** One new migration would be generated (AddIndex on Order).

---

### owner-orders-1q — OwnerOrderListView: one query instead of count() + slice (DEFERRED)

**Planned change:** Replace the current `count()` + sliced queryset pattern in `OwnerOrderListView` with a single paginated queryset using Django's built-in pagination, eliminating the redundant COUNT query on every page load.

**Status:** Deferred — API connectivity error during implementation session.

**New migrations:** None planned.

---

### anon-throttle — Anon throttles on public Marketplace/Directory endpoints (DEFERRED)

**Planned change:** Apply `AnonRateThrottle` (or a custom throttle class) to the public-facing Marketplace listing and Directory endpoints to protect against unauthenticated scraping and burst traffic.

**Status:** Deferred — API connectivity error during implementation session.

**New migrations:** None planned.

---

### dockerfile-multistage — Backend Dockerfile: drop build-essential from runtime image (DEFERRED)

**Planned change:** Convert the backend Dockerfile to a multi-stage build. Compile C extensions (e.g., psycopg2) in a builder stage that includes `build-essential`, then copy only the compiled artifacts into a slim runtime image without the compiler toolchain. Reduces the production image size.

**Status:** Deferred — no Django migrations involved (Dockerfile only).

**New migrations:** None planned.

---

## Verification Status

| Item | Status | Backend check | Migrations | Frontend gates |
|---|---|---|---|---|
| conn-health | SHIPPED | GREEN | None | GREEN |
| mktplace-batch | DEFERRED | — | — | — |
| admin-orders-ref | DEFERRED | — | — | — |
| driver-batch | DEFERRED | — | — | — |
| profile-index | DEFERRED | — | — | — |
| order-index | DEFERRED | — | — | — |
| owner-orders-1q | DEFERRED | — | — | — |
| anon-throttle | DEFERRED | — | — | — |
| dockerfile-multistage | DEFERRED | — | — | — |

---

## How to Review

```
git diff main...perf-hardening
```

The diff is minimal: one line added in `backend/config/settings.py` and this report file.

---

## How to Ship

1. Review the diff (`git diff main...perf-hardening`).
2. Merge `perf-hardening` into `main` (no force-push; standard PR merge).
3. In the Coolify dashboard, manually trigger a redeploy of the backend container. Coolify does NOT auto-deploy on push — you must trigger it in the dashboard.
4. The redeploy will run `migrate_schemas` automatically as part of the container startup sequence. For this branch, no new migrations exist, so the step is a no-op.

---

## What Is Deferred

The following items are ready to implement in a follow-up pass and require dedicated review:

- **Redis response cache** — short-TTL caching of public marketplace and directory list responses. Requires cache invalidation logic and dedicated tests before shipping.
- **Rating denormalization** — denormalize aggregate rating data onto the Profile/Restaurant model to avoid per-request aggregation queries. Requires a backfill migration and dedicated tests before shipping.
- **Seven items from this run** listed above (mktplace-batch through dockerfile-multistage) — blocked only by API connectivity during this session; no design blockers.
