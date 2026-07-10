# Kepoli — System Architecture

> **This is the canonical architecture document.** It is the single source of truth for
> *how Kepoli is built and why*. When something here conflicts with an older root-level
> `.md` file, this document wins. Read `CLAUDE.md` first for the day-to-day working rules,
> then this for the mental model, then [`RISK_REGISTER.md`](RISK_REGISTER.md) for the
> known debt, and the [ADRs](adr/) for the reasoning behind each load-bearing decision.
>
> _Last written: 2026-07-10, after a ground-up 11-dimension adversarial architecture review._

---

## 1. What Kepoli is

Kepoli is a **multi-tenant restaurant / delivery super-app**. A single deployment serves
many independent restaurants (tenants), each on its own subdomain, plus a shared layer for
customers, drivers, a marketplace directory, and platform administration. It is built to
grow beyond food into other verticals (retail, pharmacy, courier, ride-hail) behind a
capability seam — see [ADR-0008](adr/0008-superapp-capability-seam.md).

- **Backend:** Django 4.2 + [django-tenants](https://django-tenants.readthedocs.io/) 3.6 + Django REST Framework. ~27k lines of view code, 67 models, ~262 endpoints, ~215 migrations.
- **Frontend:** Vue 3 + Vite + Pinia SPA, mobile-web first, PWA, full RTL/Arabic support. 62 pages.
- **Money:** a hand-rolled, closed-loop **wallet ledger** in MAD (single currency). Stripe is wired as a dormant seam.
- **Deploy:** a single VPS via Coolify (Docker Compose), uvicorn ASGI, one Postgres, one Redis. Deploys are **manual**.

**Status (2026-07):** code-complete and hardened. The remaining work is *operational*
(DR, off-box backups, a payment-service-provider account) and a small number of product
decisions — not code. The honest structural liabilities are catalogued in
[`RISK_REGISTER.md`](RISK_REGISTER.md); read it before scaling.

---

## 2. The 10,000-foot view

```
                          ┌─────────────────────────────────────────────┐
   customer.example       │                  Traefik                     │
   *.example  (tenants)   │        (Coolify) — TLS, wildcard subdomain    │
   admin / driver / rides │              routing, WS upgrade              │
                          └───────────────────────┬─────────────────────┘
                                                   │
                                     ┌─────────────▼─────────────┐
                                     │   uvicorn (ASGI)           │   (USE_ASGI=0 → gunicorn/WSGI escape hatch)
                                     │   Django + DRF + Channels  │
                                     │   TenantAwareMiddleware →  │
                                     │   connection.set_tenant()  │
                                     └───┬───────────────┬────────┘
                                         │               │
                     ┌───────────────────▼──┐     ┌──────▼───────────────────────┐
                     │  PostgreSQL           │     │  Redis (ONE instance)         │
                     │  ─ public schema      │     │  ─ cache                      │
                     │    (accounts, tenancy,│     │  ─ sessions                   │
                     │     sales, auth)      │     │  ─ Channels layer (WS)        │
                     │  ─ tenant_xxx schemas │     │  ─ Celery broker (optional)   │
                     │    (menu: orders/menu)│     └──────────────────────────────┘
                     └───────────────────────┘
                                         ▲
                     ┌───────────────────┴──────────────────┐
                     │  Celery worker + beat (optional)      │   when CELERY_BROKER_URL is
                     │  falls back to in-process thread pool │   unset, tasks run inline
                     └───────────────────────────────────────┘
```

The **central architectural fact** — the one that explains almost every other decision —
is the two-plane tenancy model in §3. Internalize that and the rest follows.

---

## 3. The two-plane tenancy model (the core concept)

Kepoli uses **schema-per-tenant** multitenancy (django-tenants). But — and this is the
subtlety that trips up every new reader — **only one app is actually tenant-scoped.**

`config/settings.py`:
- **`TENANT_APPS` = `[contenttypes, auth, rest_framework, menu]`** → the `menu` app's tables
  (orders, order items, the catalog, dine-in ops, per-tenant analytics) are created **inside
  each tenant's Postgres schema** (`tenant_<slug>`). django-tenants sets the schema via
  `SET search_path` per request, so `Order.objects.all()` inside a request automatically
  returns only *that* restaurant's orders. Isolation here is physical and automatic.
- **`SHARED_APPS`** holds `accounts`, `tenancy`, `sales`, admin, sessions → their tables live
  in the **`public` schema**, shared by every tenant.

So the real boundary is **not** "restaurant data vs platform data." It is:

| Plane | Schema | Apps | Contains | Isolation |
|---|---|---|---|---|
| **Tenant** | `tenant_<slug>` | `menu` | Orders, OrderItems, catalog (SuperCategory→Category→Dish), modifiers, combos, recipes, dine-in tables/sections, shifts, per-tenant AnalyticsEvent | **Automatic** (search_path) |
| **Public** | `public` | `accounts`, `tenancy`, `sales` | Customers, the **wallet ledger**, DeliveryJobs, drivers, payouts, the marketplace directory (Profile), CRM leads, plans/subscriptions, Users | **By convention** (manual `tenant_id` filter) |

### The consequence you must never forget

Because `Order` lives in a tenant schema and `Customer` / `WalletTransaction` / `DeliveryJob`
live in the public schema, **you cannot have a foreign key between them.** The two planes are
joined by a **stringly-typed pair**: `(tenant_id IntegerField, order_number CharField)`.

- `Order.order_number` is `unique=True` **only within each tenant schema** — it is *not*
  globally unique. Platform-wide uniqueness is reconstructed as `(tenant_id, order_number)`.
- `DeliveryJob`, `WalletTransaction.reference`, `CustomerOrderRef`, `CustomerRating`,
  `WalletChargeRequest` all point across the boundary with a bare `tenant_id` integer + an
  `order_number` string. `handled_by_user_id`, `Shift.user_id`, `CustomerNote.customer_id`,
  etc. are likewise **bare IntegerFields, not FKs**.

**This forces two hard rules** (also in `CLAUDE.md`):

1. **Any query against a public-schema table MUST be filtered by `tenant_id`** (or by an
   ownership key). A public query without a tenant filter reads *every* restaurant's rows —
   this is the exact bug class behind the Z-report and order-status leaks we fixed.
2. **The database enforces none of the cross-plane integrity.** No FK means no cascade, no
   orphan protection. If an `Order` is ever hard-deleted or a tenant schema is dropped, the
   public rows referencing it silently become orphans. There is **no `Order` `post_delete`
   handler** and no periodic reconciliation for these refs (see RISK data-integrity).

> **Is schema-per-tenant the right call?** This is the most-challenged decision in the
> whole review. It is *fine for low-hundreds of premium tenants* but fights the grain of a
> marketplace whose queries (customer history, driver payouts, directory) are inherently
> cross-tenant — which is *why* the money layer had to be pulled into `public` in the first
> place. Full reasoning, the scaling ceiling, and the shared-schema+RLS alternative are in
> [ADR-0001](adr/0001-schema-per-tenant.md). **Decide your true tenant ceiling consciously** —
> that one number determines whether this model stays.

---

## 4. Request lifecycle

1. Traefik terminates TLS and routes `*.example` (wildcard) + the fixed hosts
   (`admin`, `driver`, `rides`, apex) to uvicorn.
2. `TenantAwareMainMiddleware` resolves the subdomain → the `Tenant` row → calls
   `connection.set_tenant(tenant)`, which sets the Postgres `search_path`. From here,
   `menu` queries are scoped to that schema automatically.
3. DRF resolves the view. Routing is **not** per-app `urls.py` — everything is hand-listed
   in three central files: `config/urls.py` (tenant-schema endpoints), `config/shared_api_urls.py`
   (public/shared: customer, driver, admin, rides), `config/public_urls.py` (apex).
4. Authentication runs (see §5). Authorization is usually enforced **inside the handler body**,
   not by a permission class (see §5 and RISK authz).
5. On success the view may call `_broadcast_order_change(order)` to push a realtime hint
   (see §8).

---

## 5. Identity & authorization

Kepoli has **two disjoint identity systems** — this is load-bearing and explains a lot of the
authz shape. See [ADR-0004](adr/0004-dual-identity-and-authz.md) for the full reasoning.

- **Staff / owner / platform-admin** authenticate as a Django `User` → `request.user`, via DRF
  **`SessionAuthentication` only** (BasicAuth is enabled solely in DEBUG). DRF's permission
  layer can see this identity.
- **Customers** authenticate through a **hand-rolled side channel**: `request.session["customer_id"]`,
  read directly in views (~49 reads in `accounts/views.py` alone). This **never populates
  `request.user`**, so DRF's auth/permission machinery is *blind* to customer identity. That
  is the structural reason customer-owned endpoints are `AllowAny` + manual
  `session.get("customer_id")` ownership checks — a permission class literally cannot see the
  customer.

**The shared cookie.** `SESSION_COOKIE_DOMAIN = ".<tenant-suffix>"` — one session cookie is
valid on **every** tenant subdomain. This is deliberate (super-app single-sign-on UX) but it
means the cookie provides **zero tenant isolation**. An authenticated owner of tenant A
presents the *same* principal to tenant B; the only thing stopping a cross-tenant read is the
per-view `tenant_id` check.

**Authorization is by convention, not by policy.** Measured across the backend:
`~198 of ~262 endpoints have no authorization permission class` — they are either public
(`AllowAny`, ~96) or authN-only (`IsAuthenticated`, ~102). Tenant/ownership enforcement is a
copy-pasted first line: `if not _is_tenant_owner(request): return 403`. There are **two
divergent `_is_tenant_owner` helpers** (different signatures, in `menu/views.py` and
`accounts/views.py`) and the tenant-match predicate `user.tenant_id == tenant.id` is
duplicated in **5+ places**. Reusable, correct permission classes (`IsPlatformAdmin`,
`IsTenantEditor`, `IsTenantEditorOrReadOnly`) *exist* but are applied to only ~60 endpoints.

> **This is the #1 structural liability.** On a shared cookie, a single forgotten guard line
> is a cross-tenant data breach, and "forgot the guard" is the *default* path. The fix —
> unify identity so customers become `request.user`, collapse the checks into one tested
> `IsTenantOwner`/`IsOrderOwner` policy layer, and add a queryset-manager backstop — is the
> highest-leverage refactor in the codebase. See RISK **AUTHZ-1**.

---

## 6. The data model

### Catalog & orders (tenant schema)
`SuperCategory → Category → Dish`, with `OptionGroup`/`DishOption` (modifiers),
`ComboComponent`, `RecipeLine → Ingredient` (food BOM), `HappyHour`. Retail/pharmacy ride on
`Dish.attributes` — a JSON blob the serializer restricts to exactly **4 keys: sku, barcode,
brand, unit**. This is a restaurant model with a thin retail sidecar, *not* a real
multi-vertical catalog; a `Dish → Item` rename is deferred. `Order` is a ~60-field god-object
that has accreted one feature-flag field at a time (kitchen status, payment, delivery, loyalty,
scheduling, SLA, idempotency, cancel reasons).

### Money, drivers, directory (public schema)
`Customer` (+ denormalized `wallet_balance`), `WalletTransaction` (append-only ledger),
`DriverPayout`, `TenantFloatTransaction`, `DeliveryJob`, `DriverCashoutRequest`,
`CustomerOrderRef` (a **public mirror** of each customer's orders so "My Orders" doesn't fan
out across every tenant schema), and `Profile` (the marketplace directory row).

### Deliberate denormalization & snapshots
Two distinct patterns, both intentional:
- **Correct, frozen snapshots** (must NOT be re-derived): `OrderItem.unit_price/dish_name`,
  `Order.commission_rate_applied`, `applied_promotion_name`, `delivery_fee`,
  `DeliveryJob.delivery_commission_rate_applied` — point-in-time facts for order history/audit.
  This is textbook event-sourcing-lite and is done right.
- **Drift-prone mirrors** (kept in sync by scattered signals): `Profile.rating_avg`,
  `rating_count`, `marketplace_promos`, `closure_dates` — each maintained by a *different*
  signal file + a *different* backfill command, all cross-schema and best-effort. Justified
  (they replace a real O(N-tenants) N+1 on the marketplace) but a permanent maintenance tax.

### The integrity gap
The loose `(tenant_id, order_number)` refs have **no FK, no orphan protection, no Order
`post_delete` handler**, and the `CustomerOrderRef` mirror sync is a `post_save`-only,
`except: pass` best-effort path that can silently drift. See [ADR-0002](adr/0002-money-in-public-schema.md)
and RISK **DATA-1**.

Indexing, by contrast, is **genuinely good** — composite indexes are workload-driven and
justified with the query they serve (e.g. `Order(status, updated_at)` for the `?since=`
delta-poll, a suffix index for phone search, partial indexes for voided items).

---

## 7. Money & the wallet ledger

The money layer is the **best-engineered part of the system**. See
[ADR-0003](adr/0003-closed-loop-wallet-ledger.md).

- **Closed-loop wallet** in `accounts/wallet_service.py`. Balances are denormalized numbers
  (`Customer.wallet_balance`, `Tenant.float_balance`) backed by **append-only journals**
  (`WalletTransaction`, `TenantFloatTransaction`) that each carry a `balance_after` snapshot.
- **Idempotency is enforced at two layers**: a DB `unique` constraint on `idempotency_key`,
  **and** a re-check of `_find_idempotent(key)` *after* `select_for_update` acquires the row
  lock — so two concurrent same-key requests **replay** the first result instead of
  double-applying or 500-ing. This pattern is applied consistently across credit/debit/
  transfer/float operations. Multi-row locks are acquired in a deadlock-safe order.
- **Ledger shape is disciplined**: `amount` is a positive magnitude, direction lives in `type`,
  every row is immutable. MAD single-currency (no FX). `Decimal` throughout.
- **Payments (Stripe) are a dormant seam** — top-up/checkout/payout code exists but is inert
  until a PSP account + keys are added.

### The one gap that matters
**Nothing enforces or even checks the invariant `wallet_balance == sum(ledger)`.** The balance
is a denormalized number the app spends against; there is no reconciliation job comparing it
to the journal. A single stray write or a crash mid-move produces **silent, permanent balance
drift that nothing detects.** A `reconcile_wallet_balances` assertion job is the cheapest,
highest-value money fix available — see RISK **MONEY-1**. Two smaller gaps: the driver-payout
"owed" check reads an *unlocked* aggregate (double-pay race), and the dormant Stripe webhook
would credit session metadata instead of the settled `amount_total` — fix both before the PSP
goes live (RISK **MONEY-2/3**).

### Invariants that MUST hold (never regress these)
- The driver cash-out **6-digit code is a live bearer credential — never log it.**
- Wallet idempotency keys derived from tenant-local ids **must be schema-namespaced**
  (a bare tenant-local id collides across schemas in the shared journal).
- Wallet mutations re-check idempotency **under the `select_for_update` lock**.

---

## 8. Async, scheduled jobs & realtime

See [ADR-0009](adr/0009-async-realtime.md). The design is thoughtful and degrades coherently,
but has growth-limiting choices.

- **Celery is opt-in.** `CELERY_BROKER_URL` gates it. When set, `enqueue()` uses `task.delay()`.
  When **unset** (a likely default), tasks run **inline on a bounded in-process
  `ThreadPoolExecutor(max_workers=4)`**, which closes the DB connection in `finally`. The
  connection-exhaustion risk was anticipated and mitigated — but inline mode means
  `autoretry_for` never fires and **queued work is lost on every deploy/restart** with no
  record (RISK **ASYNC-1**).
- **Scheduled jobs go through ONE generic task**, `run_management_command`, gated by a
  hardcoded 23-entry allowlist, wired to ~23 `CELERY_BEAT_SCHEDULE` cron entries. Consequence:
  no per-job retry/routing/metrics, and **all jobs share one 2-worker queue** — a slow
  `sweep_delivery_jobs` starves notification delivery (RISK **ASYNC-2**). A `write_beat_heartbeat`
  task + `/api/health/` check gives good beat-liveness observability.
- **Realtime = hints, not data.** Channels 4 + `channels_redis`. `_broadcast_order_change`
  fires from ~22 sites carrying only `{order_number, status, payment_status}`; clients then
  refetch over authenticated HTTP — so a lost/dup/reordered frame is harmless. `CustomerOrderConsumer`
  has a real ownership gate. **But** the frontend *also* polls at full rate (15s) even when the
  WS is live, so you pay for realtime **and** polling and get the savings of neither (RISK **ASYNC-3**).
- **One Redis** backs cache + sessions + Channels + (optional) broker. A Redis stall or its
  256 MB ceiling degrades four subsystems at once — including sessions (an eviction storm logs
  users out mid-shift) (RISK **OPS-3**).

---

## 9. Frontend architecture

- **Vue 3 + Vite + Pinia**, mobile-web first, PWA, installable. Pages in `src/pages/`, stores in
  `src/stores/`, a real **design system** in `src/styles/` (`UI_SYSTEM.md` is the contract:
  `ui-panel`, `ui-input`, `ui-btn-primary/outline`, etc.; QA gate = no horizontal overflow at
  390px, explicit loading/empty/error states, ≥44px touch targets, focus-visible, RTL-safe).
- **i18n is a HAND-ROLLED runtime** (`composables/useI18n.js` + `i18n/`), **not vue-i18n**
  (older docs say vue-i18n — they are wrong). It is **dual-source**, which is a real footgun:
  a new key must be added to **all** of `messages.js` (inline `en` + inline `fr` — read by the
  runtime, the FR-parity gate, and the usage gate), `messages-ar.js` (real Arabic), and
  `messages-en.js` (AR-parity source). Edit only some and you pass one verify script but fail
  the other and ship raw keys. See [ADR-0005](adr/0005-i18n-dual-source.md) and RISK **FE-1**.
  FR text in `messages.js` is ASCII-only by convention (avoids mojibake).
- **Mega-pages.** Six page components are 2,500–3,700 lines (`WaiterPage.vue` 3,722,
  `CustomerAccount.vue` 3,654). Single-writer bottlenecks; split by feature. (RISK **FE-2**.)
- **Realtime + polling** as in §8.

Verification is gate-only (no prod data locally): `npm run verify:i18n`, `lint`, `build`, `test`.

---

## 10. Deployment topology

See [ADR-0007](adr/0007-single-node-deploy.md). Documented in detail under `infra/` and `platform/`.

- **Single VPS, Coolify (Docker Compose).** Services: web (uvicorn ASGI), Celery worker, Celery
  beat, Postgres, Redis, Traefik. `USE_ASGI=0` falls back to gunicorn/WSGI.
- **`docker/entrypoint.sh` is fail-closed**: in production it hard-fails if `DJANGO_SECRET_KEY`
  is missing and refuses to boot with `DEBUG=True`. `/api/health/` is SSL-redirect-exempt and
  reports beat liveness. This is better ops hygiene than most startups have.
- **Deploys are MANUAL.** `git push` does **not** deploy — the owner triggers Coolify in its
  dashboard. There is no deploy API/webhook wired.
- **The two critical gaps** are both disaster-recovery: a **single Postgres with no replica and
  no PITR/WAL archiving** (RPO up to ~24h — a host failure loses every wallet transaction since
  the last dump), and **backups written on-host, not shipped off-box** (lose the VPS, lose the
  DB *and* the backups together). For a money app these are business-ending. See RISK **OPS-1/2**.

---

## 11. The super-app seam

See [ADR-0008](adr/0008-superapp-capability-seam.md). This is unusually *disciplined* scope
management at the code level — the concern is strategic sequencing, not code hygiene.

- `Profile.business_type` → a `capabilities` set gates features (dine-in off for shops, etc.).
- `VERTICALS_ENABLED` gates whole verticals; non-food ones sit at `coming_soon`.
- **One identity, one global wallet** across verticals.

The liability is that live security/support surface exists for shelved verticals (rides =
1,733 LOC, retail/pharmacy = the 4-key JSON blob) earning **zero revenue**, while the actual
revenue levers (multi-branch, inventory, a PSP) are still ahead of them. Strategic
recommendation: **depth-first on restaurant** (all sellable *today* on the closed-loop wallet,
no PSP needed); hold non-food verticals at `coming_soon` until a paying partner pulls one.

---

## 12. Known structural liabilities

The honest debt from the ground-up review lives in **[`RISK_REGISTER.md`](RISK_REGISTER.md)** —
ranked by severity, each with the failure scenario, the fix, and a rough effort. **Read it
before any scaling or onboarding push.** The headline: 3 critical-tier items (authz-by-convention
on a shared cookie; single Postgres no-PITR; on-host backups) and a handful of high items
(god-files/no `OrderService`, no API versioning, test false-confidence, cron-queue starvation,
i18n dual-source).

---

## 13. Invariants & conventions that MUST hold

These are non-negotiable — a regression here is a security or money incident:

1. **Public-schema queries are always scoped by `tenant_id`/ownership.** Never trust the
   session cookie for tenant isolation.
2. **Owner/admin endpoints check `user.tenant_id == request.tenant.id`**, not just the role —
   the cookie is valid on every subdomain.
3. **The cash-out 6-digit code is never logged.**
4. **Wallet idempotency keys from tenant-local ids are schema-namespaced.**
5. **Wallet mutations re-check idempotency under the `select_for_update` lock.**
6. **A new i18n key goes into all of** `messages.js` (inline en+fr) + `messages-ar.js` +
   `messages-en.js`.
7. **Work on a branch off `main`** (direct push to `main` is blocked); commit only
   gate-verified batches; deploys are manual.

---

## 14. Map of the codebase

| Path | What lives here |
|---|---|
| `backend/config/settings.py` | `SHARED_APPS`/`TENANT_APPS` split, security hardening, Celery beat schedule, Redis wiring |
| `backend/config/urls.py`, `shared_api_urls.py`, `public_urls.py` | All ~262 routes (tenant / public / apex) |
| `backend/config/rest_framework.py`, `exceptions.py`, `asgi.py` | DRF defaults, uniform error envelope, ASGI bounded-timeout middleware |
| `backend/accounts/` | **Public plane**: Customers, wallet ledger, drivers, payouts, delivery jobs. `wallet_service.py` = the money core. `tasks.py` = async/enqueue. `views.py` (8.7k lines) |
| `backend/menu/` | **Tenant plane**: orders, catalog, dine-in, per-tenant analytics. `views.py` (13.4k lines, the god-file). `models.py`, `signals.py`, `permissions.py` |
| `backend/tenancy/` | `Tenant`, `Profile` (marketplace directory), provisioning |
| `backend/sales/` | CRM `Lead` (dual-purpose: acquisition funnel AND table reservation), plans |
| `backend/realtime/` | Channels consumers + `broadcast.py` |
| `frontend/src/pages/` | 62 Vue pages (incl. the mega-pages) |
| `frontend/src/composables/useI18n.js`, `src/i18n/` | Hand-rolled i18n runtime + dual-source catalogs |
| `frontend/src/styles/UI_SYSTEM.md` | Design-system contract |
| `infra/`, `platform/` | Coolify deploy, DNS/TLS, backups, runbooks |
| `docs/` | **This canonical doc set** (architecture, ADRs, risk register) |
