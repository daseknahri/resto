# Kepoli — Next-Phase Roadmap (KEPOLI_NEXT.md)

> **Author:** Chief Strategist, reconciling six expert lenses (restaurant depth,
> monetization/growth, technical scale, security/compliance, super-app focus,
> customer/retention) against the real codebase, `KEPOLI_ARCHITECTURE.md` and
> `BACKLOG.md`.
> **Date:** 2026-06-14. **Audience:** owner + a small dev team who act on Monday.
> **Relationship to existing docs:** `KEPOLI_ARCHITECTURE.md` is the *contract*
> (how the super-app generalizes). The OPS-1→OPS-6 program in §4d is **DONE**
> (plus OPS-5b/5c/5d/6b). This doc is what comes **after** OPS: it sequences the
> still-open clusters (OPS-5e security, OPS-6c polish, the marketplace/billing
> items in BACKLOG) plus the genuinely new product/strategy work, into a path to
> first real revenue.

---

## 1. Executive summary

Kepoli's restaurant **service core is past MVP and is genuinely a daily driver**:
course firing, per-item void with proportional loyalty clawback + wallet refund,
per-item kitchen ready-ticking, table grouping with split-bill/partial settle, an
operator-grade Z-report (service-day window, cash/wallet split, voids/refunds/tips/
per-staff, CSV+print), reservations/waitlist/capacity, combos, happy-hour, loyalty,
win-back. The OPS hardening program closed the acute scale/security/ops fences
(idempotency + DB backstops, tenant-tagged Sentry, Celery-aware health check,
retention crons, the `is_staff` priv-esc bleed across 10 helper sites, Celery RCE
allowlist). The platform is **architecturally sound and one year of single-location
growth is realistic today.** The two revenue rails are: a live closed-loop float/
wallet + delivery commission (PSP-free, working) and a marketplace that is
**structurally invite-only without a PSP** because there is no online wallet top-up.

**The single most important thing to do next: the OWNER starts the PSP merchant-account
application NOW (CMI + a local aggregator, in parallel).** It is the only blocker on
this entire list whose lead time is measured in *months not engineering-days*, it
gates the whole marketplace + every shop vertical + automated subscription billing,
and the engineering seam (`wallet_service.credit_wallet`, idempotent, Stripe-webhook-
shaped) is already built. Everything else is engineering we control; the PSP is the
one thing we can only *wait* on — so it must start on day one and run in parallel.

**But do not ship the PSP top-up live on top of today's wallet code.** Two OPS-5e
money/IDOR defects (driver cash-out cross-tenant brute-force; caller-chosen global
idempotency keys) are *prerequisites* for safely accepting real money. They are
verified still-open in code (`accounts/driver_service.py:155`,
`accounts/wallet_service.py:59`). Security batch first, then money.

**Two more Phase-A prerequisites the OPS program left open, both verified in
`settings.py`.** (1) **Durability:** prod silently degrades when `REDIS_URL`/
`CELERY_BROKER_URL` are unset — cache falls back to in-process `LocMemCache`, the
channel layer to `InMemoryChannelLayer` (cross-worker broadcasts are lost, so live
order/paid updates can miss multi-worker sockets), and the task queue runs inline in a
daemon thread with no retry (a restart drops in-flight notifications). Standing up Redis
+ a Celery worker with a boot-time assertion belongs in Phase A — *before* money-
adjacent events ride this path on multi-worker prod (A7). (2) **Privacy:** Phase A is
the moment a real PII base (paying tenants + their customers) and PSP/PCI scope first
land, so the privacy baseline must be *decided* before that onboarding, not deferred —
the implementation can phase, but the decision gate is a Phase-A entry condition (§4).

---

## 2. The critical path to first revenue

The minimal ordered sequence to onboard the first paying restaurants and take real
money. Two tracks run in parallel from day one: an **OWNER decision track** (no
code) and an **engineering track**.

### 2.0 OWNER decision track (start Monday, blocks nothing downstream by waiting)
1. **Apply for a PSP merchant account** (see options table below). External KYC/
   onboarding dominates the timeline — this is why it is step zero.
