# Performance & Hosting Efficiency Backlog

_Generated: 2026-08-30 — 22-lens read-only audit fan-out (43 raw findings), 8 high/critical findings adversarially re-verified against source; medium/low findings recorded but not individually re-verified. Supersedes the 2026-06-07 edition of this file, whose backlog is fully implemented (see `CLAUDE.md` "Current state")._

---

## 1. Executive Summary

**Speed — the 3 biggest wins:**

1. **Route the last synchronous email/SMS call sites through the async notification infra that already exists.** Three separate findings are the same bug in three places: bulk order-confirm (up to **50 sequential blocking SMTP sends inside one request — critical**), the single owner order-status-update endpoint, and customer phone-OTP send. All three should call the existing `enqueue()` helper (`accounts/tasks.py`) the way the SMS/WhatsApp/push paths already do a few lines away in the same functions. This is not new infrastructure — it's finishing a migration that's already 90% done. Effort S each, ship together.
2. **Two missing indexes, one migration file each.** `DeliveryJob.declined_by` (JSONB `__contains`, polled every 5–15s by every online driver) and `AdminAuditLog` (paginated/sorted/pruned with zero indexes) are both full-table-scan patterns on tables that only grow. Cheapest possible fix, compounding payoff as data volume grows.
3. **Stop annotating reservation `.count()`-only queries with reminder-metrics joins.** Every reservations list/alert poll pays for a JOIN + GROUP BY + 3 subqueries to produce an integer a plain indexed `COUNT(*)` would give for free. S effort, no schema change.

**Hosting — the 3 biggest wins:**

1. **Same three query/index fixes above double as hosting-cost fixes.** The audit's own impact language is explicit: the AdminAuditLog scan and prune job burn "DB CPU/IO on a resource-constrained Coolify host," and the `declined_by` scan "becomes a real bottleneck as ... concurrent online drivers grow." Fixing these for speed also lowers DB load per request on the box the app is actually deployed on.
2. **Cache `AdminPlatformAnalyticsView`'s ~15 uncached aggregate queries** the same way another view in the same file already does (`_public_list_get_or_build`). Turns N admin dashboard loads/minute into ~one round of DB aggregation.
3. **This pass did not surface verified Docker/image, dependency, or ops-cost findings** — the prior audit's Dockerfile/compose/runtime backlog is already shipped (per `CLAUDE.md`). Treat hosting-efficiency-specific categories (image layers, dependency weight, worker tuning) as **not re-audited this round**, not as "clean" — a dedicated pass is the honest way to confirm that, not an inference from absence here.

**Frontend, worth doing but lower urgency:** cold-load is gated behind a network round-trip for the EN i18n chunk before `app.mount()`, and Sentry ships its Replay recorder in every page's vendor chunk even though replay sampling defaults to off. Both are self-contained frontend-only fixes (M effort).

---

## 2. Speed Backlog

Items marked **[VERIFIED]** were individually re-checked against the source in this audit; **[reported]** items were surfaced by the finder pass but not individually re-verified — treat as likely-correct, confirm before relying on the line numbers.

### 2A. Backend — Queries & Indexes

