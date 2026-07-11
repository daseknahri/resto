# Kepoli — Risk Register (known structural debt)

> The honest output of a ground-up, 11-dimension adversarial architecture review
> (2026-07-10). Every future session should read this **before** a scaling or onboarding
> push, so nobody rediscovers this debt the hard way. Items are ranked by severity; each has
> a concrete failure scenario, the fix, and a rough effort. When you close one, strike it
> through and note the commit.
>
> **Overall verdict:** the architecture is **not poor** — it is genuinely good craftsmanship
> for a small team, with debt concentrated in a few foundational places. The items below are
> that concentrated debt. Fix the 3 critical items before onboarding paying tenants at volume.
>
> Effort key: **S** = hours · **M** = a few days · **L** = weeks · **XL** = multi-week project.

---

## Summary (ranked)

| ID | Area | Sev | One-line | Effort |
|---|---|---|---|---|
| **AUTHZ-1** | Auth | ◑ Partial | Authorization by-convention on a shared cross-subdomain cookie → forgotten guard = cross-tenant breach. **Backstop middleware shipped** (foreign-tenant staff sessions downgraded to anonymous); policy layer + IDENTITY-1 remain | L |
| **OPS-1** | DR | 🔴 Critical | Single Postgres, no replica/PITR → ~24h RPO, money loss on host failure | M |
| **OPS-2** | DR | 🔴 Critical | Backups written on-host, not off-box → VPS loss = DB + backups lost together | S |
| ~~**MONEY-1**~~ | Money | ✅ Done | ~~No balance-vs-ledger reconciliation → silent wallet drift~~ — `reconcile_wallet_balances` shipped (detect-only on Beat, `--fix` for triage) | ~~S–M~~ |
| **IDENTITY-1** | Auth | 🟠 High | Dual identity: customer lives in `session`, invisible to DRF → forces manual checks | L |
| **STRUCT-1** | Structure | 🟠 High | God-files (13.4k / 8.7k lines), no `OrderService`, 574-line order method | L |
| **TEST-1** | Testing | ✅ Done | count-floor + DB-fail-not-skip + Playwright E2E in CI + **real threaded money/isolation DB tests** (MFA DB tests un-skipped). Residual: de-mock a low-value tail (cleanup, not risk) | M |
| **DATA-1** | Data | 🟠 High | Loose cross-schema refs, no orphan protection, no `Order` delete handler | M |
| **API-1** | API | 🟠 High | No API versioning → can't evolve safely once a client is pinned | S (now) / XL (later) |
| **ASYNC-2** | Async | 🟠 High | One generic cron task on a shared 2-worker queue → sweeps starve notifications | M |
| **ASYNC-1** | Async | 🟠 High | Inline task fallback loses queued work on every deploy restart, no retry | M |
| **MULTITENANCY-1** | Tenancy | 🟠 High* | Schema-per-tenant caps scale (O(N) migrations, no PgBouncer, atomic-index landmine) | XL |
| ~~**MONEY-2**~~ | Money | ✅ Done | ~~Driver-payout "owed" check reads an unlocked aggregate → double-pay race~~ — driver row now locked in `record_driver_payout` | ~~S~~ |
| ~~**MONEY-3**~~ | Money | ✅ Done | ~~Dormant Stripe webhook would credit metadata, not settled `amount_total`~~ — now credits `amount_total`, paid-only | ~~S~~ |
| **OPS-3** | Ops | 🟡 Med | One Redis SPOF; sessions cache-only (eviction logs users out) — ⚠️ naive `cached_db` fix BREAKS (django-tenants schema); needs a schema-pinned backend | M |
| **ASYNC-3** | Async | 🟡 Med | WS + full-rate polling both run → realtime cost without the load savings | M |
| **ASYNC-4** | Async | 🟡 Med | `acks_late` + no reject-on-worker-lost + no DLQ → duplicate SMS/email on worker loss | S |
| **FE-1** | Frontend | 🟡 Med | i18n dual-source: 4 coordinated edits per string → raw-key bugs | M |
| **FE-2** | Frontend | 🟡 Med | Six 2,500–3,700-line page components (single-writer bottleneck) | L |
| **FE-3** | Frontend | 🟡 Med | ~500KB locale catalogs block first paint; Sentry not lazy | S–M |
| **SER-1** | API | 🟡 Med | 242 raw `request.data` reads vs 41 serializer writes → validation/price-manip class | L |
| **SCHEMA-1** | API | 🟡 Med | OpenAPI via legacy `generateschema` → duplicate operationIds, unusable for client-gen | S |
| **DATA-2** | Data | ◑ Partial | `CustomerOrderRef` mirror had no `post_delete` (phantom orders) — **fixed**; item-mutation re-mirror + periodic reconcile remain | S |
| **DATA-3** | Data | 🟡 Med | `Dish` + 4-key JSON is not a real multi-vertical catalog | L |
| ~~**DATA-4**~~ | Data | ✅ Done | ~~Directory opt-in fields nullable with no "opt-in requires them" rule~~ — serializer now requires city+coords to opt in | ~~S~~ |
| **DATA-5** | Data | 🟡 Med | Four denormalized `Profile` mirrors kept by scattered signals → drift on a missed one | M |
| **STRUCT-2** | Structure | 🟡 Med | 215 migrations, `Order` field sprawl, no squashing → slow per-schema deploys | M |
| **API-2** | API | 🟢 Low | Contract sprawl / inconsistent naming / RPC verbs in 3 god url-files | M |
| **OPS-4** | Ops | 🟢 Low | ⏭️ Re-scoped — `daphne` is a registered `INSTALLED_APP` (ASGI runserver), NOT dead weight; removing it is a dev-tooling change, not a freebie | S |

