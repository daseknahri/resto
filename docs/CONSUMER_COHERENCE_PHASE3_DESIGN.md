# Phase 3 — Consumer Coherence (unify the two front-ends)

> 2026-08-02 · grounded in a 3-lens code map (tenant storefront flow, marketplace flow,
> host-dispatch/duplication). Companion to
> [`PRODUCT_VISION_AND_REBUILD_PLAN.md`](PRODUCT_VISION_AND_REBUILD_PLAN.md). Multi-PR phase;
> each PR links back here.

## The problem (one line)
There are **two consumer front-ends sharing a login** — the per-tenant storefront (`CustomerLayout`,
resolved by subdomain host) and the platform marketplace (`LandingLayout`, resolved by `:slug`) — with
large duplicated logic and two separate cart models. Same app, two implementations.

## What's already shared (build on this)
- **Order-item wire format is identical:** `{ slug, qty, option_ids?, note? }` on both `/place-order/`
  and `/marketplace/order/`.
- **Rating** (`POST /orders/<n>/rate/`) and **guest-claim** (`POST /customer/orders/claim/`) endpoints
  are identical in both flows; both mint an `idempotency_key`.
- Shared components already: `DeliveryTracker`, `CustomerAuthModal`, `AppIcon`; shared utils
  `useI18n`, `businessHours`, `idempotency`.

## The duplication (the actual work)
| Job | Tenant storefront | Marketplace | Status |
|---|---|---|---|
| Cart | Pinia `stores/cart.js`, `cart:${host}` (per-host, rich: keys/notes/option_labels/reorder/express) | inline `ref([])` in `MarketplaceMenuPage`, `mkt:cart:${slug}` (per-slug, slug-keyed, no note) | **two models** |
| Delivery pricing | `Cart.vue:~1176-1310` | `MarketplaceMenuPage.vue:~1370-1453` | **copied verbatim** |
| Saved addresses | `/customer/addresses/` CRUD in `Cart.vue` | same CRUD re-implemented in `MarketplaceMenuPage` | duplicated |
| Rating UI + error map | `OrderStatus.vue` | `MarketplaceOrderStatus.vue` ("mirrors OrderStatus") | duplicated |
| Happy-hour price helpers | both | both | duplicated |
| Order-status stepper | `OrderStatusTimeline.vue` (rich, WS) | inline 6-step markup, poll-only | duplicated |
| Reorder | `useReorder` → `/reorder-resolve/` (availability-safe) | inline rebuild, options dropped | divergent |

## Deep fork (the keystone, deferred)
The tenant side assumes **one tenant per host** (host-scoped stores + `cart:${host}` keys); the
marketplace is **slug-parameterized** with its own API surface and threads `restaurant=<slug>` through
every call. Collapsing them needs a shared **tenant-context abstraction** (slug- OR host-derived) and
backend convergence of the two place-order / order-status endpoints. High risk — do LAST, and surface
the backend-convergence decision to the owner first.

## Phased plan (lowest-risk-first)

- **Phase 3a — shared logic (composables/libs; pure, zero host coupling, no behavior change):**
  1. `lib/deliveryPricing.js` — the verbatim haversine / `ROAD_FACTOR` / `validCoord` / distance→fee /
     out-of-range / min-gap math, as pure functions + unit tests; both pages use it. **First PR.**
  2. Rating composable/component (identical submit + error-code map).
  3. Happy-hour price helpers; saved-address CRUD composable.
- **Phase 3b — presentational convergence (low/medium risk):**
  4. Marketplace adopts `OrderStatusTimeline.vue` (drop its inline stepper).
  5. Marketplace menu adopts `DishCard.vue` + shared option-group sheet.
- **Phase 3c — the keystone (high risk, deferred, owner-surfaced):**
  6. One cart model keyed by tenant-slug (the Pinia store is the richer superset) replacing both.
  7. Unified menu data contract; unified order submission (one endpoint / `/place-order/` gains an
     optional `restaurant`); unified order-status + realtime (bring WS to the marketplace); unified
     server-backed history retiring the `mkt*`/per-host localStorage schemes.

## Sequencing rationale
3a is a pure de-duplication wedge — both sides already agree on the backend contracts, so composables
share cleanly with no host coupling and no user-visible change. It removes the drift-bug risk of
copy-pasted money math first, and establishes the shared-code pattern before the invasive 3c cart/host
unification (which is gated on a tenant-context abstraction + a backend-convergence decision).