| Pri | Issue | Files | Fix | Impact | Effort |
|-----|-------|-------|-----|--------|--------|
| **H** [VERIFIED] | `DeliveryJob.declined_by` JSONB `__contains` full-table scan, hit by a driver endpoint polled every 5–15s by every online driver | `accounts/views.py:7778`, `accounts/models.py:985`, `accounts/dispatch.py:179-226` | Quick (S): add `GinIndex(fields=["declined_by"], name="deliveryjob_declined_gin")` to `DeliveryJob.Meta.indexes` + migration. Structural (M): replace the JSON-array scan with a small indexed `DeliveryJobDecline(job_id, driver_id)` table or a `Customer.declined_deliveries_count` counter bumped alongside the existing `declined_by` writes; keep `declined_by` itself for dispatch-exclusion, which it already serves well | Background cost today; becomes a real bottleneck as `DeliveryJob` rows and concurrent online drivers grow — every driver's earnings poll degrades together on the same unindexable predicate | S (quick) / M (structural) |
| **H** [VERIFIED] | Reservation `count()`/alert endpoints run on a reminder-metrics-annotated queryset — JOIN + GROUP BY + 3 subqueries just to produce an integer | `sales/views.py` (`OwnerReservationListView`, `_owner_reservation_counts()`, `AdminReservationAlertsView`, `OwnerReservationExportView`) | Add a lean `_owner_reservations_base_queryset(...)` (same filters, no `_with_reservation_reminder_metrics`) and use it for every `.count()`-only call site and the CSV export row source. Reserve the annotated version for the one place that actually serializes reminder fields | 9-10x more DB work than needed on every reservations-list page load and every admin alerts poll; cost scales with both Lead volume and per-lead reminder history, so it gets slower over time, not just under bigger tenants | S |
| **H** [VERIFIED] | `AdminAuditLog` has zero indexes despite being paginated/sorted/filtered and pruned by date on an unbounded, append-only public-schema table | `sales/models.py`, `sales/views.py`, `commands/prune_admin_audit_logs.py` | Add `Index(fields=["-created_at"], name="adminauditlog_created_idx")` + `Index(fields=["tenant","-created_at"], name="adminauditlog_tenant_created_idx")` to `Meta.indexes`. Build with `AddIndexConcurrently` + `atomic = False` (repo convention, see `backend/MIGRATIONS.md`) so the migration doesn't take an ACCESS EXCLUSIVE lock on deploy. Optionally index `action` if the exact-match filter is used often | Every admin audit-log page view does an unindexed sort + full-table count; the prune job does a full sequential scan+delete over the same growing table. Both worsen linearly as the platform accrues admin/money actions | S |
| **M** [reported] | Password-reset confirm scans and decodes every active Django session platform-wide to find one user's sessions | `accounts/serializers.py:197-216` | Either drop the loop and rely on `SessionAuthenticationMiddleware` invalidation (matches the existing comment's own reasoning), or maintain a lightweight indexed `UserSession(user_id, session_key)` mapping written at login | Rare today (password resets are infrequent) but cost scales with total platform session count, not reset volume — slows over time purely from user-base growth | S |
| **M** [reported] | Order-line creation loops per-row `.create()` instead of `bulk_create()` on every order placement | `menu/views.py`, `accounts/views.py`, `tests/test_happy_hour.py` | Replace per-item `.create()` loops with `OrderItem.objects.bulk_create([...])` (Postgres returns populated pks, nothing downstream breaks). Update the 4 `test_happy_hour.py` assertions from `.create.called` to `.bulk_create.called` | Cuts N sequential round-trips to 1 per order placed/appended; shortens the lock-hold window on the `select_for_update()` transaction that already guards the ordered dishes, reducing contention under concurrent checkouts on popular dishes | M |
| **L** [reported] | `enforce_subscriptions` cron issues up to 2 `Subscription` queries per active tenant instead of 2 total | `commands/enforce_subscriptions.py` | Batch into two set lookups before the loop (`valid_tenant_ids`, `any_sub_tenant_ids`); replace per-tenant `has_valid_subscription()` calls with `in` checks against the sets; reuse for the billing-suspended reactivation loop | O(N) query count today is cheap; will start costing measurable Celery-worker time and DB connection churn at hundreds of tenants — cheap to fix now, harder to unwind later | S |
| **L** [reported] | Tenant settings export defeats its own `prefetch_related` with a chained `.order_by()`, turning 3 queries into ~1+N+M | `sales/views.py`, `menu/models.py` | Drop the redundant `.order_by("position","name")` on `category.dishes.all()` (prefetch cache is already ordered via `Dish.Meta.ordering`); bake the desired order into the options prefetch itself (`Prefetch("dishes__options", queryset=DishOption.objects.order_by("id"))`) instead of re-querying after | 20 categories × 20 dishes = ~421 queries instead of 3. Admin-only, not a hot path, but a plausible source of request-timeout tickets on any tenant with a non-trivial menu | S |

### 2B. Backend — Caching & Async