\* MULTITENANCY-1 is "high" as a *strategic* decision to make consciously, not an urgent bug.

---

## 🔴 Critical

### AUTHZ-1 — Authorization is a copy-pasted convention on a shared cookie
**Where:** ~198 of ~262 endpoints (no permission class); `_is_tenant_owner` duplicated in
`menu/views.py` and `accounts/views.py` (divergent signatures) + predicate in 5+ places;
`SESSION_COOKIE_DOMAIN = ".<suffix>"`.
**Failure scenario:** A developer adds an owner endpoint and forgets the
`if not _is_tenant_owner(request): return 403` line (or writes a bespoke check that validates
the *role* but not `tenant_id` — exactly the Z-report bug). Because the session cookie is valid
on every tenant subdomain, an authenticated owner of tenant A changes one id in the URL and
reads tenant B's revenue, PII, and customer list. The Z-report leak and order-status IDOR we
already fixed were symptoms of this class, not isolated bugs.
**Fix:** (1) Unify identity — see IDENTITY-1 — so customers are `request.user`. (2) Replace the
inline guards with **one tested policy module**: `IsTenantMember`, `IsTenantOwner` (always
tenant-match), `IsOrderOwner`, `IsPlatformAdmin`, applied via `permission_classes` +
`has_object_permission` on detail views. Delete both `_is_tenant_owner` helpers. (3) Add a
**defense-in-depth backstop**: a `TenantScopedManager` (or middleware assertion) so any
public-schema object returned must carry `tenant_id == request.tenant.id` — a forgotten filter
becomes a fail-closed no-op instead of a leak.
**Effort:** L. Do it in slices (backstop first — it protects everything immediately).
**Progress (slice 1 — backstop, 2026-07-10):** `CrossTenantSessionGuardMiddleware`
(`config/middleware.py`, registered after `AuthenticationMiddleware`) now **downgrades to
anonymous** any tenant-owner/staff session on a *foreign* tenant's host (mismatched or null
`user.tenant_id`), so a forgotten per-view guard fails closed (401/403) instead of leaking —
the Z-report/IDOR class is dead app-wide. A downgrade rather than a 403 because the shared
cookie makes "owner of A browsing restaurant B as a guest" the normal case; superusers and
platform admins are exempt (matching `_is_tenant_owner`/`IsPlatformAdmin`); sessions are not
flushed (customer identity may share the session). Logged as `cross_tenant_session_downgraded`.
Tests: `tests/test_cross_tenant_session_guard.py` (13, no DB). A query-level backstop
(scoped manager) was evaluated and deliberately **deferred**: an inventory of all public-model
call-sites found the unscoped majority is *legitimately* cross-tenant (driver app, customer
marketplace, wallet ledger, admin, reconcile/GDPR commands), so auto-scoping would break the
app for marginal gain; revisit after IDENTITY-1 lands. The one flagged query
(`menu/views.py` CustomerRating average) is by-design platform-wide (per model docstring) and
now commented as such.
**Remaining:** (1) IDENTITY-1, (2) the policy-class layer (`IsTenantOwner` etc.) + delete both
`_is_tenant_owner` helpers.
**Source:** API/auth review (rated the authz *architecture* **poor**), security-isolation review.

### OPS-1 — Single Postgres, no replica, no PITR
**Where:** `docker-compose.coolify.yml` (one `postgres` service); no WAL archiving/replica.
**Failure scenario:** The VPS disk fails at 14:00. The last dump ran at 02:00. Every wallet
top-up, order, and payout from the last 12 hours is gone — unrecoverable. Your own runbook
already admits "customers may need manual wallet adjustments." For a money app this is
business-ending, not "degraded."
**Fix:** Enable continuous WAL archiving / PITR (e.g. `pgBackRest` or a managed Postgres with
PITR), and/or a streaming replica. Target RPO ≤ 5 min for the money tables.
**Effort:** M.
**Source:** ops/scale review (CRITICAL).