2. **Set the three plan prices** (Basic/Growth/Pro, MAD/month + billing cycle).
   `Plan` has *no price field* and `pricing.js` ships null placeholders — there is
   no system-of-record for what a tenant owes until the owner supplies numbers.
3. **Confirm the default marketplace commission rate** (today hardcoded 10%) and
   whether launch partners get a discounted/0% rate.

### 2.1 Engineering track — what unblocks money (ordered)
1. **Close the OPS-5e money/IDOR cluster** (security batch — see Phase A). This is a
   hard prerequisite to taking real money: until wallet idempotency keys are
   server-namespaced and asserted on replay, wiring a PSP top-up webhook on top is
   unsafe (the webhook keys on the event id and rides the same seam).
2. **Server-namespace + assert wallet idempotency** (`wallet_service.py`). This is
   *the* money-truth backbone and the literal prerequisite the PSP webhook depends on.
3. **Add `Plan.price`/`currency`/`billing_period`** (one nullable-defaulted, non-
   breaking migration) and wire `pricing.js` + the marketing page to read them.
   Engineering is small; it is gated only on the owner's numbers (2.0 step 2).
4. **Build the PSP top-up seam dormant behind a feature flag**: `CustomerWallet.vue`
   self-serve top-up UI + a PSP-agnostic top-up-intent endpoint + the idempotent
   `StripeWebhookView → credit_wallet(idempotency_key=event_id)` handler, all gated
   off with no live keys. **This decouples engineering from the KYC wait** — when the
   PSP account clears, going live is a config flip, not a 4-week sprint.
5. **Pre-PSP GMV unlock — extend COD-on-handover to the marketplace path.** Direct
   orders already let trusted repeat customers pay cash on handover (`_cod_eligible`,
   `menu/views.py:2009`); `MarketplacePlaceOrderView` has no COD branch. Porting the
   existing gate lets the marketplace transact for trusted customers with **zero PSP**,
   growing GMV and commission revenue *while the PSP application is in flight*.
6. **Fix marketplace commission** (`accounts/views.py:3213`): per-tenant rate
   (`Profile.marketplace_commission_pct`) + `Order.commission_rate_applied` snapshot +
   one consistent basis + tenant-local month bucketing — mirror the delivery pattern
   (`delivery_commission_pct` / `DeliveryJob.platform_commission`). Unlocks negotiated
   launch-partner rates as a sales lever *and* fixes the >10%-looking reconciliation bug.

### PSP options (the owner decision, called out explicitly)
| Option | Onboarding | Card coverage (Morocco) | What it unlocks | Recommendation |
|---|---|---|---|---|
| **CMI** | Heavy KYC, slower | Broadest local card acceptance | Full online wallet top-up → marketplace + shop verticals + auto-billing | **Apply (primary)** |
| **Payzone / YouCan Pay-class aggregator** | Faster, SMB-friendly | Good local | Same seam, possibly live sooner | **Apply in parallel; pick whichever clears KYC first** |
| **PayPal** | Fast | Poor MA card coverage, FX-unfriendly | Limited | Fallback only |
| **Stripe** | N/A for MA-domiciled biz as of cutoff | — | — | Verify availability before relying on it; do not block on it |

**What the PSP unlocks (and nothing else does):** online wallet top-up → first-time
remote customers can pay → the *entire* marketplace + shops + pharmacy verticals
become acquirable, and automated recurring subscription billing becomes possible.
The closed-loop float + delivery/ride/courier commission already earn margin without
a PSP — but marketplace food-GMV is throttled until top-up flips on.

---

## 3. Phased roadmap

Effort key: S ≈ ≤2 days · M ≈ ~1 week · L ≈ ~2-3 weeks · XL ≈ a month+.
Each batch ships independently using the proven OPS protocol (Sonnet agents, gates,
one adversarial reviewer, fix loop, personal code verification, BACKLOG update).

### Phase A — "Take money safely" (next ~2-4 weeks) — P0
**Theme: close the money/security holes and the durability gap that block accepting
real money, then build the dormant PSP seam and the pre-PSP GMV unlock. Durable infra
(Redis + Celery) and the privacy decision gate are prerequisites here, not later
polish — Phase A is the moment real PII and real money first arrive.**

