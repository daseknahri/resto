# Platform Vision — Restaurant OS to Delivery Marketplace

> Living document. Updated as phases are completed.
> Last updated: 2026-05-19

---

## The Big Picture

We are building a **B2B2C flywheel platform** — not just a SaaS tool and not just a marketplace.
The two reinforce each other:

```
Restaurant joins SaaS (pays subscription)
    → brings their existing customers to the platform
        → customers get platform-level accounts
            → customers discover other restaurants on the platform
                → more restaurants want in to access that customer base
                    → platform grows without paying for either side
```

This is how Grab beat Uber in Southeast Asia and how Gojek became a super-app — not by spending billions on ads, but by making each participant on one side the acquisition channel for the other.

**Our unfair advantage:** Restaurants using our SaaS tool pay us a fair subscription fee (not Glovo's 30% commission). When we add the marketplace layer, our commission is 8–12%. Restaurants stay because leaving means losing their menu builder, table management, reservations, staff tools, AND their customer base — all switching costs stacked together.

---

## Business Model by Phase

| Phase | Revenue Source | Model |
|---|---|---|
| 1 — SaaS | Monthly subscription per restaurant | B2B |
| 2 — Customer Platform | Subscriptions + wallet float | B2B + B2C |
| 3 — Marketplace | Subscriptions + marketplace commission (8–12%) | B2B2C |
| 4 — Delivery | Subscriptions + commission + delivery fees | Full marketplace |

---

## Architecture Principles (Apply from Day One)

These decisions must be made now, even if the features they enable are months away.

### 1. Customer Identity Lives at Platform Level

The single most important architectural decision.

```python
# backend/accounts/models.py  (shared schema — NOT per tenant)
class Customer(models.Model):
    phone        = CharField(max_length=30, unique=True)   # primary ID
    email        = EmailField(blank=True)
    name         = CharField(max_length=80)
    locale       = CharField(max_length=10, default="en")
    wallet_balance = DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at   = DateTimeField(auto_now_add=True)

class WalletTransaction(models.Model):
    TYPES = [("topup","Top-up"),("payment","Payment"),
             ("refund","Refund"),("bonus","Bonus")]
    customer  = ForeignKey(Customer, on_delete=CASCADE)
    type      = CharField(max_length=20, choices=TYPES)
    amount    = DecimalField(max_digits=10, decimal_places=2)
    reference = CharField(max_length=100)   # order number or topup ref
    tenant    = ForeignKey(Tenant, null=True, blank=True)  # which restaurant
    created_at = DateTimeField(auto_now_add=True)
```

```python
# Order model — add nullable FK now, keep anonymous orders working
class Order(models.Model):
    customer = ForeignKey(
        "accounts.Customer",
        null=True, blank=True,
        on_delete=SET_NULL,
        related_name="orders"
    )
    # ... all existing fields stay unchanged
```

Anonymous orders still work exactly as today.
When a customer creates an account (by phone), past orders are linked retroactively by matching `customer_phone`.
The wallet, ratings, cross-restaurant history, and discovery all follow from this one model.

### 2. Modular Monolith — Not Microservices

Build clean **Django app boundaries** today so each domain can be extracted later without a rewrite.

```
backend/
  accounts/       ← platform users (owners, staff) + Customer model
  menu/           ← tenant-scoped: categories, dishes, options
  orders/         ← tenant-scoped: order lifecycle
  reservations/   ← tenant-scoped: table bookings
  sales/          ← platform: leads, deals, provisioning
  ratings/        ← platform: cross-restaurant ratings (Phase 2)
  wallet/         ← platform: credits, transactions (Phase 2)
  delivery/       ← platform: drivers, jobs, tracking (Phase 4)
```

Each app has its own models, serializers, views, and URLs.
They communicate through foreign keys and internal Python imports — not HTTP calls.
When a module grows big enough, extracting it to its own service is mechanical, not a crisis.

### 3. Feature Flags Gate Everything

Every feature is behind a flag — this enables A/B testing, gradual rollout, and tier gating from a single control plane. Already in place. Keep using it.

---

## Phase 1 — Complete the SaaS Product

> **Goal:** A fully polished, production-ready restaurant operating system that a restaurant would pay for on its own merits, with the platform-level customer foundation silently in place.

This phase is the longest and the most important. A mediocre SaaS product does not generate the customer acquisition flywheel. The product must be genuinely better than what restaurants have today.

---

### 1A — Foundation Work (Architecture, already partially done)

- [x] Multi-tenant infrastructure (django-tenants, subdomain routing)
- [x] Owner/staff auth (roles: `platform_superadmin`, `tenant_owner`, `tenant_staff`)
- [x] Feature flag system per plan
- [x] Super-admin sales console (leads, deals, provisioning)
- [x] Activation token flow (owner receives link, sets password, enters onboarding)
- [x] i18n EN / FR / AR
- [x] **Add `Customer` model at platform level** (shared schema, nullable FK on Order, `WalletTransaction` model, Google OAuth + phone/email OTP auth in place)
- [x] **Phone-based customer lookup endpoint** (unauthenticated, returns orders by phone for a tenant — foundation for history without accounts)

---

### 1B — Menu Builder (partially done, needs polish)

The menu builder is the daily-use tool. It must feel as good as Notion or Linear.

- [x] Categories CRUD (with super-categories)
- [x] Dishes CRUD (name, description, price, image, availability toggle)
- [x] Dish options / add-ons
- [x] Onboarding wizard (StepBrand → StepSuperCategories → StepCategories → StepDishes → StepHours → StepTables)
- [x] Publish / unpublish controls
- [x] **Menu visual themes** — restaurant can pick from 3–5 layout/color themes for their public menu page (cards, list, magazine, dark, light)
- [x] **Hero / cover image** — banner image at top of public menu (not just a logo)
- [x] **Availability scheduling** — dish only available Fri–Sun, or 11:00–15:00 (not just a manual toggle)
- [x] **Allergen tags** — selectable icons (gluten, nuts, dairy, vegan, etc.) displayed on dish cards
- [x] **Multi-language dish names** — owner can add FR/AR translation of dish names and descriptions (uses existing i18n locale system)
- [x] **QR code generation** — auto-generate per-table QR codes, downloadable as PNG/PDF sheet for printing
- [x] **Menu preview mode** — owner sees their menu exactly as a customer would before publishing

---

### 1C — Order Management (partially done, needs completion)

- [x] In-app order creation (customer → checkout → order stored in DB)
- [x] Order status workflow (pending → confirmed → preparing → ready → completed / cancelled)
- [x] Owner orders dashboard (filters, search, status tabs, CSV export)
- [x] Owner note + ETA on order panel
- [x] Real-time polling for new orders
- [x] Sound alerts for new orders
- [x] Print ticket
- [x] **Kitchen Display view** — stripped-down full-screen view showing only active orders (pending/confirmed/preparing), auto-refreshes, large text for kitchen staff on a tablet
- [x] **Order email notification to customer** — when order status changes to confirmed, preparing, ready — send email if customer provided one
- [x] **Order SMS notification** (optional, Twilio/similar) — SMS when order is ready
- [x] **Re-order shortcut** — on order status page, "Order again" button pre-fills cart with the same items

---

### 1D — Waiter Interface (missing, critical for SaaS stickiness)

The waiter interface is what makes the SaaS irreplaceable. If waiters use it every shift, the restaurant can never churn.

- [x] **Lightweight mobile PWA** at `/waiter` route — separate from the owner dashboard
- [x] **Order list** — shows active orders for the logged-in staff's tenant, grouped by table or status
- [x] **One-tap status updates** — large touch targets: Confirm / Preparing / Ready / Done
- [x] **New order push notification** — polling + sound alert on new pending order
- [x] **Table assignment** — order card shows table label; order header identifies the table
- [x] **Shift summary** — at end of shift: count of orders handled, total revenue, average prep time
- [x] **Works on poor WiFi** — optimistic UI (tap confirm, update immediately, sync in background)
- [x] **Offline queue** — if connection drops, status updates queue and flush when back online

---

### 1E — Table & Reservation Management (partially done)

- [x] Table CRUD (label, position, active/inactive)
- [x] Bulk table generation
- [x] Reservation CRUD with timeline notes
- [x] **Reservation calendar view** — week/day grid, color-coded by status, drag to reschedule
- [x] **Auto-confirm reservations** — option to auto-confirm within a time window
- [x] **Reservation reminders** — email/SMS to customer 2h before (uses notification system)
- [x] **Capacity management** — max covers per time slot, overbooking prevention
- [x] **Waitlist** — when fully booked, customer can join waitlist and get notified on cancellation

---

### 1F — Staff & Settings Management (partially missing)

- [x] Owner account creation via activation flow
- [x] **Invite staff** — owner creates staff account (email + temp password sent by email), staff signs in and gets `tenant_staff` role
- [x] **Staff permissions** — owner can grant/revoke specific capabilities (can manage orders, can view revenue, cannot change menu)
- [x] **Working hours** — set open/close times per day, displayed on public page, blocks orders outside hours
- [x] **Holiday / closure dates** — mark specific dates as closed
- [x] **Delivery settings** — enable/disable delivery, define delivery radius or zones, set minimum order, delivery fee
- [x] **Custom receipt message** — owner writes a thank-you note shown on order confirmation

---

### 1G — Basic Per-Restaurant Ratings (Phase 1 entry point for ratings)

No platform-wide identity needed yet. Rating is tied to a completed order.

- [x] **Post-order rating prompt** — after order status reaches `completed`, order status page shows 1–5 star rating + optional comment field
- [x] **Rating model** — `Rating(order, score 1-5, comment, created_at)` — tenant-scoped (migration 0014_rating)
- [x] **Ratings display** — `rating_summary {average, count}` added to `/api/meta/` response so frontend can display it in the restaurant header
- [x] **Owner ratings dashboard** — `GET /api/owner/ratings/` returns count/average + full list; `?format=csv` exports to spreadsheet

---

### 1H — Analytics for Owners (missing, important for retention)

Owners who see their data stay subscribed. This is a retention tool as much as a feature.

- [x] **Revenue dashboard** — daily/weekly/monthly revenue chart, total orders, average order value
- [x] **Popular dishes** — ranked by order frequency and revenue contribution
- [x] **Peak hours heatmap** — orders by hour of day / day of week
- [x] **Order funnel** — how many carts started vs completed (conversion rate)
- [x] **Customer return rate** — % of orders from returning phone numbers (even without accounts)
- [x] **Export** — CSV download of any date range

---

### 1I — Billing & Subscription Management

- [x] Plan model and feature flags
- [x] Manual upgrade flow (admin confirms payment, switches plan)
- [x] **Owner billing page** — shows current plan, renewal date, payment history
- [x] **Upgrade request flow** — owner clicks "Upgrade", creates a request, admin sees it in console and confirms
- [x] **Invoice generation** — PDF invoice per payment, stored and accessible by owner
- [x] **Grace period handling** — if payment overdue, show warning but don't cut service for 7 days
- [x] **Plan limits enforcement** — e.g., Starter: max 50 dishes, max 2 staff accounts; Growth: unlimited

---

### 1J — Customer-Facing Experience Improvements

- [x] Cart and checkout
- [x] Order status page with polling
- [x] WhatsApp order handoff (Starter tier)
- [x] **Recent orders (localStorage)** — "Your recent orders" section at bottom of menu page, links to status pages of last 5 orders from this device
- [x] **Guest order lookup** — "Find my order" page: enter phone number → see all orders from that tenant on this device's last visit
- [x] **Menu search** — search bar on public menu page filters dishes by name/description in real time
- [x] **Dietary filter** — filter menu by allergen tags (vegan, gluten-free, etc.)
- [x] **Estimated wait time display** — if owner sets ETA on an order, customer sees it prominently on status page with countdown
- [x] **Share dish** — share button on dish detail generates a link that opens the dish in context

---

### 1K — Platform & Operations

- [x] Docker Compose deployment
- [x] SSL / wildcard subdomain routing
- [x] Daily DB backups
- [x] **Sentry error tracking** wired to both Django and Vue frontend
- [x] **Uptime monitoring** — health check endpoint (`/api/health/`) with DB + cache probes; point UptimeRobot/BetterUptime at it
- [x] **Admin audit log** — every provisioning, plan change, and activation recorded with timestamp and actor
- [x] **Tenant data export** — owner can request a full export of their data (GDPR compliance foundation)
- [x] **Tenant deletion / offboarding** — clean process to deactivate and archive a tenant

---

### Phase 1 Success Criteria

Before moving to Phase 2, all of the following must be true:

1. At least 10 paying restaurants using the platform in production
2. Waiter interface in daily use at 3+ restaurants
3. Average setup-to-publish time under 30 minutes for a new tenant
4. Owner churn rate under 5% monthly
5. Customer model at platform level is in production (even if no customer-facing auth yet)
6. Per-restaurant ratings are live and collecting data

---

## Phase 2 — Activate the Customer Platform

> **Goal:** Give customers a reason to have a platform account. Unlock cross-restaurant history, a wallet, and the foundation for marketplace discovery.
> **Revenue added:** Wallet float interest + optional transaction fee on wallet payments.

### 2A — Customer Accounts (frontend)

- [x] Customer sign-up (phone + OTP, or email + password)
- [x] Customer profile page (name, phone, email, locale preference)
- [x] Secure JWT session for customers (separate from owner/staff auth)
- [x] "Sign in to save your order" prompt at checkout — optional, never blocking
- [x] Retroactively link existing orders to account (match by `customer_phone`)

### 2B — Cross-Restaurant Order History

- [x] "My Orders" page in customer app — all orders across any restaurant on the platform
- [x] Re-order button on any historical order
- [x] Order detail with full item list, status timeline, and rating prompt if unrated

### 2C — Wallet / Credits System

The wallet is a **credits system first** — buy platform credits, spend at any partner restaurant.

- [ ] **Top-up credits** — customer buys 50 credits, may receive a bonus (e.g., 5 free) as incentive (requires payment processor integration)
- [x] **Pay with credits at checkout** — if customer has a balance, "Pay with credits" appears as payment option
- [x] **Wallet transaction history** — customer sees every credit spent/received with restaurant name and date
- [ ] **Partner restaurant deal** — restaurants who accept credit payments pay reduced commission (their incentive to participate)
- [x] **Wallet balance in header** — logged-in customers see their balance in account page and badge
- [x] **Refund to wallet** — when an order is cancelled, amount returns to wallet automatically
- [x] **Bonus campaigns** — platform admin can issue bonus credits to all customers, or to customers of specific restaurants

> **Regulatory note:** In most jurisdictions, a "credits" system tied to a specific platform avoids the e-money license requirements that apply to general-purpose wallets. Consult a local lawyer before launching in a new country.

### 2D — Cross-Restaurant Discovery

- [x] Simple restaurant directory page on the main domain
- [x] Filter by cuisine type, city, average rating
- [x] Restaurants must opt-in to appear (default: off — they stay private/QR-only)
- [x] Restaurant card shows name, cuisine, rating, open/closed status, min order

### 2E — Platform-Level Ratings (upgrade from Phase 1)

- [x] Ratings are now tied to the platform Customer account (not just anonymous)
- [x] A customer's rating history is visible on their profile
- [x] Restaurant can see if a customer has a history of cancellations or low-effort reviews
- [x] Owner rates customer after a completed order: 1–5 stars (hidden from customer, visible to other restaurants — inDrive-style trust score)
- [x] Customers with consistently low trust scores can be flagged (shown to restaurant before confirming)

---

## Phase 3 — Marketplace Mode

> **Goal:** Turn the restaurant directory into a genuine marketplace. Restaurants compete for platform customers, not just their own QR code traffic.
> **Revenue added:** Commission on marketplace orders (8–12% vs Glovo's 30%).

### 3A — Marketplace Storefront

- [x] Full public marketplace at main domain (e.g., `yourdomain.com/order`)
- [x] Location-aware restaurant listing (sort by distance using customer's location)
- [x] Advanced filters: cuisine, dietary tags, price range, delivery/pickup, ratings
- [x] Real-time open/closed status based on restaurant working hours

### 3B — Unified Checkout

- [x] Customer can order from a marketplace restaurant without visiting the subdomain
- [x] Checkout uses platform-level customer account + wallet
- [x] Order lands in the restaurant's existing order dashboard — no change for the owner

### 3C — Merchant Analytics Upgrade

- [x] Restaurant owner can see how many orders came from marketplace vs direct QR
- [x] Marketplace-driven orders displayed separately in revenue dashboard
- [x] Commission breakdown visible on monthly invoice

### 3D — Promotions Engine

- [x] Restaurant creates a promotion (e.g., "20% off orders over 25€ on Fridays")
- [x] Promotions appear as badges on marketplace listing cards
- [x] Platform-wide flash sales (platform sponsors a discount, restaurants opt in)

---

## Phase 4 — Delivery Platform

> **Goal:** Add the delivery layer on top of the marketplace. This is the hardest phase — do not start until Phase 3 has validated demand and operational density.
> **Revenue added:** Delivery fee (fixed or distance-based) + higher commission tier for delivery orders.

> **Warning:** Delivery is not primarily a software problem. It is a logistics and supply problem. The driver app is the smallest part. Managing driver supply, zone coverage, on-time rates, and disputes is a full-time operations team.

### 4A — Driver App (separate mobile app, React Native or Flutter)

- [ ] Driver registration (platform-level Customer with `is_driver=True` flag)
- [ ] Driver availability toggle (online/offline)
- [ ] Incoming delivery job notifications with accept/decline
- [ ] Live order tracking view (pickup address → delivery address navigation)
- [ ] Delivery confirmation (photo + signature optional)
- [ ] Driver earnings dashboard

### 4B — Delivery Job Model

```python
class DeliveryJob(models.Model):
    order        = OneToOneField(Order, on_delete=CASCADE)
    driver       = ForeignKey(Customer, null=True, on_delete=SET_NULL,
                              limit_choices_to={"is_driver": True})
    status       = CharField(choices=[
                       "searching", "assigned", "at_restaurant",
                       "picked_up", "delivered", "failed"])
    driver_lat   = FloatField(null=True)
    driver_lng   = FloatField(null=True)
    assigned_at  = DateTimeField(null=True)
    picked_up_at = DateTimeField(null=True)
    delivered_at = DateTimeField(null=True)
    delivery_fee = DecimalField()
```

- [x] `DeliveryJob` model (public schema, loose FK to tenant order, delivery fee, driver payout, timestamps)
- [x] `DeliveryZone` model (polygon as JSON, center lat/lng, approx radius, city, active flag)
- [x] Driver fields on `Customer` (`is_driver`, `is_driver_online`, `driver_lat/lng`, `driver_position_updated_at`)
- [x] `Profile` model gains `delivery_zone_id` + `delivery_radius_km`
- [x] Driver registration, status toggle, position update endpoints
- [x] Driver job list, accept, and status update endpoints
- [x] Admin delivery job list + manual create endpoints

### 4C — Real-Time Tracking

- [x] Customer sees driver position on the order status page (SSE streaming + polling fallback)
- [x] `OrderTrackingView` — GET `/api/marketplace/track/<order_number>/` returns driver name, status, position, addresses
- [x] `?stream=1` mode streams SSE events (polls every 3s, caps at 90s to protect Gunicorn workers)
- [x] Frontend `MarketplaceOrderStatus.vue` polls tracking every 10s, shows driver panel with Google Maps link
- [ ] Restaurant sees driver's ETA to pickup on the order dashboard
- [ ] Driver arrival notification to restaurant ("Driver is 2 minutes away")

### 4D — Three-Way Ratings

- [x] Customer rates the driver (speed, professionalism) — on order status page after delivery
- [x] Driver rates the customer — via driver app / API
- [x] Restaurant rates the driver — via `role=restaurant` on rating endpoint
- [x] All ratings stored on `DeliveryJob` — `customer_driver_rating`, `driver_customer_rating`, `restaurant_driver_rating` (+ notes)
- [x] `DeliveryRatingView` — POST `/api/marketplace/track/<order_number>/rate/` accepts `role` + `score` + `note`
- [ ] Rating summaries surfaced in driver profile / admin views

### 4E — Zone Management

- [x] Platform admin defines delivery zones per city (polygon as JSON array of lat/lng points)
- [x] `AdminDeliveryZoneListCreateView` + `AdminDeliveryZoneDetailView` (CRUD API)
- [x] `AdminDeliveryZones.vue` — admin console page for managing zones (table + create/edit drawer)
- [x] Restaurants configure their delivery zone (`OwnerDeliveryZoneView`) and radius (`OwnerDeliveryRadiusUpdateView`)
- [ ] Dynamic delivery fee based on distance tiers

---

## Technical Debt to Avoid

| Temptation | Why to avoid it | What to do instead |
|---|---|---|
| Microservices from day one | Adds 10x operational complexity with no team to support it | Modular monolith; extract when a module has a dedicated team |
| Separate database per module | Kills cross-module queries needed for analytics and ratings | One PostgreSQL instance, separate schemas only where legally required |
| Rebuild frontend as native app | PWA covers 95% of use cases with zero app store friction | Ship PWA first; native app is Phase 3–4 if metrics justify it |
| Build billing from scratch | Subscriptions, invoices, dunning, proration — months of work | Use Stripe Billing or Paddle; integrate via webhooks |
| Launch delivery in multiple cities at once | Driver supply is local; spreading thin kills the network effect | One city only, achieve 80% zone coverage, then expand |

---

## The One-Pager (for pitching to restaurants)

> "You pay Glovo 30% of every order — forever.
> You pay us a flat monthly fee for your own ordering app, your own customer data, and your own brand.
> Your customers become yours, not Glovo's.
> When you're ready to reach new customers beyond your QR code, our marketplace is there — at 10% commission, not 30%."

---

## What We Are Building — Summary

```
Today (Phase 1):   Best-in-class restaurant OS. Subscription SaaS.
Tomorrow (Phase 2): Customer accounts + wallet. The data layer.
Later (Phase 3):   Opt-in marketplace. The discovery layer.
Future (Phase 4):  Delivery network. The logistics layer.
```

Each phase pays for itself before the next one starts.
No phase requires the previous one to be torn down.
The multi-tenant architecture built in Phase 1 is the foundation that all four phases share.