### OPS-2 — Backups live on the same host they protect
**Where:** backup scripts write to local disk on the VPS.
**Failure scenario:** The VPS is lost (provider incident, ransomware, accidental teardown).
The database *and* every backup vanish together. A backup you can't reach when the host is
gone is not a backup.
**Fix:** Ship every backup **off-box** immediately after creation (S3-compatible object store
with versioning + lifecycle + a restore drill). This single change also materially mitigates
OPS-1's blast radius.
**Effort:** S. **This is the cheapest critical fix — do it first.**
**Source:** ops/scale review (CRITICAL).

---

## 🟠 High

### MONEY-1 — No `balance == sum(ledger)` invariant  ✅ ADDRESSED (2026-07-10)
**Where:** `Customer.wallet_balance` / `Tenant.float_balance` (denormalized) vs
`WalletTransaction` / `TenantFloatTransaction` (journals). No reconciliation job.
**Failure scenario:** A process crashes between writing the journal row and updating the
denormalized balance (or any code path updates one without the other). The balance silently
drifts from the ledger. Nothing detects it; it compounds; the first symptom is a customer
dispute you can't explain.
**Resolution:** `accounts/management/commands/reconcile_wallet_balances.py` reconciles both
ledgers by asserting `balance == balance_after of the latest ledger row` — a **sign-agnostic**
anchor (`amount` is a positive magnitude and `adjustment` can go either way, so summing signed
amounts is ambiguous; the recorded `balance_after` is not). Categories: OK / **DRIFT** (fixable)
/ **ORPHAN** (non-zero balance, no ledger — never auto-fixed) / **CHAIN** (`--deep`: a row whose
balance step ≠ its amount). Default mode is read-only detect + alert (on the `payments` channel);
`--fix` repairs only the unambiguous DRIFT case under the wallet service's `select_for_update`
lock, re-checking under the lock. Scheduled on Beat every 6h **detect-only** (Beat never
auto-mutates money; a human runs `--fix` after triage). Verified: every active ledger writer
(service + loyalty redeem + admin bulk bonus) sets `balance_after` to the persisted balance, so
the check does not false-positive. Tests: `tests/test_reconcile_wallet_balances.py` (7, green on
Postgres).
**Source:** money review, data-model review.

### IDENTITY-1 — Two disjoint identity systems; the customer is invisible to DRF
**Where:** staff → `request.user` (SessionAuth); customer → `request.session["customer_id"]`
(~49 raw reads in `accounts/views.py`), never in `request.user`.
**Failure scenario:** You *cannot* write an `IsOrderOwner` permission class for customer
resources because the permission layer can't see the customer — so ownership is forced into
every handler body and into response-shaping. This is the structural reason AUTHZ-1 exists and
why the order-status IDOR was possible.
**Fix:** A `CustomerSessionAuthentication` DRF auth class that hydrates `request.user` from
`session["customer_id"]` (or a custom auth backend). Then customers, staff, owners, drivers,
and admins all flow through one auth stack — the prerequisite for AUTHZ-1's policy layer.
**Effort:** L (touches ~60 customer views), but it's the keystone.
**Source:** API/auth review.

### STRUCT-1 — God-files and no `OrderService`
**Where:** `menu/views.py` = **13,380 lines / 110 classes** across 8 domains;
`accounts/views.py` = 8,742; `PlaceOrderView.post` = a **574-line method** doing
stock+loyalty+promo+wallet inline with locally-defined exception classes; **618 function-local
imports** exist only to dodge circular deps between the two fat files.
**Failure scenario:** The crown-jewel order path is raw inside an HTTP handler (contrast the
clean `wallet_service`). Every change risks a regression in an unrelated concern; onboarding a
new engineer means reading a 13k-line file; the circular-import web makes refactoring scary.
**Fix:** Extract `OrderService` (place/modify/cancel/refund) as a tested domain service, then
split the god-files by bounded context (orders / catalog / dine-in / analytics / admin). The
618 local imports mostly dissolve once the files are split.
**Effort:** L. Start with `OrderService` — highest value, and it de-risks the money path.
**Source:** backend-structure review.