| # | Workstream | Effort | BACKLOG ref |
|---|---|---|---|
| A1 ✅ | **OPS-5e security batch (one batch).** Driver cash-out: throttle + per-actor lockout after N bad attempts shipped (driver_service.py); wallet idempotency keys server-namespaced at view layer (`ownercharge:{schema}:` prefix) + customer assertion on replay in wallet_service.py; MarketplaceOrderStatusView IDOR patched; push-sub hijack scoped to (customer_id, endpoint); rating fraud: ownership + throttle. All items verified `[x]` in BACKLOG.md (OPS-5e SHIPPED section). | L | OPS-5e (BACKLOG:157-204) |
| A2 ✅ | **`Plan.price`/`currency`/`billing_period` migration** + wire `pricing.js` + marketing page. *(Gated on owner numbers — 2.0 step 2.)* — **Shipped:** `Plan.price_monthly + currency + billing_period` (tenancy/migration 0046); `PlanSerializer` + `PlanAdmin` updated; `PublicPlanPricingView` at `GET /api/public/plans/` (AllowAny); `pricing.js` now exports `fetchPlanPricing()`; `Home.vue` fetches on mount + shows live currency prefix. Owner sets prices in Django admin → marketing page updates automatically. | M | OPS-6 pricing scaffold; ARCH §4d decision-gated |
| A3 ✅ | **PSP top-up seam, dormant behind a flag.** `CustomerWallet.vue` + top-up-intent endpoint + `StripeWebhookView` → idempotent credit. No live keys. — **Shipped:** `PSP_TOPUP_ENABLED` settings flag (default off); `CustomerTopUpIntentView` (POST `/api/customer/topup/intent/`) creates Stripe Checkout Session; `CustomerTopUpWebhookView` (POST `/api/customer/topup/webhook/`) verifies Stripe-Signature + credits wallet via `credit_wallet(idempotency_key="stripe:{event_id}")` (idempotent); `CustomerSessionView` now includes `platform: {psp_topup_enabled}` in response; `customer.js` store reads `data.platform`; `CustomerAccount.vue` top-up card (amount input + Stripe redirect) gated on `customerStore.platform?.psp_topup_enabled`; return-from-Stripe success/cancelled banner; 8 unit tests in `test_psp_topup.py`. Go-live: set `PSP_TOPUP_ENABLED=1 + PSP_STRIPE_SECRET_KEY + PSP_STRIPE_WEBHOOK_SECRET + PSP_SITE_URL` in env. | L | ARCH Phase 3; BACKLOG "Stripe wallet top-up seam" |
| A4 ✅ | **Marketplace COD-on-handover** — `_cod_eligible` ported to `MarketplacePlaceOrderView` (accounts/views.py:3991-4024); trusted-repeat-customer cash path + `_mkt_cod_order` flag matches direct PlaceOrderView behavior. | M | (new — from monetization lens) |
| A5 ✅ | **Marketplace commission fix** — per-tenant rate (`Profile.marketplace_commission_pct`, defaults 0.10) + `Order.commission_rate_applied` snapshot at checkout + per-currency totals in the marketplace report (accounts/views.py:3971-3984, 4183). | M | BACKLOG:373-384 |
| A6 ✅ | **Redis `requirepass`/ACL** + fail-fast if broker URL unauthenticated in prod — `config/checks.py:redis_has_auth_credentials` (kepoli.W002): deploy check parses REDIS_URL and emits a Warning when no password is present in production. | S | OPS-5d Celery-RCE note (mitigation) |
| A7 ✅ | **Durable prod infra boot assertions** — `config/checks.py:redis_and_celery_configured` (kepoli.E001 + kepoli.W001): ERROR if REDIS_URL unset in prod (hard-fails the deploy via `--fail-level ERROR` in entrypoint.sh), WARNING if CELERY_BROKER_URL unset. `coolify.env.example` documents the Redis + worker + Beat setup. | M | Scale lens P1 (settings.py:201-296, durability blocker) |

**Exit criteria for Phase A:** no open HIGH money/IDOR; wallet idempotency is tenant-
namespaced + asserted; Redis + a Celery worker are running in prod with boot-time
assertion (no silent LocMem/in-memory/inline-thread fallback); the PSP webhook is built
and tested (dormant); marketplace can transact via COD for trusted customers; plan
prices render on the marketing page; the privacy decision gate (§4) is answered before
the first paying tenant onboards real PII.

