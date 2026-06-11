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
R5: Final pass — full-journey adversarial review + manual smoke checklist + tag
  restaurant v1.0 complete; then production deploy + real-tenant onboarding.
Token discipline: Sonnet workers, 1 backend + 1 frontend agent per batch, single
focused reviewer, fix-loop max 1.

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