### TEST-1 — Test suite gives false confidence  ✅ ADDRESSED (2026-07-10)
**Where:** mock-heavy `SimpleTestCase`s that patch `WalletTransaction.objects`,
`transaction.atomic`, `select_for_update`; DB tests self-skip when Postgres is absent;
Playwright E2E specs exist but aren't wired into CI; no test-count floor.
**Failure scenario:** The tests that "cover" money and isolation actually patch the very
machinery they claim to protect — they verify Python control flow, not the invariant. One CI
infra hiccup and DB tests silently skip, CI goes green with zero DB tests run, and a real
concurrency/isolation regression ships.
**Fix:** (1) Make DB tests **fail, not skip**, when the DB is absent in CI. (2) Wire the
Playwright E2E (incl. the cross-subdomain-CSRF spec) into CI. (3) Add a **test-count floor**
so a collection error can't silently drop tests. (4) Convert the highest-value money/isolation
mocks into real DB integration tests.
**Resolution (item 3, 2026-07-10):** the CI "Backend tests" step now asserts a floor on
`passed` (≥ 4000) and a ceiling on `skipped` (≤ 100) parsed from the pytest summary — a collection
error or a mass DB-self-skip (the exact false-green this warns about) now fails CI instead of
passing with a silently shrunken suite. Parsing validated locally against real/edge summaries.
**Resolution (item 1, 2026-07-10):** CI now sets `PYTEST_REQUIRE_DB=1`; `tests/conftest.py`
aborts the whole session (`pytest_sessionstart`) if Postgres is unreachable, and the per-file
availability guards re-raise instead of skipping. **Bonus root-cause find:** the old in-file probe
(`django.db.connection.ensure_connection()` at import) *always* raised under pytest-django's
access blocker — so the 24 MFA DB tests (`test_mfa_totp.py` B1–B7) had **never actually run in
CI** (they were the mysterious "24 skipped" baseline). The probe now connects via the raw
psycopg2 driver (`tests/_dbprobe.py`), so those tests execute in CI for the first time — and
that first run exposed that all 24 were **written but never validated**: they drove the full
`APIClient` stack against the default host `testserver`, which is neither a tenant domain nor a
`PUBLIC_SCHEMA_HOST`, so every request 404'd at the tenant middleware before reaching a view.
Fixed by pointing the client at the public host `localhost` (the MFA/login endpoints live in the
shared urlconf and never read `request.tenant`); the 24 now exercise the real enrollment / login-
gate / verify / disable flows.
**Resolution (item 2, 2026-07-10):** a new `e2e` CI job (`.github/workflows/ci.yml`, gated on the
backend+frontend jobs) stands up the real stack — Postgres, `migrate_schemas`, `seed_plans
--with-demo` (creates the `demo` tenant + admin + owner), `runserver` on :8000, Vite dev on :5173,
`demo.localhost` mapped to loopback — and runs the Playwright specs. **Split gate:**
`cross-subdomain-auth-csrf` (the security/isolation + CSRF regression this item names) **and**
`mobile-breakpoint-regression` (390px no-horizontal-overflow QA invariant) are **blocking**;
`critical-saas-flow` (the fragile full onboarding journey) runs **informational**
(`continue-on-error`). The e2e job's first green run also surfaced real pre-existing debt the specs
were built to catch — both now **fixed**: an `AddIndexConcurrently`-vs-provisioning 500 (see
MULTITENANCY-1) and a **390px horizontal overflow on `/owner/onboarding`** (contained by a
`Wizard.vue` `overflow-x-clip` guard after the overflow proved data-dependent and
non-reproducible locally; the mobile spec was then promoted to blocking).
Traces/screenshots/server logs upload as artifacts on every run.
**Resolution (item 4, 2026-07-10):** the load-bearing money/isolation invariant the mocks could
never verify — that the `select_for_update` row lock and the under-lock idempotency re-check
actually serialize *concurrent* writers — is now covered by real multi-threaded DB tests
(`tests/test_money_concurrency.py`): concurrent same-key credit (must apply once, no unique-key
500), concurrent debits (no overspend / negative balance), concurrent credits (no lost update),
and concurrent driver payouts (no double-pay past `owed`, RISK MONEY-2). Each worker runs on its
own connection, released together by a barrier so they genuinely contend; assertions are
deterministic on correct code and only fail when the lock is broken. Both `test_wallet_service.py`
and `test_driver_payout_service.py` had explicitly flagged this as un-coverable single-threaded —
that gap is now closed. **Residual (low value):** a tail of older tests still mock `transaction.atomic`
/ `select_for_update` (e.g. `test_a4_marketplace_cod.py`, `test_bulk_order_status.py`); they now
duplicate control-flow coverage the real DB tests provide, so de-mocking them is cleanup, not risk.
**Effort:** M (remaining). **Source:** testing/CI review.