| Pri | Issue | Files | Fix | Impact | Effort |
|-----|-------|-------|-----|--------|--------|
| **C** [VERIFIED] | Bulk order-confirm endpoint fires up to 50 sequential blocking SMTP sends inside the request | `menu/views.py:8556-8567`, `menu/views.py:4135-4218`, `accounts/tasks.py` | Add a Celery task `order_status_email(order_number, tenant_id, new_status)` mirroring the existing `campaign_email`/`customer_order_milestone` pattern — re-fetch the order under `schema_context`, reuse the existing email-building logic. Replace every direct `_send_order_status_email(...)` call with `enqueue(order_status_email_task, ...)`, exactly like the SMS branch 6 lines below already does (`menu/views.py:8424-8428`) | Owner-facing bulk-confirm can hang for minutes or hard-fail with a false 500 under any SMTP slowness; ties up a worker thread per concurrent bulk-confirm request during exactly the busy periods owners batch-confirm the most | S |
| **H** [VERIFIED] | Owner order-status-update endpoint sends the customer email synchronously while the SMS 6 lines below correctly goes through the async queue | `menu/views.py:8406-8409` | Reuse the task added above; replace the direct call at `menu/views.py:8409` with `enqueue(order_status_email_task, order.order_number, tenant.id, new_status)` | The busiest write endpoint in the app blocks its request/worker thread up to `EMAIL_TIMEOUT` (10s) whenever the customer has an email on file and SMTP is slow — slows the kitchen/owner UI ("mark ready", "mark out for delivery") during peak service and holds a worker slot the whole time | S |
| **H** [VERIFIED] | Customer phone-OTP send is a synchronous, un-queued Twilio call — inconsistent with every other SMS in the app | `accounts/views.py:995-1025`, `accounts/views.py:511-550`, `accounts/tasks.py` | Add `accounts.tasks.customer_otp_sms` (same shape as `sms_order_ready`); call via `enqueue()` from `CustomerPhoneRequestView` instead of calling `_send_otp` inline. Keep the DEBUG-mode console-log fast path unqueued (no network call) | Every OTP request (signup/login — conversion-critical, latency-sensitive) blocks the request thread on a live Twilio round-trip, up to 10s of dead time if Twilio is slow, unlike the rest of the app's notification paths | S |
| **M** [reported] | Five more ad hoc synchronous `send_mail()` calls bypass the async notification system | `accounts/views.py:1998-2030`, `accounts/views.py:6174-6210`, `accounts/ride_views.py:1369-1398`, `menu/views.py:530-559`, `menu/views.py:4100-4132` | Generalize the task above into `accounts.tasks.send_transactional_email(subject, message, from_email, recipient_list, tenant_id=None)`; replace each direct `send_mail(...)` call with `enqueue(send_transactional_email, ...)` | Individually lower-traffic than order-status, but each still ties up a request thread up to 10s on SMTP hiccups; the admin-fanout case (`_notify_admins_new_driver`) scales with admin count. Systemic pattern gap, not one-off — the async stack (dedupe, outbox durability, retry) already exists for this | S |

### 2C. Frontend — Bundle

