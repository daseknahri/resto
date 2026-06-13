# Kepoli — super-app architecture & roadmap

> **Status (2026-06-08):** Phase 0 (brand + capability seam + rider acquisition +
> PWA) shipped. Retail catalog and ride-hailing are planned, not built. This doc
> is the contract for how the super-app generalizes — read it before extending a
> vertical.

## 1. What Kepoli is

**Kepoli** is the umbrella brand for a multi-tenant **super-app**. One platform,
several personas:

- **Businesses** (tenants) — run their menu or catalog, take orders, manage
  delivery. Each keeps its own name and subdomain; "Kepoli" is the platform around
  them, not their brand.
- **Customers** — discover businesses in the cross-business marketplace, order, and
  track delivery.
- **Riders** — anyone can apply to deliver; once vetted they join the shared
  platform delivery pool and earn per drop-off.

The expansion path: **restaurants + riders → retail/other shops → ride-hailing
(car drivers)**. Each step reuses the same tenancy, wallet, delivery, marketplace
and notification infrastructure rather than rebuilding it.

## 2. Brand

- Platform name: **Kepoli**. Single source of truth:
  - frontend: `frontend/src/lib/brand.js` (`PLATFORM_NAME`, `PLATFORM_MONOGRAM`, …)
  - backend: `backend/config/brand.py`
- Displayed marketing copy lives in i18n (`landingLayout.*`, `home.*`) so it can be
  localized (en/fr/ar). Use the brand constants for code-level references
  (titles, fallbacks), **not** hard-coded "Kepoli" strings in components.
- PWA identities (separate installable apps, one per persona):
  | manifest | app | start_url |
  |----------|-----|-----------|
  | `public/app-manifest.json`     | Kepoli (customer)  | `/`       |
  | `public/manifest.json`         | Kepoli Business    | `/owner`  |
  | `public/driver-manifest.json`  | Kepoli Rider       | `/driver` |
  | `public/waiter-manifest.json`  | Kepoli Waiter      | `/waiter` |
  `public/manifest-loader.js` picks the manifest by route prefix.
- Tenant restaurant/store names are **never** rebranded — they own their identity.

## 3. Business types & capabilities (the generalization seam)

The platform began restaurant-only. Rather than fork the codebase per vertical, a
single **capability seam** gates restaurant-specific features:

- `Profile.business_type` — `restaurant | cafe | bakery | grocery | retail`
  (default `restaurant`). Migration `tenancy/0033`.
- `Profile.capabilities` (derived property) → `{tables, dine_in, waiter, kitchen,
  reservations}`. Restaurants & cafés get the full set; bakery keeps `kitchen`
  only; grocery/retail are pure catalog + pickup/delivery shops. Unknown/blank
  types fall back to the **full** set, so an existing tenant can never be silently
  downgraded.
- Exposed to the SPA via `/api/meta/` (`ProfileSerializer`): `business_type`
  (read+write) and `capabilities` (read).
- Frontend: `useTenantStore().capabilities` / `.businessType`; `OwnerLayout`
  hides Tables / Reservations / Waiter / Kitchen nav for shop verticals.
- Owner sets their vertical in the publish step (`StepPublish.vue`).

**Deliberately deferred:** the `Dish → Item` / `Menu → Catalog` rename. It crosses
every tenant schema via `migrate_schemas`, so it lands last, rehearsed on a schema
clone. `Order`/`OrderItem` already snapshot slug+name+price and are vertical-
agnostic; wallet, delivery, marketplace and tenancy are already business-agnostic.

### Adding a new business vertical (recipe)
1. Add the value to `Profile.BusinessType` + a row in `_CAPABILITIES_BY_TYPE`
   (default missing keys to the safe value). Migration.
2. Add the i18n label (`stepPublish.businessType*`).
3. If it needs a feature restaurants don't have, add a new capability key to
   `CAPABILITY_KEYS` (default `True` for restaurant to stay non-breaking) and gate
   it in the nav + the relevant view.
4. No new order/wallet/delivery code — those are already generic.

## 4. Rider marketplace (gig delivery)

Riders are **public-schema `Customer` rows** with driver flags — no separate model,
so a customer can "switch to work with us" without a second account.

- `Customer.is_driver` = applied; `Customer.driver_approved` = vetted & allowed
  online; `driver_vehicle`, `is_driver_online`, GPS fields.
- Apply: `POST /api/driver/register/` (session-auth, sets `is_driver=True`). On a
  fresh application the platform admins are notified (email + `NotificationLog`).
- Vet: `AdminDriverApprovalView` (`/api/admin/drivers/<id>/approve|reject/`) +
  `AdminDrivers.vue`.