### Phase B — "Make a single location complete + grow repeat business" (next quarter) — P1
**Theme: finish the operator-grade single location (the §4b restaurant-first directive)
and turn the retention machine on the full audience. This is what makes a serious
operator pick Kepoli over Toast/Square, and what lifts repeat revenue.**

| # | Workstream | Effort | Source |
|---|---|---|---|
| B1 ✅ | **Email as a 2nd channel for win-back already shipped** — `send_winback_nudges.py` already has dual-channel delivery: `_send_nudge_email()` + `send_marketing_email()` + `email_by_id` dict built from `email_verified=True` customers; tries both push AND email, burns 90-day slot only if both fail. | M | CX lens |
| B2 ✅ | **Repeat-business analytics panel** — `OwnerRepeatAnalyticsView` GET `/api/owner/repeat-analytics/?days=N`; repeat_rate + new vs. returning customer count + revenue split; `RepeatAnalyticsWidget.vue` in OwnerAnalytics page (3-card grid + split bar); 9 backend tests. | L | CX lens |
| B3 ✅ | **Ingredient/recipe inventory + food-cost %.** Phase 1 ✅ — `Dish.cost_price` field (migration 0063) + food-cost section on Z-report (Subquery aggregation) + labor section on Z-report frontend. Phase 2 ✅ — `Ingredient` + `RecipeLine` models (migration 0068); `IngredientSerializer`/`RecipeLineSerializer`; 6 owner endpoints (`/api/owner/ingredients/`, `/low-stock/`, `/adjust/`, `/api/owner/dishes/<slug>/recipe/`); atomic stock depletion in PlaceOrderView + MarketplacePlaceOrderView via F() UPDATE; `is_low_stock` computed field; 39 new tests. | XL (phase it) | Restaurant lens |
| B4 ✅ | **Labor module** — `Shift` model (tenant schema, migration 0065); `POST /api/staff/clock-in/` / `POST /api/staff/clock-out/` / `GET /api/staff/my-shift/`; Z-report labor section (shifts, total_hours, total_labor_cost, labor_pct); WaiterPage clock-in/out buttons + elapsed-since chip; 12 backend tests. | L | Restaurant lens |
| B5 ✅ | **Real table-state model** — `TableLink.status` (open/occupied/dirty/reserved) + `capacity`; migration 0064; `PATCH /api/staff/tables/<id>/status/`; `POST /api/staff/orders/<src>/transfer-items/`; `POST /api/staff/orders/<dest>/merge/`; WaiterPage status badges + mark-dirty/clean buttons + Transfer/Merge modals; 28 new backend tests. | L | BACKLOG:358; Restaurant lens |
| B6 ✅ | **Referral mechanic** — `Customer.referral_code` (auto-gen), `referred_by` FK, `referral_reward_given` guard; `Profile.referral_enabled + referral_reward_points`; first-paid-order hook credits both parties; GET `/api/referral/<code>/` + POST `/api/customer/link-referral/`; frontend captures `?ref=CODE` → localStorage → auto-links after auth; customer overview referral card + owner toggle in Promotions. migrations accounts/0049 + tenancy/0045. | L | CX lens |
| B7 ✅ | **Customer re-order rail + loyalty progress nudge** — last-3-orders re-order rail in CustomerAccount overview tab; loyalty tile nudge (progress bar + "Ready to redeem" badge) in the same tab. | M | CX lens |
| B8 ✅ | **Marketplace N+1 already killed** — `Profile.rating_avg` + `rating_count` denormalized (tenancy/models.py:321-331); post_save/delete signals in menu/signals.py call `recompute_tenant_rating()`; DirectoryView + MarketplaceView read from Profile (no cross-schema hops). | M | BACKLOG:446; Scale lens |
| B9 | **Backups automated + restore rehearsed end-to-end.** Enable Coolify Postgres backup (daily/30d) AND actually run the §9 per-schema `pg_restore` against a real dump once. Highest-severity reliability gap for a money-ledger DB; the runbook is unproven until executed. | S | OPS-5 runbook; Scale lens |
| B10 ✅ | **`perm_void` split already shipped** — `User.perm_void` field exists (default True), `effective_perm_void()` gates `VoidOrderItemView`, session includes `perm_void`, `OwnerStaffPage` renders void_orders toggle independently of manage_orders. No action needed. | S | Restaurant lens; OPS_AUDIT Theme 8 |
| B11 | **Renewal-ready billing surface** ~~(default `invoice_amount` from `Plan.price`; renewal-due list in AdminConsole; pre-lapse reminder email)~~. ✅ **DONE** — `payment_overdue_since` in admin API; grace-period badge in AdminConsole; `send_renewal_reminder_email` + `_send_renewal_reminder` in enforce_subscriptions; 10 tests. | M | Monetization lens |
| B12 ✅ | **OPS-6c privacy+SEO+a11y already shipped** — noindex on cart/account/order-status (INDEXABLE_ROUTE_NAMES allowlist in useSeoMeta.js); sitemap.xml (backend) + robots.txt Sitemap: directive; hreflang en/fr/ar; Restaurant + Breadcrumb + MenuItem JSON-LD on public pages; DishCard ARIA (aria-label, aria-live qty counters); skip-link in CustomerLayout + OwnerLayout + WaiterLayout + LandingLayout; OG+Twitter meta complete. No further action needed. | M | OPS-6c (BACKLOG:75-117) |
| B13 ✅ | **Scale sweep:** CRM segment predicate is HAVING SQL (`_seg_having` dict pushed to DB, verified in code menu/views.py:9435-9444); phone search uses btree exact-match on `customer_phone_digits` for 6+ digit terms (code 9453-9454); `OrderItem.voided_at` partial index shipped in migration 0060; Z-report N+1 fixed (BACKLOG [x]); non-blocking index migrations: 0060 + 0062 converted to `AddIndexConcurrently + atomic=False` (CREATE INDEX CONCURRENTLY, no ACCESS EXCLUSIVE lock on live tables). | M | BACKLOG:437-465; Scale lens |

