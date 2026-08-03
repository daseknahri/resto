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

## 3c decision (owner delegated: "make the right call") — **Option B: shared order service**

A deep read of the two order backends (`PlaceOrderView` menu/views.py:2619 vs `MarketplacePlaceOrderView`
accounts/views.py:4288) settled the backend-convergence fork:

- **Chosen — Option B: extract a shared `place_order` service** in `menu/order_service.py` (the seam
  already exists — delivery-fee/tip/prepay are already extracted there) that BOTH thin views call. It
  centralizes the ~600 lines of duplicated item-resolution / pricing / promo / loyalty / stock / wallet /
  order-creation logic while each view keeps its own auth, tenant resolution (host vs slug+schema_context),
  notifications, and response contract. It's schema-agnostic (operates on the caller's established schema —
  `connection.schema_name` is already correct in both), so the shared `debit_wallet` key pattern ports
  unchanged. **Test-verifiable** (unlike the visual 3b), lower-risk, and incremental/reversible slice-by-slice.
- **Rejected — Option A: merge the two endpoints** (`/place-order/` gains an optional `restaurant`). It's
  where all the risk lives: the endpoint is tenant-urlconf-only + assumes an ambient tenant schema; merging
  forces reconciling two auth models, two throttles, and every divergence below onto one path — silently
  changing pricing/security for one client population and breaking one response contract. Only worth
  revisiting *after* Option B proves the shared core.

**Divergences that MUST stay explicit parameters (current per-caller default), never flattened —**
they are money/security-affecting: happy-hour rule source (all-active `get_all_active_hh_rules` vs
time-windowed `get_active_happy_hours`); open-now gate (`_is_restaurant_currently_open` vs
`_compute_is_open_now`, the latter honours closure_dates + temp-disable); **delivery verification**
(storefront requires verified account + phone; marketplace requires only signed-in); tip; table/dine-in;
promo-code vs flash-sales; commission + `source=MARKETPLACE`; staff preview/attribution/coursing;
owner notifications (storefront: dispatch+WhatsApp+push+WS; marketplace: dispatch only); response shape.

**Sliced extraction plan (each PR behavior-identical + tests ported/added):**
1. **Item resolution** — `resolve_available_dishes(slugs)` + `resolve_option_map(option_ids)` (byte-identical
   queries in both; pure, pre-transaction, zero money risk). ✅ **slice 1 — #113.**
2. **Per-item validation + line building** — `price_line_options(dish, option_ids, options_map, base_unit_price)`
   centralizes the OPS-5f option binding + `stale_options` guard, the B2 group-select enforcement, and the
   `price_delta` accumulation + snapshots (byte-identical in both loops). ✅ **slice 2.**
   Key call: the helper takes the caller's already-happy-hour-adjusted **base unit price** rather than calling
   `effective_unit_price` itself — so each view keeps its own happy-hour rule source AND its distinct
   `effective_unit_price` patch target (storefront patches `menu.views.effective_unit_price`;
   marketplace/others patch `menu.pricing.effective_unit_price`). Per-line qty parsing (serializer-trusted vs
   `max(1,min(99,…))` clamp), note truncation, and course/seat stay per-view.
3. **Stock lock/decrement + component** — `deplete_stock(locked_dishes, stock_updates, pk_to_slug,
   comp_stock_agg, comp_pk_to_name)` centralizes the dish + combo-component validate/decrement over the
   caller's `select_for_update`-locked rows (a decrement to 0 flips `is_available`+`stock_auto_zeroed`).
   The lock and the `_OutOfStock` raise stay in each view with the transaction; the helper **returns** the
   first sold-out slug/name instead of raising (the caller re-raises inside the same atomic block, so a
   short component still rolls back the dish decrements exactly as before). ✅ **slice 3a.** Works with the
   existing `@patch("menu.views.Dish.objects")` tests because `.objects` is a class attribute — patching it
   is path-independent (`menu.views.Dish` **is** `menu.models.Dish`).
   - **Ingredient depletion (B3 Phase 2)** — `deplete_ingredients(order_items_data, dishes_map)` (recipe BOM
     → `Ingredient.stock_quantity` `F()` decrement; negative allowed = variance flag). ✅ **slice 3b.** Split
     from 3a because it references `RecipeLine`/`Ingredient`, which order-path tests `@patch("menu.views.
     RecipeLine")` as a *name* binding (not `.objects`) — a `menu.models`-based helper isn't intercepted and
     would hit the real DB. 3b repointed those to `@patch("menu.models.RecipeLine")` in test_happy_hour,
     test_course_sequencing, test_station_snapshot + the 3 test_ingredients source checks. The marketplace's
     `_inject_module("menu.models", …)` tests (test_a4, test_r15b) keep working because the helper's
     **function-local** `from menu.models import` re-resolves the injected module at call time.
4. Loyalty sizing/earn; the bounded promo-counter bump; wallet settle.
Each slice lands as its own gate-verified PR; the frontend cart-model unification (the visual half) is
deferred with 3b to a UI/UX pass.