- Work: `/driver` is the install-first PWA console — online toggle, live GPS,
  job offers, accept, status flow, proof-of-delivery code, earnings, weekly
  cash-out at a restaurant. Jobs are the shared pool (`DeliveryJob`, public schema,
  `unique_together(tenant_id, order_number)`).
- Acquisition: signed-out `/driver` is an "Earn with Kepoli" value-prop +
  install page; landing footer links to it.

## 4b. STRATEGY (owner decision, 2026-06-10): restaurant-first completion
The groundwork for all verticals is LAID: service registry (§6), business_type
capability seam (§3), retail vocabulary + attributes, per-vertical delivery
semantics (§5c), and the trip primitive (rides/courier). These seams exist so
future verticals are config + focused features, not rewrites.
With the ground set, the FOCUS is completing the FIRST service end-to-end:
a complete, real-world app for RESTAURANTS. Other verticals stay live but
receive only fixes until the restaurant experience is finished. New deep
vertical features (store pick-flow/substitutions, pharmacy-specific flows,
ride extras) are deliberately parked behind restaurant completeness.

## 4c. Restaurant completion plan (from the 2026-06-11 completeness audit)
R1 ✅ (f716d97): daily close digest + cash/wallet split; category pause; live reorder prices.
R2 (next): DINE-IN SERVICE ARCHITECTURE — one designed batch:
  - OrderItem.is_voided/voided_at/void_reason (migration menu/0047)
  - POST /api/staff/orders/<id>/items/  — append items to an OPEN TABLE order
    (statuses pending/confirmed/preparing, fulfillment=table, payment != PAID;
    reuses PlaceOrderView item-building + locked stock decrement; new items enter
    kitchen flow is_ready=False; totals recomputed; broadcast)
  - POST /api/staff/orders/<id>/items/<item_id>/void/ — void one item: restock
    (locked), recompute totals; if order PAID with wallet -> partial wallet refund
    of the line total (idempotency voiditem:{item_id}); cash-paid -> record only
  - is_voided in every item payload; struck-through in waiter/owner/customer views
  - Waiter UI: add-items (WaiterNewOrder append mode), item void w/ reason,
    client-side TABLE GROUPING with combined outstanding total per table
R3: WhatsApp/OG link previews — served HTML has zero og: tags (bots get a blank
  shell). Bot-serving branch (nginx UA detection -> Django OG view per tenant menu).
R4: SPLIT-BILL by amount (partial settle ledger) — deliberately separated from R2;
  needs a payment-records model, not a flag. Plus any audit re-run findings.
R5 ✅ (2026-06-11): Final pass — full-journey adversarial review + manual smoke checklist + tag
  restaurant v1.0 complete; then production deploy + real-tenant onboarding.
Token discipline: Sonnet workers, 1 backend + 1 frontend agent per batch, single
focused reviewer, fix-loop max 1.
Catch-net: BACKLOG.md at the repo root collects everything deferred/forgotten —
every batch APPENDS (deferred review findings, audit leftovers, MVP cuts);
reviewed in full during R5 and periodically after. Nothing gets lost silently.

## 4d. OPS program — operator-grade hardening (owner directive 2026-06-13)

**Goal: a restaurant manager opens this at 11:00 and runs every service on it, every
day, and prefers it to their old POS.** Grounded in the 8-lens operator audit
(2026-06-13, ~70 file:line-evidenced findings; full clustered output preserved in the
audit run). Verdict: the service core IS a daily driver; what's missing is the
operator-grade shell around it. Feature backlog is closed — this program is the work.

Execution protocol (unchanged, proven over R1–R5 + post-v1.0 batches): one Workflow
batch per OPS item — Sonnet agents, gates, one focused adversarial reviewer, fix loop,
then personal verification of every critical/major in code, full gates, BACKLOG update,
commit, push. Catch-net: BACKLOG.md.

**Scout (owner directive 2026-06-13): every OPS batch also runs a SaaS-expert scout
agent** — a veteran-multi-tenant-SaaS-architect lens that does NOT review the batch;
it walks the touched area + neighbors and takes working notes on gaps nobody asked
about (tenancy isolation habits, authz consistency, API design debt, ops blind spots,
data-model smells, staff-screen accessibility). Rules: file:line evidence required;
must read OPS_AUDIT.md + §4d + BACKLOG.md first and never repeat them; ≤10 notes,
staff-design-review quality. Notes are triaged into BACKLOG.md ("Scout notes"
section) at ship time — accepted ones become future batch material, rejected ones
are recorded with the reason so they aren't re-flagged.