### Phase C — "Expand the surface deliberately" (later) — P2
**Theme: only after a single location is complete and money flows, widen scope —
one deliberate step at a time, never speculatively.**

| # | Workstream | Effort | Source |
|---|---|---|---|
| C1 | **Auto-print on new order** via a local print agent / ESC-POS bridge. Closes "great kitchen screen" → "replaces my printer setup." | M | BACKLOG:22; Restaurant lens |
| C2 ✅ | **Prep-station routing** (optional station tag on Category/Dish; split kitchen tickets per station). Non-breaking; independents ignore it. — **Shipped:** `Category.station` + `OrderItem.station` snapshot (migration 0066); `StepCategories.vue` station input; `OwnerKitchen.vue` per-station filter bar + item dimming + station chip; EN/FR/AR i18n; 4 snapshot tests in `test_station_snapshot.py`. | M | Restaurant lens |
| C3 ✅ | **Loyalty depth** — tiers (Bronze/Silver/Gold), birthday bonus (once/yr, platform-wide), first-order bonus (tenant-scoped). `Customer.lifetime_loyalty_points` + `birthday` + `loyalty_birthday_rewarded_year`; `LoyaltyConfig` gains 7 tier/bonus fields; PlaceOrderView + MarketplacePlaceOrderView apply multipliers and bonuses; OwnerLoyalty.vue + CustomerAccount.vue updated; 15 tests. | L | CX lens |
| C4 | **Multi-branch** (location group over tenants + consolidated reporting + shared menu). The largest revenue-expansion lever AND the heaviest lift (django-tenants is one-schema-per-location). Sequence *after* B3/B4/B5 make a single location genuinely complete. | XL | BACKLOG:20; Restaurant lens |
| C5 | **DB scaling ceiling:** PgBouncer (transaction pooling, mindful of `SET search_path`) + a read path for the heavy public marketplace. Revisit at ~50-100 tenants. | L | Scale lens |
| C6 ✅ | **Full data-subject tooling** — self-serve export + GDPR right-to-erasure. **Shipped:** `CustomerDataExportView` (GET `/api/customer/my-data/`) returns JSON bundle of profile/wallet/orders/addresses with `Content-Disposition: attachment`; `CustomerErasureRequestView` (POST `/api/customer/request-erasure/`) runs Phase-0 guard rails (open orders, pending charges, non-zero balance) then delegates to `erase_customer` management command + flushes session; `_check_guard_rails` extracted to module level for testability; 9 unit tests (SimpleTestCase, no DB). Frontend: Privacy & Data panel in CustomerAccount.vue Profile tab — download button (fetch → Blob → `<a download>`), inline delete-confirm flow with guard-blocked error display; 14 i18n keys (EN/FR/AR); all 4 frontend gates pass. | L | Security lens |
| C7 ✅ | **Pre-dispatch reminder push for SCHEDULED orders.** **Shipped:** `Order.predispatch_reminder_sent_at` field (migration 0069) as an idempotency stamp; `send_predispatch_reminder_sync` in `accounts/push.py` (EN/FR/AR locale-aware copy, respects `notify_order_updates` opt-out, cleans stale subscriptions); `send_predispatch_reminders` management command — finds SCHEDULED orders with `scheduled_for` in the 55–90 min window, sends push, stamps the field (dry-run supported); command added to `_MANAGEMENT_COMMAND_ALLOWLIST` + Beat schedule every 15 min; 13 unit tests (SimpleTestCase, no DB). | S | BACKLOG: Pre-dispatch reminder |
| C8 ✅ | **Email bounce/complaint suppression list.** **Shipped:** `CustomerEmailSuppression` model (public schema, unique by email) + migration 0052; `EmailSuppressionWebhookView` (POST `/api/public/email/suppression/`) with Bearer-token auth (disabled until `EMAIL_SUPPRESSION_WEBHOOK_SECRET` set in env); supports generic bounce/complaint payload + Mailgun nested `event-data`; suppression checked in `send_campaign_email_sync` and `send_winback_nudges._build_audience`; 11 unit tests. Set `EMAIL_SUPPRESSION_WEBHOOK_SECRET` in env + configure ESP webhook URL to activate. | M | BACKLOG: email bounce suppression |
| C9 ✅ | **Car-doc expiry tracking.** **Shipped:** `driver_licence_expiry` + `driver_insurance_expiry` DateFields on `Customer` (migration 0053); `send_driver_doc_expiry_push_sync` in `accounts/push.py` (EN/FR/AR, warning vs. expired message variants); `check_car_doc_expiry` management command — expire sweep de-approves drivers + sends push (idempotent), warning sweep fires in 12–14 day window; command added to `_MANAGEMENT_COMMAND_ALLOWLIST` + daily Beat entry; `AdminCarApprovalView` accepts optional `licence_expiry`/`insurance_expiry` date strings; doc re-upload clears corresponding expiry; expiry dates surfaced in both driver self-view and admin driver list; 20 unit tests (SimpleTestCase, no DB). | M | BACKLOG: car-doc expiry |
| C10 ✅ | **Ride pre-dispatch reminder push.** **Shipped:** `RideRequest.predispatch_reminder_sent_at` (migration 0054) as idempotency stamp; `send_ride_predispatch_reminder_sync` in `accounts/push.py` (EN/FR/AR, ride + package variants, `{n}` minutes in body); `send_ride_predispatch_reminders` command finds SCHEDULED trips with `scheduled_for` in the 20–40 min window + `predispatch_reminder_sent_at IS NULL`, pushes to rider, stamps field; command added to allowlist + Beat every 15 min; 14 tests (SimpleTestCase, no DB). | S | BACKLOG: Pre-dispatch reminder push for scheduled trips |
| C11 ✅ | **k6 load & stress harness (R22).** **Shipped:** `infra/k6/load.js` — three scenarios (smoke 2 VU×2 min, ramp 0→VUS_RAMP→0 ~11 min, soak VUS_SOAK×SOAK_DURATION) covering 4 traffic groups (health 15%, marketplace browse 35%, directory 15%, tenant menu load 35%). Per-route p95 thresholds + global <1% error gate. `infra/k6/README.md`: install, quick-start, env vars, output interpretation, what-to-scale-when table, CI workflow snippet. All tunable via env vars (BASE_URL/TENANT_URL/MENU_SLUG/VUS_RAMP/VUS_SOAK/SOAK_DURATION). | S | BACKLOG: R22 |
| C12 | **`Dish→Item` schema rename.** Held until a PSP-enabled retail tenant proves demand; 204 backend symbols + 53 frontend files + a `migrate_schemas` pass = high blast radius for zero current payoff. Rehearse on a clone (ARCH §3). | XL | BACKLOG:38; ARCH §3 |