### DATA-1 — Cross-schema refs have no orphan protection
**Where:** `(tenant_id, order_number)` on `DeliveryJob`, `WalletTransaction`, `CustomerOrderRef`,
`CustomerRating`; **no `Order` `post_delete` handler anywhere**; `order_number` is only
tenant-unique.
**Failure scenario:** An `Order` is hard-deleted or its tenant schema is dropped. A
`DeliveryJob` still carries `driver_payout` and feeds `reconcile_driver_earnings` → a driver is
paid for a delivery whose order no longer exists, with no FK to catch it. Separately, any code
that ever queries these public tables by `order_number` **without** `tenant_id` cross-contaminates
restaurants.
**Fix:** Make `order_number` **globally unique** (`{tenant_id}-{seq}` or UUID) so public refs need
one column and can't cross-contaminate; add a reconciliation job for orphaned refs (generalize
`reconcile_driver_earnings`); add an `Order` soft-delete convention + `post_delete` cleanup.
**Effort:** M.
**Source:** data-model review.

### API-1 — No API versioning
**Where:** zero versioning (URL/header/namespace) across all routes; no `VERSIONING` setting.
**Failure scenario:** A PWA/mobile-web client caches an old bundle (service workers persist for
hours/days). You ship a breaking response-shape change; in-flight clients break with no
negotiation path. The moment there's a store-distributed native app (the rides/delivery
ambition implies one), old versions are pinned in users' hands and you **cannot** force-upgrade.
**Fix:** Introduce `/api/v1/` (`URLPathVersioning`) **now**, while there's one client and it's
trivial. Retrofitting after a client is pinned is near-impossible.
**Effort:** S now / XL if deferred.
**Source:** API/auth review.

### ASYNC-2 — One generic cron task on a shared 2-worker queue
**Where:** `run_management_command` (single task, 23-entry allowlist) wired to ~23 beat entries;
`--concurrency 2`; no `CELERY_TASK_ROUTES`; the sweep task has no retry decorator.
**Failure scenario:** A slow `sweep_delivery_jobs` (the dispatch heartbeat) occupies one of the
two worker slots; because every cron and every push notification share the single default queue,
customers' "order ready" SMS are starved behind it. And the sweeps carry no retry, so a
transient DB blip during a tick just drops that tick.
**Fix:** Replace the generic task with named `@shared_task`s per command; add `task_routes` so
sweeps go to a `cron` queue and notifications to their own; add retry/backoff to sweeps. The
task name *becomes* the allowlist, deleting the drift-prone parallel list.
**Effort:** M.
**Source:** async/realtime review.

### ASYNC-1 — Inline fallback loses work on restart
**Where:** `accounts/tasks.py` `enqueue()` — when `CELERY_BROKER_URL` is unset (a likely default),
tasks run on an in-process `ThreadPoolExecutor`; `.run()` bypasses `autoretry_for`; the pending
queue is unbounded and evaporates on process exit.
**Failure scenario:** Every deploy does a rolling uvicorn restart. Any inline task still queued
(a `charge_request` money-nudge, an `sms_order_ready`) is dropped with no record and no retry.
The docstring claims "durable, survives restarts" — true only in the broker branch, which may
not be running.
**Fix:** Make the broker **required in production** (fail-closed if unset), or give the inline
path a durable outbox. At minimum, document that inline mode is dev-only and assert a broker in
prod boot.
**Effort:** M.
**Source:** async/realtime review.

### MULTITENANCY-1 — Schema-per-tenant caps the ambition (decide consciously)
**Where:** `TENANT_APPS = [..., menu]`; django-tenants; the money layer pulled into `public`.
**Failure scenario (at scale):** (a) Every deploy runs each of 76 `menu` migrations **per
schema** — at hundreds of tenants a migration window is an operational hazard; (b) can't use
PgBouncer transaction-pooling (`SET search_path` is session state) → connection ceiling; (c)
O(N-schema) analytics; (d) a ~~**latent landmine**~~ **REALIZED then fixed (2026-07-11)**:
provisioning wrapped schema creation in `transaction.atomic()`, but the shipped index migrations
(`menu/0060`, `0062`, `0066` — `AddIndexConcurrently`) **cannot run in a transaction**, so **every
new tenant signup 500'd**. It was dormant only because no tenant had been provisioned since those
migrations shipped; the new **e2e CI job surfaced it** (first thing in CI to create a tenant). Fixed
in `sales/services.provision_lead` and `seed_plans --with-demo`: create the tenant ROW inside the
txn with `auto_create_schema=False`, then `create_schema()` **after commit** (outside any txn); a
schema-build failure rolls the tenant back (deletes it so the slug frees) and marks the
`ProvisioningJob` FAILED. Tests: `tests/test_provision_schema_deferral.py` (deferral + rollback) +
updated `test_seed_plans_command.py`; the success path is exercised end-to-end by the e2e job. The
broader items (a)–(c) remain the conscious scaling decision below.
**Fix / decision:** This is a *conscious decision*, not an urgent patch. If your true ceiling is
**low-hundreds of premium tenants**, schema-per-tenant is fine — keep it. If you genuinely target
**thousands**, plan a migration to **shared-schema + Postgres Row-Level Security** — which your
money layer already proves works. Do not rewrite now; **decide the ceiling** and record it in
[ADR-0001](adr/0001-schema-per-tenant.md).
**Effort:** XL (only if you choose to migrate).
**Source:** multitenancy review, data-model review.