### OPS-1 — The kitchen never goes dark (service-speed, every-shift wins)
- Screen Wake Lock API on kitchen (+ waiter) with re-acquire on visibilitychange;
  poll must keep running when document hidden (OwnerKitchen.vue:582 skips it today).
- Manifest: drop portrait-primary lock for staff personas (kitchen tablets are
  landscape; manifest.json:8) — per-persona manifest like the driver app already has.
- 86-from-kitchen: sold-out toggle directly on the kitchen screen (today: 5-step
  navigation away to OwnerHome panel).
- Bulk mark-ready endpoint (today: N serial PATCHes per order, OwnerKitchen.vue:667).
- Table picker: TableLink dropdown instead of free-text label (typos split table
  groups + mis-target course firing; WaiterNewOrder.vue:52).
- Realtime quick wins (NOT the full WS rebuild): require/verify Redis channel layer in
  prod (InMemoryChannelLayer is per-process — broadcasts silently lost multi-worker),
  reconnect-forever with a visible "live/polling" indicator (today gives up after 6
  tries), targeted single-order patch on WS event instead of full refetch ×N devices.
- Kitchen in KeepAlive (refresh mid-rush = 1-3s blind skeleton today).

### OPS-2 — Money truth: Z-report & shift close (end-of-day blocker)
- Owner Z-REPORT view: tenant-local SERVICE-DAY window (configurable day-end hour —
  restaurants close at 2am), discrete snapshot: gross, cash vs wallet collected (from
  the ledger), refunds issued, voids (count+value+reasons+who), tips, per-staff
  collected totals. Print stylesheet + CSV export.
- Fix revenue truth: dashboard/digest count COMPLETED(+out_for_delivery delivered)
  only — today PREPARING/READY/CONFIRMED inflate the drawer total
  (sales/views.py:2466); surface a refunds_issued line (today invisible).
- Payment-method correction flow (wrong cash/wallet recording is permanent today)
  with audit trail.
- Surface the audit data that already exists: void_reason, recorded_by_name, payment
  ledger rows → owner order detail + CSV export columns.
- Timezone truth: TruncDate uses UTC (charts bucket late-night orders on the wrong
  day); owner/waiter "today" stats bucket by DEVICE timezone (OwnerOrders.vue:931).
  One tenant-local day helper everywhere.
- Waiter shift summary gains cash/wallet split (handover-usable).

### OPS-3 — Integrity on flaky wifi (the restaurant reality)
- Persist the waiter offline queue (localStorage/IndexedDB) — today a refresh during
  an outage silently discards queued transitions (waiter.js:37).
- Idempotency completion: status-advance PATCH (client key + select_for_update — today
  unlocked last-write-wins), wallet mark-paid (cash path has a key, wallet does not),
  waiter order placement (timeout+resubmit = duplicate kitchen ticket).
- DB-level backstop: unique (order, idempotency_key) on OrderPayment (Redis-down
  currently nullifies cache-based idempotency silently).
- Queue flush hygiene: backoff, discriminate permanent 4xx (drop+surface) from
  transient (retry) — today 400s loop forever; refetch-on-409 so the losing device
  self-heals instead of showing a dead error.
- Staff throttle scoped per-user (shared restaurant NAT exhausts per-IP caps on
  reconnect bursts).

### OPS-4 — Scale fences (year-one data)
- Order list: date-fence active view (service day + open older), drop the JOIN-heavy
  COUNT, real load-more (today: silent 200 cap, full-table scan + COUNT every 15s).
- Customer list: server-side pagination + search (today: one 3k-row JSON, double
  GROUP BY).
- Indexes: Order.customer_phone (4 query paths scan today) + verify filters used by
  sweeps/CRM against Meta.indexes.
- Retention crons: prune NotificationLog (+ WinbackNudge >90d) — analytics/audit
  already pruned, these two grow unbounded.
- revenue.py return-rate subquery (Python IN-list today).

### OPS-5 — Platform cockpit (run the SaaS, not just build it)
- Sentry tenant tagging backend (middleware scope) + frontend (setTag on tenant load)
  — today errors are unattributable to a restaurant.
- /api/health/ checks Celery (beat heartbeat), channel layer, media storage — today
  DB+cache only; a dead worker queues notifications forever silently.
- Admin support view: read-only live order queue per tenant (today support is blind
  over the phone).
- Billing ops: renewal-date column in AdminConsole, invoice_amount set on approve
  (today requires Django /admin/ edit), receipt download reliability.
- Backups: pg_dump sidecar/cron + tested per-tenant-schema restore runbook + rollback
  section in LAUNCH_CHECKLIST (today: one checklist sentence).