---

## 4. Decision gates (OWNER must answer)

| Gate | Recommendation | Consequence of not deciding |
|---|---|---|
| **PSP choice** | Apply to **CMI + a local aggregator (Payzone/YouCan-class) in parallel** Monday; pick whichever clears KYC first. | The marketplace stays invite-only indefinitely; all shop verticals + auto-billing stay blocked. This is the only multi-month lead time on the list. |
| **Plan prices** (Basic/Growth/Pro MAD/month + cycle) | Supply three numbers this week so A2 can ship. | No system-of-record for what tenants owe; marketing page can't convert; no sales motion. |
| **Marketplace commission default rate** (and launch-partner discount) | Confirm the default (keep 10% or set new) + offer 0%/discounted to the first ~10 Morocco partners as an acquisition lever. | A5 can't ship a sensible default; you can't offer negotiated rates without a code change for everyone. |
| **Self-serve signup vs manual provisioning** | **Defer self-serve.** For first-10-restaurants, manual `provision_lead` is an asset (qualify leads, set the right plan, high-touch). Revisit only when lead volume exceeds human throughput. | Risk of building signup you don't need yet, optimizing a problem you don't have. |
| **Vertical focus** (which stay customer-visible) | **Formally SHELVE car-rides** (flip to `coming_soon` + gate endpoints — needs a separate licensed-car-driver supply); **KEEP courier warm** (reuses the existing delivery pool, real MA same-city parcel demand); **PARK grocery/pharmacy deep features** (blocked on PSP + unbuilt pick-flow). | Five verticals advertised `status:'live'` (`services.js:27`) with no operational support = support/expectation liability against the restaurant-first directive. |
| **Multi-branch timing** | **After** Phase B (inventory/labor/table-state). A single complete location is the prerequisite, per §4b. | Building it early caps you at independents anyway, and ships an incomplete location to the lucrative small-chain segment. |
| **`Dish→Item` rename timing** | **Hold** until a PSP-enabled retail tenant proves demand. | Premature high-blast-radius `migrate_schemas` for zero payoff; `useVocabulary.js` already gives shops the right UX nouns with no schema cost. |
| **PCI/PSP security boundary** | Decide *now*, in the PSP conversation: PSP card form is fully hosted/redirect/iframe, **no PAN ever touches Kepoli** → SAQ-A scope. Document as a hard rule before any integration. | Engineering could build the top-up the wrong way and pull you into a far heavier PCI scope. |
| **Privacy baseline** (jurisdiction + retention scope) | Decide *before the first paying tenant onboards real PII* (a Phase-A entry condition). Pick the governing regime (MA Law 09-08 / GDPR-equivalent if EU diners), set a retention rule, publish a privacy policy, and have a manual export/erasure runbook ready. Automated data-subject tooling (C6) can follow. | A real PII base + PSP/PCI scope land in Phase A with no policy, no retention rule, and no erasure path — a compliance and trust liability that is far costlier to retrofit after onboarding than to decide up front. |