---

## 🟡 Medium

### MONEY-2 — Driver-payout "owed" check is unlocked  ✅ ADDRESSED (2026-07-10)
**Where:** `accounts/driver_service.py` `record_driver_payout`, which aggregated "owed"
(`earned − sum(payouts)`) without a row lock.
**Failure scenario:** Two concurrent payout requests both read the same "owed" total before
either writes → double payout.
**Resolution:** `record_driver_payout` now acquires `Customer.objects.select_for_update()` on the
driver row before (re)computing owed and creating the `DriverPayout`, so concurrent settlements
serialize — the second recomputes owed *including* the first's committed payout. Idempotency is
also re-checked under the lock (a concurrent same-key request replays instead of racing a second
insert that would 500 on the unique key). An adversarial review added two further hardenings to
match the wallet-service discipline: a **cross-driver idempotency-key collision guard** (a
caller-supplied key resolving to another driver's payout is refused, not silently handed back),
and a **fail-closed** check if the driver row is absent (so the mutex can't be a silent no-op).
Mirrors the wallet-service discipline; single-row lock, so no new deadlock ordering. Tests:
`tests/test_driver_payout_service.py` (6, green on Postgres).
**Source:** money review.

### MONEY-3 — Dormant Stripe webhook trusts metadata  ✅ ADDRESSED (2026-07-10)
**Where:** `accounts/views.py` `CustomerTopUpWebhookView`, which credited `metadata.amount`
(the *requested* amount echoed back), not the settled amount.
**Failure scenario (when PSP goes live):** a partial/adjusted (or, without a signing secret,
tampered) session credits the wrong amount.
**Resolution:** the webhook now credits the **settled `amount_total`** Stripe reports (minor units
→ MAD), only for sessions with `payment_status == "paid"`, falling back to metadata only when
`amount_total` is absent (older events). Signature verification (when `PSP_STRIPE_WEBHOOK_SECRET`
is set) and event-id idempotency (`stripe:<event_id>`) were already in place; the docstring still
flags that the secret is **required in production**. Still dormant (`PSP_TOPUP_ENABLED=False`) —
this hardens it before go-live. Tests: `tests/test_psp_topup.py` (+3, incl. amount_total-wins and
unpaid-no-credit; 10 total, no DB needed).
**Source:** money review.

### OPS-3 — One Redis backs four subsystems
**Where:** `REDIS_URL` = cache + sessions + Channels layer + optional broker; 256 MB cap.
**Failure scenario:** A WS fan-out spike or the 256 MB ceiling triggers eviction → cached
idempotency mutexes/throttle counters vanish **and** sessions get evicted, logging users out
mid-shift.
**Fix:** Move sessions off the cache, then split the broker onto its own instance at first contention.
**⚠️ GOTCHA (verified 2026-07-10):** the naive `SESSION_ENGINE = cached_db` swap **breaks prod** here —
django-tenants switches the connection to the *tenant* schema during middleware unwind, and
`django_session` lives only in `public`, so a `cached_db` write 500s on every authenticated request
(the team documented this at `config/settings.py` ~L409). The real fix is a **schema-pinned session
backend** (force `schema_context("public")` around session DB writes) or **signed-cookie sessions**
(size/invalidation tradeoffs) — a deliberate custom component, not a one-line setting.
**Effort:** M. **Source:** async/realtime review.

### ASYNC-3 — Realtime and polling both run at full rate
**Where:** `OrderStatus.vue` polls every 15s even when the WS is live; `OwnerOrders.vue` polls
15s and doesn't instantiate the (already-built) `useOwnerRealtime` at all.
**Failure scenario:** You pay for `channels_redis` + WS fan-out **and** keep full-rate polling —
backend request volume is ~unchanged from poll-only, plus the WS cost. Realtime is additive, not
substitutive.
**Fix:** Gate polling on `connectionState !== 'live'` (drop to a 60s safety net when the socket is
up); wire `useOwnerRealtime` into `OwnerOrders`.
**Effort:** M. **Source:** async/realtime review.

### ASYNC-4 — `acks_late` without dedupe → duplicate sends
**Where:** `acks_late=True`, no `task_reject_on_worker_lost`, no DLQ; `_sync` senders have no
dedupe key.
**Failure scenario:** A worker is killed mid-`sms_order_ready` (by the 120s time-limit or OOM) →
the task is redelivered and re-run → the customer gets a duplicate SMS (real cost + trust hit),
exactly under the load when redelivery happens.
**Fix:** Add an idempotency/dedupe key to notification sends (e.g. on `NotificationLog`); add a
DLQ or a rejected→alert path.
**Effort:** S. **Source:** async/realtime review.

### FE-1 — i18n dual-source footgun
**Where:** `messages.js` (inline en+fr, read by runtime + gates) **and** `messages-ar.js` **and**
`messages-en.js` must all be edited for one new key.
**Failure scenario:** A dev edits only `messages-{en,fr}.js`, passes `verify-i18n.mjs`, fails
`verify-i18n-usage.mjs` (or ships raw keys at runtime). Already happened this project.
**Fix:** Collapse to a **single source of truth** — delete `messages.js` as the runtime source,
generate the parity files, or move to a keyed catalog with one file per locale. See
[ADR-0005](adr/0005-i18n-dual-source.md).
**Effort:** M. **Source:** frontend review.

### FE-2 — Mega-page components
**Where:** `WaiterPage.vue` 3,722, `CustomerAccount.vue` 3,654, + four more 2,500–3,700 lines.
**Failure scenario:** Single-writer bottleneck; merge conflicts; hard to test; slow to reason about.
**Fix:** Split each into feature child-components + composables.
**Effort:** L. **Source:** frontend review.

### FE-3 — Locale catalogs block first paint
**Where:** ~500KB of locale data loaded up front; Sentry not lazy.
**Failure scenario:** An Arabic visitor waits on ~500KB of JS before first meaningful paint.
**Fix:** Split catalogs by namespace/route and lazy-load; lazy-init Sentry.
**Effort:** S–M. **Source:** frontend review.

### SER-1 — Writes bypass serializers
**Where:** 242 raw `request.data.get(...)` reads vs 41 serializer-mediated writes.
**Failure scenario:** Validation/type-coercion is hand-rolled per handler; a money endpoint
reads a price/amount from `request.data` without a serializer guard → price-manipulation class
(cf. the DishOption price-manip bug already fixed).
**Fix:** Route writes — especially money/price endpoints — through serializers with explicit
fields + `read_only_fields`.
**Effort:** L (incremental; start with money endpoints). **Source:** API/auth review.

### SCHEMA-1 — OpenAPI has duplicate operationIds
**Where:** CI exports via legacy `generateschema`; ~239 view classes, zero `operationId` overrides.
**Failure scenario:** Colliding operationIds make the schema unusable for typed client-generation
(openapi-generator/orval drop or dedupe colliding ops) — the one mechanism that could let clients
evolve safely against the API is itself broken.
**Fix:** Switch to **drf-spectacular** (`@extend_schema`, unique operationIds); enables a generated
typed client (which also mitigates API-1's client-drift risk).
**Effort:** S–M. **Source:** API/auth review.

### DATA-2 — `CustomerOrderRef` mirror can silently drift  ◑ PARTIALLY ADDRESSED (2026-07-10)
**Where:** `menu/signals.py` `mirror_order_to_public_index` fired on `menu.Order` `post_save` only;
OrderItem mutations don't always re-save the parent.
**Failure scenario:** A customer's cross-restaurant "My Orders" shows phantom orders (deleted
orders that lingered), stale statuses, or a stale re-order cart.
**Resolution (this batch):** added a `post_delete` receiver `remove_order_from_public_index` that
drops the mirror row (scoped by `tenant_id` + `order_number`) when an order is deleted — killing
the phantom-order class. The existing sync already logs failures via `logger.exception` (not a
silent `except: pass`). Tests: `tests/test_order_mirror_delete.py` (3, incl. a receiver-registration
guard against a wrong sender string).
**Remaining (smaller residuals):** re-mirror on OrderItem void/comp/append mutation (status/items
snapshot can still drift while the order lives), and a periodic mirror-reconcile as belt-and-suspenders.
**Effort:** S. **Source:** data-model review.

### DATA-3 — `Dish` + 4-key JSON is not a multi-vertical catalog
**Where:** `Dish.attributes` restricted to `{sku, barcode, brand, unit}`; retail/pharmacy have no
home for variants, tax class, expiry, dosage, controlled-substance flags, batch/lot.
**Failure scenario:** The first serious pharmacy/retail tenant needs regulated fields → you either
overload `attributes` into an unqueryable free-for-all or do the deferred `Dish→Item` rename
across 76 migrations + every serializer/view/frontend ref.
**Fix:** When a paying non-food tenant is real, design a neutral `Product` with a typed
`product_kind` + per-vertical satellite tables (`FoodAttrs`/`RetailAttrs`/`PharmacyAttrs`). Until
then, keep verticals at `coming_soon` (see the product recommendation in ARCHITECTURE §11).
**Effort:** L. **Source:** data-model review.

### DATA-4 — Directory opt-in has no data prerequisite  ✅ ADDRESSED (2026-07-10)
**Where:** `cuisine_type`, `city`, `lat`, `lng` are `blank/null=True` with no rule tying them to
`directory_opt_in=True`.
**Failure scenario:** A restaurant opts into the public directory with empty city/coords →
distance-sort silently breaks; every consumer must null-guard (the frontend already had to).
**Resolution:** `ProfileSerializer.validate` now rejects `directory_opt_in=True` unless the
effective **city** and **valid coordinates** are present (coords checked *after* the existing
(0,0)/out-of-range normalization). Enforced only when `directory_opt_in` is in the update payload
(mirrors the disable-note rule), so turning it on requires the data but editing an unrelated field
on an already-listed profile isn't blocked. Tests: `tests/test_directory_optin_validation.py` (7,
no DB). Left `cuisine_type` optional so non-food verticals aren't over-constrained.
**Source:** data-model review.

### DATA-5 — Four `Profile` mirrors kept by scattered signals
**Where:** `rating_avg`, `rating_count`, `marketplace_promos`, `closure_dates` — each synced by a
different signal file + a different backfill command, all cross-schema, all best-effort.
**Failure scenario:** A bulk update / data migration / direct SQL misses a signal → the public
marketplace shows wrong ratings/promos with no constraint to catch it.
**Fix:** Consolidate the denorm into one well-tested sync path; add a periodic reconcile. (Justified
optimization — this is about making it robust, not removing it.)
**Effort:** M. **Source:** data-model review.

### STRUCT-2 — Migration sprawl, `Order` field-by-field growth
**Where:** 215 migrations (menu at 0076); `Order` ~60 fields accreted one flag at a time; no squashing.
**Failure scenario:** Every deploy runs a longer per-schema migration chain (compounds with
MULTITENANCY-1); wide `Order` rows hurt every scan.
**Fix:** Squash migrations at a release boundary; consider decomposing `Order` by bounded context
as part of STRUCT-1.
**Effort:** M. **Source:** data-model review.

---

## 🟢 Low

### API-2 — Contract sprawl
Inconsistent naming (`api/admin/customers/` vs `api/admin-tenants/`), RPC-style verb routes, all
hand-listed in three god url-files. Maintainable now (authors hold it in their heads); won't
survive team growth. **Fix:** naming convention + per-domain url modules as part of STRUCT-1.
**Effort:** M. **Source:** API/auth review.

### OPS-4 — `daphne` — re-scoped (NOT dead weight)  ⏭️ (2026-07-10)
The async review called `daphne` dead weight, but on inspection it is **wired into `INSTALLED_APPS`**
(`config/settings.py` ~L163 inserts it when channels is present) — it provides the ASGI `runserver`
dev command. Prod serves via uvicorn, so `daphne` isn't the *server*, but removing the package also
means removing the `INSTALLED_APPS` insertion and changes local `runserver` to the WSGI dev server
(no WS in dev runserver). That's a deliberate dev-tooling change, **not** the free image-slim win the
review implied — **skipped** as low-value/low-priority. If you do remove it: drop the requirement
*and* the settings insertion, and confirm nobody relies on `manage.py runserver` for local WS.
**Effort:** S. **Source:** async/realtime review (claim corrected here).

---

## Recommended sequencing (the smart path)

1. **This week (S/M, stops the bleeding):** OPS-2 (off-box backups) → OPS-1 (PITR) →
   MONEY-1 (reconciliation job) → MONEY-2 (lock payout) → TEST-1 (DB tests fail-not-skip + wire E2E).
2. **Next few weeks (the keystone refactors):** AUTHZ-1 backstop first, then IDENTITY-1 →
   the `IsTenantOwner`/`IsOrderOwner` policy layer → STRUCT-1 (`OrderService`) → FE-1 (kill dual-source).
3. **Before the PSP goes live:** MONEY-3, and re-audit every money endpoint through the new policy layer.
4. **Before a native app ships:** API-1 (versioning) + SCHEMA-1 (drf-spectacular).
5. **Strategic, decide don't drift:** MULTITENANCY-1 (pick your tenant ceiling) and the
   depth-first-on-restaurant product call (ARCHITECTURE §11).