| Pri | Issue | Files | Fix | Impact | Effort |
|-----|-------|-------|-----|--------|--------|
| **H** [VERIFIED] | `app.mount()` is gated behind a network round-trip for the EN locale chunk on every cold load | `src/main.js`, `i18n/localeLoader.js` | Keep the code-split chunk (don't re-inline EN into the entry bundle), but stop relying on runtime discovery: add a Vite `transformIndexHtml` build step reading the manifest to inject `<link rel="modulepreload" href="/assets/messages-en-<hash>.js">` into `index.html` so it fetches in parallel with `main.js`. Alternative: mount immediately with a minimal inline critical-path EN subset (nav/error strings) and hydrate the rest reactively — `catalog` is already `reactive({})`, so this needs no store rewrite, just accepting a brief raw-key flash | ~1 extra network RTT + parse time for a ~200KB chunk before first paint on every cold visit, across all four personas — pure added latency on already-slow mobile networks in the target market, compounding with the extra non-EN fetch for FR/AR visitors (`localeLoader.js:99-107` awaits EN first even for AR) | M |
| **H** [VERIFIED] | Sentry's Replay recorder ships in every page load's vendor-sentry chunk even though replay sampling defaults to 0 (off) | `lib/sentry.js`, `src/main.js` | Use Sentry's documented lazy-loading pattern: import only `init`/`browserTracingIntegration` eagerly; load Replay via `Sentry.lazyLoadIntegration('replayIntegration')` (or a separate dynamic `import()` of just the replay entry point), gated on the same condition that decides sampling is actually on | Ships recorder code (and its bundle weight) to 100% of page loads for a feature that's off by default for essentially all of them — dead weight on every cold load, worst on the same slow mobile connections the EN-chunk finding above already flags | M |

### 2D. Frontend — Runtime

No verified or reported findings in this category this pass — not confirmed clean, just not covered by this round of finders. If frontend runtime perf (re-renders, watcher cost, list virtualization) matters for the next planning cycle, run a dedicated pass rather than assuming absence-of-finding means absence-of-issue.

---

## 3. Hosting Efficiency Backlog

**Coverage note up front:** this fan-out surfaced exactly one finding explicitly tagged `hosting` (3E below). The Docker/image, dependency-weight, and ops-cost categories below are carried over from the 2026-06-07 audit for continuity — per `CLAUDE.md` that backlog already shipped (multi-stage Dockerfile, `CONN_HEALTH_CHECKS`, etc.) — and are **not re-verified in this pass**. Don't treat their absence here as "already optimal"; it means this round didn't look. Section 3D cross-lists the 2A/2B items above whose own impact language explicitly names DB-host resource cost, since those genuinely are hosting-efficiency findings, not just speed ones.

### 3A. Docker / Image

No new findings this pass. Prior backlog item (multi-stage backend build removing `build-essential` from the final layer) shipped per `CLAUDE.md`. If image size/build-time needs re-checking (e.g. after dependency additions since), that's a fresh, scoped pass — not inferable from this audit.

### 3B. Server Runtime & Static / Media

No new findings this pass. Prior items (`CONN_HEALTH_CHECKS`, worker-count tuning, Redis presence check) shipped per `CLAUDE.md`.

### 3C. Dependencies

No new findings this pass.

### 3D. Multi-Tenant Scale (cross-listed from Speed — these genuinely are hosting-cost findings)

| Pri | Issue | Files | Fix | Hosting-cost angle | Effort |
|-----|-------|-------|-----|---------------------|--------|
| **H** [VERIFIED] | `AdminAuditLog` unindexed sort/count + unindexed prune scan | `sales/models.py`, `sales/views.py`, `commands/prune_admin_audit_logs.py` | See 2A | Explicitly named in the audit as increasing "DB CPU/IO on a resource-constrained Coolify host" on every admin page view and every prune run, worsening linearly as admin/money-action volume grows | S |
| **H** [VERIFIED] | `DeliveryJob.declined_by` unindexed JSONB scan on a 5-15s driver poll | `accounts/models.py:985`, `accounts/dispatch.py` | See 2A | Every online driver hits the same growing table with the same unindexable predicate — DB load scales with fleet size × poll frequency, not just data volume | S |
| **H** [VERIFIED] | Reservation `.count()`-only queries paying for a JOIN+GROUP BY+3-subquery annotation | `sales/views.py` | See 2A | 9-10x DB work on a query pattern hit by every reservations page load and every admin alerts poll — direct DB-host CPU cost, independent of the speed win | S |

### 3E. Ops Cost

| Pri | Issue | Files | Fix | Impact | Effort |
|-----|-------|-------|-----|--------|--------|
| **M** [reported] | `AdminPlatformAnalyticsView` runs ~15 uncached full-table aggregate queries on every dashboard load, despite an existing caching pattern in the same file | `accounts/views.py:7982-8191`, `accounts/views.py:3684` | Wrap the aggregation in the existing `_public_list_get_or_build(cache_key, build_fn)` helper (or `cache.get_or_set` with a 30-60s TTL) — an admin dashboard tolerates that staleness easily | Turns N admin page-loads/minute into effectively one DB round of aggregation; keeps the page fast as core tables grow instead of degrading with data volume | S |

---

## 4. Recommended Sequencing

### Phase 1 — Quick wins (high impact, low effort; ship together as one batch)

1. **Wire the three sync-email/SMS call sites through `enqueue()`** — bulk order-confirm (critical), owner order-status-update, customer OTP SMS. Same task pattern, same fix, three call sites (`menu/views.py:8409`, `menu/views.py:8556-8567`, `accounts/views.py:995-1025`).
2. **Add the two missing indexes** — `deliveryjob_declined_gin` (GIN on `declined_by`) and the two `AdminAuditLog` indexes — each a single migration file, use `AddIndexConcurrently` for `AdminAuditLog` per repo convention.
3. **Split the reservation queryset** — lean `_owner_reservations_base_queryset()` for every `.count()`-only call site in `sales/views.py`.
4. **Cache `AdminPlatformAnalyticsView`** with the existing `_public_list_get_or_build` helper — same file, same pattern already used elsewhere.

### Phase 2 — Needs-confirmation items (medium/low, verify line numbers before scheduling)

5. Batch `enforce_subscriptions` cron queries; fix the tenant-export `prefetch_related` self-defeat; drop or replace the password-reset session scan; `bulk_create()` for order-line creation (also update the 4 `test_happy_hour.py` mock assertions); the remaining 5 synchronous `send_mail()` call sites via a generalized `send_transactional_email` task.

### Phase 3 — Frontend bundle (self-contained, do independently of backend work)

6. Modulepreload (or critical-subset-inline) the EN i18n chunk so `app.mount()` isn't gated behind it.
7. Lazy-load Sentry Replay via `lazyLoadIntegration('replayIntegration')` instead of bundling it unconditionally.

### Phase 4 — Structural (larger effort, real payoff at scale)

8. Replace the `declined_by` JSON-array-scan pattern with an indexed `DeliveryJobDecline` table or counter, once the GIN-index quick fix (step 2) is no longer enough.

### Not scheduled — needs a dedicated pass, not inferable from this audit

9. Docker/image size, dependency weight, frontend runtime perf, and general ops-cost review — this fan-out did not produce verified findings here; the coverage note in Section 3 explains why. Re-audit these specifically before assuming they're clean, especially since dependencies have moved since the 2026-06-07 baseline.

---

## 5. Verification Status

### Verified [8 findings — individually re-checked against source in this audit session]

- Bulk order-confirm: up to 50 sequential blocking SMTP sends inside the request — `menu/views.py:8556-8567`, `menu/views.py:4135-4218`
- Owner order-status-update: synchronous customer email while SMS 6 lines below is async — `menu/views.py:8406-8409`
- Customer phone-OTP: synchronous, un-queued Twilio call — `accounts/views.py:995-1025`, `accounts/views.py:511-550`
- `DeliveryJob.declined_by`: unindexed JSONB `__contains` scan on a driver-polled endpoint — `accounts/views.py:7778`, `accounts/models.py:985`, `accounts/dispatch.py:179-226`
- Reservation `.count()`/alert endpoints: reminder-metrics-annotated queryset used for count-only calls — `sales/views.py`
- `AdminAuditLog`: zero indexes on a paginated/sorted/pruned unbounded table — `sales/models.py`, `sales/views.py`, `commands/prune_admin_audit_logs.py`
- `app.mount()` gated behind EN locale chunk network round-trip — `src/main.js`, `i18n/localeLoader.js`
- Sentry Replay recorder bundled unconditionally despite default-off sampling — `lib/sentry.js`, `src/main.js`

### Reported, not individually re-verified [13 medium/low findings — treat as likely-correct, confirm line numbers before scheduling]

- `AdminPlatformAnalyticsView` ~15 uncached aggregate queries — `accounts/views.py:7982-8191`
- Password-reset confirm scans every active session platform-wide — `accounts/serializers.py:197-216`
- Order-line creation loops `.create()` instead of `bulk_create()` — `menu/views.py`, `accounts/views.py`, `tests/test_happy_hour.py`
- `enforce_subscriptions` cron issues up to 2N queries instead of 2 — `commands/enforce_subscriptions.py`
- Tenant settings export defeats `prefetch_related` with a chained `.order_by()` — `sales/views.py`, `menu/models.py`
- Five more ad hoc synchronous `send_mail()` call sites — `accounts/views.py:1998-2030`, `accounts/views.py:6174-6210`, `accounts/ride_views.py:1369-1398`, `menu/views.py:530-559`, `menu/views.py:4100-4132`

**Raw totals from the fan-out, for context:** 43 findings before verification (1 critical, 16 high, 16 medium, 10 low). This document carries full detail for the 8 verified high/critical findings plus the ~13 medium/low findings surfaced with enough detail to act on. The remaining ~22 findings (mostly the rest of the 16 high + 16 medium + 10 low buckets) were not surfaced with actionable detail in this audit's output and are not included here rather than guessed at — re-run the finder pass with full output capture if the complete list is needed.

### Dismissed False Positives

1. **"Frontend production image is built with a Node major (26) that CI never tests — the exact `npm ci`/`vite build` that ships to prod is unvalidated."** — Refuted. `ci.yml` has a `docker` job (lines 388-447) on every push/PR to `main`, unrestricted by the frontend job's Node-22 setup, that runs `docker build -t kepoli-frontend:ci ./frontend` (line 413) against the real `frontend/Dockerfile`, which pins `FROM node:26-alpine AS build` and runs the identical `npm ci` + `npm run build` (Dockerfile lines 31-35) — the actual artifact-producing path that ships to prod. The job then boots the built nginx image and polls `/health` (lines 430-444), so the Node-26 build is both executed and verified to boot. The proposed remedy ("add a CI leg that builds via `docker build` on the real Dockerfile") already exists verbatim as this job — the finding only inspected the `frontend` job's Node-22 `setup-node@v4` step and the `e2e` job's Node-20 step, missing the separate `docker` job. A narrow residual point survives: lint/test run under Node 22 while the prod artifact builds under Node 26, so a Node-major-specific lint/test *behavior* difference (not build-breakage) could theoretically diverge — materially weaker than the finding's actual headline claim and not worth actioning as stated.