---

## 5. Risk register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | **Single-PSP dependency / long lead time.** The entire marketplace + billing thesis rests on one external approval with months of KYC. | High | Apply to two PSPs in parallel Monday (CMI + aggregator). Build the seam dormant (A3) so go-live is a config flip. Grow GMV pre-PSP via COD (A4) + closed-loop float + delivery commission. |
| R2 | **Open money/IDOR security debt shipped to paying tenants.** Driver cash-out cross-tenant brute-force (`driver_service.py:155`, verified) + caller-chosen global wallet idempotency keys (`wallet_service.py:59`, verified) move/mis-attribute real money. | High | Phase A1/A2 *before* onboarding paying tenants or wiring the PSP. The PSP webhook literally depends on the namespaced idempotency fix. |
| R3 | **Marketplace cross-schema N+1 scale cliff.** `DirectoryView` does O(N_tenants) schema hops per cache miss on the busiest public endpoint; 90s cache is a bandage. | High at ~100 tenants | B8: denormalize rating onto public `Profile`. Cheap, highest-ROI scale change; do before aggressive growth. |
| R4 | **Unrehearsed restore on a schema-per-tenant money ledger.** A bad RunPython or schema drop has no tested recovery path. | High | B9: automate backups AND execute the per-schema restore once against a real dump before real tenants. |
| R5 | ✅ **Scope dilution across 5 advertised verticals** — MITIGATED. `VERTICALS_ENABLED` frozenset in settings (default excludes `rides`); `_vertical_gate(kind)` guards all 11 ride/driver endpoints (503 + `vertical_disabled` code); `enabled_verticals` in CustomerSessionView platform dict; `getServices(enabledVerticals)` for dynamic frontend gating; `services.js` marks rides `coming_soon` statically. 12 new gate tests. | Medium | ✅ Done |
| R6 | **Retention machine pointed at a near-empty audience.** Win-back/campaigns are push-only → most lapsed diners unreachable. | Medium | B1: add email fallback. Already-built engine, full opted-in audience, no owner decision. |
| R7 | **Deploy/migration fragility at tenant count.** Manual Coolify, serial `migrate_schemas`, non-CONCURRENT index builds take per-schema write locks; no staging rehearsal. | Medium, growing | B13: `AddIndexConcurrently`/`atomic=False`; pre-deploy `pg_dump` for data migrations; rehearse pending migrations on a multi-schema clone. |
| R8 | **Silent prod durability fallback.** With `REDIS_URL`/`CELERY_BROKER_URL` unset, prod degrades quietly (`settings.py:201-296`): `LocMemCache` (no shared cache), `InMemoryChannelLayer` (cross-worker broadcasts lost → missed live order/paid updates on multi-worker prod), inline daemon-thread task queue (no retry → dropped notifications on restart). Money-adjacent events ride this path. | High once on multi-worker prod | A7: stand up Redis + a Celery worker + Beat; **assert their presence at boot when `DEBUG=False`** so a misconfigured deploy hard-fails instead of silently losing events. |
| R9 | **PII onboarded before a privacy baseline exists.** Phase A brings real customer/tenant PII + PSP/PCI scope, but there is no policy, retention rule, or erasure path today. | Medium, becomes acute in Phase A | Privacy decision gate (§4): decide jurisdiction + retention + publish policy + manual export/erasure runbook before the first paying tenant onboards; automated tooling follows in C6. |

