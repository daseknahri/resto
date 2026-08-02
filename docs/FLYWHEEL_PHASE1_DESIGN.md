# Flywheel Phase 1 — Design (QR soft-capture + discovery bridge)

> 2026-08-02 · grounded in a 3-lens read of the live code (order→customer signal, consumer
> hub/marketplace, phone-OTP identity). Companion to
> [`PRODUCT_VISION_AND_REBUILD_PLAN.md`](PRODUCT_VISION_AND_REBUILD_PLAN.md). This is the plan
> for the multi-PR Phase 1 build; each PR links back here.

## The goal (one line)
Turn the anonymous QR/guest diner into a **platform customer with a durable relationship to the
business** — so they reorder through the marketplace and the platform captures the transaction.

## What the code already gives us (reuse, don't rebuild)
- **Guest orders already place** with `Order.customer = None`; the diner's phone is captured as
  free text (`Order.customer_phone` / `customer_phone_digits`, btree-indexed). `MarketplaceMenuPage`
  collects the phone and stamps `mktLastOrderNumber/At/Slug` in localStorage, then routes to a
  status page with a "just placed" banner — the natural claim anchor.
- **The identity half of "verify to claim" is done.** `POST /api/customer/auth/phone/verify/`
  (`CustomerPhoneVerifyView`) validates an OTP, get-or-creates a `Customer` by phone, sets
  `phone_verified=True`, and establishes the `session["customer_id"]`. `CustomerAuthModal` is a
  reusable phone-first OTP surface. `Customer.phone_digits` is btree-indexed — the join key exists
  on both sides.
- **The cross-tenant history index auto-syncs off `customer_id`.** `mirror_order_to_public_index`
  (`menu/signals.py:25`) upserts a `CustomerOrderRef` **iff `Order.customer_id` is set**. So the
  moment we stamp a guest order's `customer_id`, its history row (with items snapshot + vertical)
  materializes for free.
- **The hub already reads `CustomerOrderRef`** for its "Order again" rail and per-vertical usage.

## The one missing keystone
**There is no claim/back-link flow.** No production code ever sets `Order.customer` after creation,
so an anonymous QR/guest order stays `customer=None` **forever** — even if that diner later signs in.
That single gap is why the flywheel never starts.

## The soft-capture flow (the locked "frictionless + one-tap" choice)
1. Diner orders as a guest (no wall) — **already works**. Phone captured as free text.
2. On the post-order status page, a one-tap CTA: *"Save this order & earn points — verify your
   phone."*
3. One tap opens `CustomerAuthModal` (phone OTP) — **already works** → session established.
4. **NEW: claim.** The client calls the claim endpoint with the just-placed `{tenant_slug,
   order_number}` (from the localStorage stamp). The server enters that tenant's schema, finds the
   order, and — **only if the order is unclaimed and its `customer_phone_digits` match the verified
   customer's `phone_digits`** — sets `order.customer_id`. Saving fires the existing signal →
   `CustomerOrderRef` materializes.
5. The diner is now a platform customer with this business in their history → reorders via the
   marketplace.

### Claim security model
The OTP proves the caller owns the phone; the **phone-digits match** binds that phone to the specific
order. Both must hold. An order already linked to another customer is refused (`409`). Claiming is
idempotent (already mine → ok). The claim runs inside the order's **tenant schema** (orders are
tenant-local), unlike the OTP endpoints which run in public.

## Data-model decisions
- **"My businesses" (implicit) = aggregation over `CustomerOrderRef`**, NOT a new mirror table.
  `values('tenant_id','restaurant_slug','restaurant_name','vertical').annotate(last=Max(order_created_at),
  count=Count('*'))` gives the relationship with zero new write-path and **no signal double-count
  risk** (the signal re-fires on every status change; a counter maintained there would overcount).
- **Explicit favorite/follow = a new `CustomerTenantFollow`** (public schema), mirroring the existing
  `CustomerTenantOptOut` shape exactly: `(customer FK, tenant_id IntegerField, restaurant_name/slug,
  vertical, created_at)`, `unique_together(customer, tenant_id)`. This backs the marketplace heart
  (today localStorage-only, per-device) and lets a diner pin a business they haven't ordered from.
- **The order signal stays unchanged.** No new model is written from it; setting `customer_id` on the
  claimed order already cascades into `CustomerOrderRef` via the existing upsert.

## PR sequencing (each independently gate-verified)
1. **PR-1 (keystone): order-claim soft-capture.** Backend claim endpoint (schema-scoped, phone-match
   guarded, idempotent) + tests; frontend claim CTA on the marketplace post-order status page wired
   through `CustomerAuthModal`. Converts guest marketplace orders → attributed → they appear in the
   existing "Order again" rail. *Marketplace-first, cleanest path.*
2. **PR-2: "My businesses" surface.** `GET /api/customer/businesses/` (aggregate `CustomerOrderRef` +
   merge follows) + `CustomerTenantFollow` model + follow/unfollow endpoint; hub "My businesses" rail;
   bind the marketplace heart to the server.
3. **PR-3: marketplace personalization.** Give `MarketplaceView` optional customer auth so rows can
   carry `is_followed` and a "from businesses you follow / visited" section can exist.
4. **PR-4: tenant-storefront QR dine-in claim.** Extend the claim CTA to the tenant `OrderStatus.vue`
   (the actual table-QR path) and relax `Cart.vue`'s guest phone capture for dine-in. *(Bigger — the
   dine-in cart currently drops `customer_phone`.)*

## Owner decisions to surface (not blocking PR-1)
- **Auto-list on menu-publish** (marketplace default opt-in → auto): needed for discovery but changes
  what businesses are publicly exposed — a consent call worth confirming before flipping. Deferred to
  its own PR with the decision called out.