### OPS-6 — First impressions & onboarding polish
- Marketing page: NO hardcoded dev domain (config-driven brand domain; today
  'doro.menu.ibnbatoutaweb.com' renders in the hero), real pricing section
  (owner provides prices — config-driven), distinct badge semantics, empty-state CTAs
  (published tenant with 0 orders sees a dead refresh icon today).
- Onboarding friction: CSV import surfaced INSIDE the wizard (exists but hidden
  post-wizard), category-delete shows dish count + offers reassign (silent CASCADE
  today), in-app staff password change (today: delete+recreate for shared-phone
  waiters), per-table QR PDF export, price-0 publish warning.
- Polish sweep: currency-formatter fallbacks (raw toFixed(2) paths), RTL gaps in
  charts/tables, toLocaleString(undefined) → app locale (5 sites), raw backend
  `detail` strings reaching customers (Cart.vue:2008), report print stylesheet,
  maskable PWA icons.

### Decision-gated (owner input needed — NOT scheduled)
- **PSP / online wallet top-up** — THE marketplace blocker per the audit (first-time
  customers must visit in person to load a wallet). Blocked on the owner obtaining a
  PSP account (CMI / Payzone / Stripe-when-available). START THE APPLICATION NOW —
  external lead time dominates. The seam is ready (wallet_service idempotent credits).
- **Self-service signup** vs deliberate manual provisioning — a sales-motion choice,
  not a bug. Decide when tenant volume warrants it.
- **Recurring billing automation** — depends on how subscriptions are actually
  collected (cash vs PSP); revisit with the PSP decision.
- **Plan prices** for the marketing page — owner supplies numbers.

Order: OPS-1 → OPS-2 → OPS-3 → OPS-4 → OPS-5 → OPS-6 (value-first; 1 and 2 are
every-shift operator pain, 3 protects data, 4 protects year-one, 5 protects the
platform, 6 sells it). Each batch ships independently; "continue" = next batch.

## 5. Phased roadmap

### Phase 0 — Super-app foundation ✅ (shipped 2026-06-08)
Brand (kepoli) · `business_type` capability seam · rider acquisition + admin-notify
· customer & rider PWAs + install/download CTAs.

### Phase 1 — Retail / catalog vertical ✅ (shipped 2026-06-10, rename still deferred)
Goal: a non-restaurant shop can list products and sell with pickup/delivery.
- ✅ Vocabulary layer (`useVocabulary` composable; Menu→Catalog, Dish→Product).
- ✅ Product attributes: `Dish.attributes` JSON (sku/barcode/brand/unit, validated
  in `DishSerializer.validate_attributes`, migration menu/0045, commit d4ec3e6).
  Owner form is shop-gated; owner search matches sku/barcode/brand; customers see
  brand · pack-size only. Variants keep riding on `Dish.options`/stock for now.
- ✅ Marketplace: filter/sort by `business_type`; category chips per vertical.
- Still deferred by design: the hard `Dish→Item` schema rename — wait for proven
  retail demand; when done, run on a schema clone first (see §3).

### Phase 2 — Ride-hailing ✅ MVP (shipped 2026-06-10, commit 9aed4b2)
Shipped: `accounts.RideRequest` + migration 0035 (+ `Customer.driver_vehicle_type`,
PlatformConfig ride fares base/per-km/min/commission); `ride_service.py` estimate +
atomic idempotent settle (wallet w/ cash fallback); rider endpoints (estimate/create/
active/cancel/rate) + driver endpoints (offers/accept/status, car-only, first-accept-
wins); RidePage.vue (/ride) + DriverPage rides section; EN/FR/AR. Completed 2026-06-10
(98e9a0d): car-document vetting tier (driver doc uploads + admin car-approve gating
ride offers), time-based fare (PlatformConfig.ride_per_minute, default 0, upfront
quote fixed), driver-rates-rider. Phase 2 is fully shipped. Original plan follows:
Reuse the rider pool + live GPS + wallet; the new primitive is a **trip** (no
tenant, no menu).
- New public-schema `RideRequest` (rider=Customer, pickup/dropoff coords, fare
  estimate, status) parallel to `DeliveryJob`; reuse driver online/GPS/dispatch.
- A new `Profile`-independent flow: customer requests a ride → nearest online
  driver with a `car` vehicle type is offered → accept → live track → fare settled
  from wallet (or cash) → both rate.
- Add `Customer.driver_vehicle_type` (motorbike|car|bicycle) so delivery vs ride
  dispatch can target the right pool. Vetting tiers (car needs licence/insurance
  docs) extend the existing approval flow.