---

## 6. Explicitly NOT now (formally shelved to stay focused)

- **Self-serve tenant signup.** Manual `provision_lead` is the right high-touch motion for the first 10 restaurants. Revisit on a clear volume signal.
- **Recurring auto-charge billing.** PSP-gated; cash/transfer + the renewal-due surface (B11) is enough at 10 tenants.
- **Car-ride vertical (deep work).** Needs a separate licensed/insured car-driver supply the current motorbike-delivery recruiting doesn't produce. Flip to `coming_soon` + gate endpoints.
- **Grocery/pharmacy deep features** (pick-flow, substitutions, refund deltas, basket→vehicle, cold-chain). Unbuilt AND blocked on PSP; building them now is pure dilution.
- **`Dish→Item` / `Menu→Catalog` schema rename.** Held until a PSP-enabled retail tenant proves demand. `useVocabulary.js` covers the UX today.
- **Multi-branch.** Real, but sequenced after a single location is complete (Phase C). Largest lever, heaviest lift.
- **PgBouncer / read replica.** Not urgent today; revisit at ~50-100 tenants after the per-request N+1s (B8/B13) are fixed.
- **Prescription pharmacy flows.** Permanently out of scope (parapharmacie only).

---

*Bottom line: the product is real and the foundation is hardened. Phase A makes it
safe to take money and unblocks revenue without waiting on the PSP; Phase B makes a
single location genuinely complete and turns retention on the full audience; Phase C
expands deliberately. The owner's three Monday actions — apply for the PSP, set plan
prices, ratify vertical focus — gate more value than any sprint the dev team can run.*
