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

## 6. Non-negotiables when extending

- **Non-breaking first.** New columns nullable/defaulted; capabilities default to
  the restaurant (full) set. Never silently disable an existing tenant.
- **Reuse the public-schema primitives** — `wallet_service` (atomic+idempotent),
  `DeliveryJob`, `Customer` driver flags, `accounts/notifications.record_notification`,
  `accounts/tasks.enqueue`. Don't fork them per vertical.
- **The catalog rename lands last**, rehearsed on a clone, because it crosses every
  tenant schema.
- **Per-tenant identity is sacred** — Kepoli brands the platform, never the tenant.