- Pricing: distance/time fare via the existing haversine helper
  (`tenancy/delivery_pricing.py`) generalized to a fare calculator.

### Phase 3 — Payments (deferred, unchanged)
Stripe (or a Morocco-friendly PSP) as a wallet **top-up** funding source only —
`StripeWebhookView` → `wallet_service.credit` with the event id as idempotency
key. Orders/trips still settle from the wallet. No PSP keys are entered by the
assistant; only the seam is built.

## 5b. Courier service ✅ (shipped 2026-06-10, commit 83221d6)
Packages are a KIND of trip: `RideRequest.kind` (ride|package, default ride) +
recipient_name/phone + package_note (migration accounts/0037). Same fares, settle,
sweep, tracking as rides. Dispatch rules: rides -> car + car-doc approved only;
packages -> every approved online driver (any vehicle). recipient_phone: never on
open offers; rider-owned on own trip; assigned driver only otherwise. Customer page
/send-package (SendPackagePage.vue); registry flip made it appear on Home + the
marketplace hub automatically.

## 5c. Per-vertical delivery semantics (the differences that matter)

One driver pool, but each vertical's delivery is a DIFFERENT operation. The platform
must never paper over these with restaurant-shaped assumptions:

| Aspect            | Restaurant            | Store/Grocery/Pharmacy   | Courier (package)      | Ride            |
|-------------------|-----------------------|--------------------------|------------------------|-----------------|
| Merchant step     | KITCHEN cooks (prep)  | Staff PICK shelves       | none — sender hands off| none            |
| Driver waits at   | "the restaurant"     | "the store/pharmacy"    | pickup address         | pickup address  |
| Timing driver     | prep-time on confirm  | pick-time (same field,   | immediate              | immediate or    |
|                   | (DX4)                 | different meaning)       |                        | scheduled       |
| Handover proof    | delivery code (DV1)   | delivery code (DV1)      | handover code on the   | passenger IS    |
|                   |                       |                          | trip (sender shares it)| the proof       |
| Vehicle targeting | any                   | any (big baskets → car,  | any approved driver    | car + car-doc   |
|                   |                       | deferred)                |                        | approved only   |
| Cargo notes       | hot food              | bags/fragile/cold-chain  | package_note free text | n/a             |
|                   |                       | (deferred)               |                        |                 |

Shipped mechanics: every delivery-job payload carries the tenant's business_type
(batched lookup, default restaurant) and the frontends branch wording through
frontend/src/lib/deliveryVocab.js — "At the restaurant" / "At the store" /
"At the pharmacy" across customer tracker, driver cards and admin chips. Packages
carry a rider-only 6-digit handover code (RideRequest.delivery_code, migration
accounts/0040) the courier must enter to complete — same lockout pattern as
restaurant delivery codes; the code never appears in driver or admin payloads.

Deferred (build when a vertical demands it): store pick-time substitutions /
out-of-stock refund deltas; basket-size → vehicle targeting for groceries;
cold-chain / fragile flags; prescription flows (explicitly out of scope — pharmacy
is parapharmacie only).

## 6. Service registry (how new services are added)

The customer-facing super-app surfaces render from ONE registry:
`frontend/src/lib/services.js` (SERVICES array). Each entry: id, emoji icon,
status (live | coming_soon), kind ('lens' = a marketplace business-type lens,
'route' = a dedicated page), accent token. Consumers: Home.vue verticals strip
and the Marketplace.vue hub rail. i18n convention: services.<id>Title /
services.<id>Desc (+ services.comingSoon) in EN/FR/AR.

To add service N: (1) add the registry entry (status coming_soon until built),
(2) add the three i18n keys per locale, (3) when live, point kind/route at the
new page or lens. NO Tailwind classes in services.js (purge safety) — accent
class maps live inside the consuming .vue files. The marketplace lens state is
URL-synced (?type=food|shop): seeded on load, watched on back/forward, written
on chip/hub clicks, cleared by clearFilters.

## 7. Non-negotiables when extending

- **Non-breaking first.** New columns nullable/defaulted; capabilities default to
  the restaurant (full) set. Never silently disable an existing tenant.
- **Reuse the public-schema primitives** — `wallet_service` (atomic+idempotent),
  `DeliveryJob`, `Customer` driver flags, `accounts/notifications.record_notification`,
  `accounts/tasks.enqueue`. Don't fork them per vertical.
- **The catalog rename lands last**, rehearsed on a clone, because it crosses every
  tenant schema.
- **Per-tenant identity is sacred** — Kepoli brands the platform, never the tenant.
