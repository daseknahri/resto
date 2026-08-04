# Kepoli — Feature & Surface Map (current state)

> **What the app actually does _today_, per surface.** This is the "know what's built" companion
> to the canonical set — read alongside [`ARCHITECTURE.md`](ARCHITECTURE.md) (*how* it's built),
> [`PRODUCT_VISION_AND_REBUILD_PLAN.md`](PRODUCT_VISION_AND_REBUILD_PLAN.md) (*where* it's going +
> the locked owner decisions), [`NEXT_SESSION.md`](NEXT_SESSION.md) (*what to do next*), and
> [`RISK_REGISTER.md`](RISK_REGISTER.md) (known debt).
>
> _Derived from the code (router + urlconfs + models) on 2026-08-04. It is a **snapshot** — when it
> disagrees with the code, the code wins; fix this doc. `ARCHITECTURE.md` remains the source of
> truth for the model; this is the surface inventory that would otherwise take a new session hours
> to reconstruct._

## Read the whole app in 5 minutes — the load-bearing files

| To learn… | Read |
|---|---|
| Every route + all gating (host, auth, role, capability, vertical) | `frontend/src/router/index.js` (one file; `beforeEach` guard) |
| Every endpoint | `backend/config/urls.py` (tenant + shared) + `backend/config/shared_api_urls.py` (public); an additive **`/api/v1/…` alias** mirrors every `api/…` route |
| Tenancy + the capability seam | `backend/tenancy/models.py` (`Tenant`/`Plan`/`Profile`) + `backend/accounts/verticals.py` |
| The money core | `backend/accounts/wallet_service.py` + `backend/accounts/models.py` |
| Which host serves which app | `frontend/src/lib/runtimeHost.js` |

## The surfaces & host dispatch

One host-dispatched SPA. `runtimeHost.js` + the router's `beforeEach` decide which surface renders:

- **Platform-public host** (e.g. `kepoli.app`) → the **consumer super-app** (`/` redirects to `/hub`).
- **Tenant subdomain** (`<slug>.…`) → that restaurant's **storefront** (the QR/dine-in landing).
- **Platform-admin host** → the **admin/sales console** (guard forces navigation here; needs `session.isPlatformAdmin`).

Layouts (`frontend/src/layouts/`): `LandingLayout`, `CustomerLayout`, `OwnerLayout`, `WaiterLayout`, `AdminLayout`, `PlainLayout` (chrome-less).

---

## 1. Consumer / super-app

### 1a. Super-app + marketplace — `LandingLayout`, `meta.interface:"landing"` (platform-public host)
| Route | Page | Notes |
|---|---|---|
| `/` | `Home.vue` | On the platform host → redirects to `super-app-hub`; on a tenant host it's the B2B owner-marketing page |
| `/hub` | `SuperAppHub.vue` | The super-app service grid (the true consumer home) |
| `/order` | `Marketplace.vue` | Discovery/browse across restaurants |
| `/order/:slug` | `MarketplaceMenuPage.vue` | A restaurant's marketplace menu (order pickup/delivery/scheduled) |
| `/order/:slug/status/:orderNumber` | `MarketplaceOrderStatus.vue` | Marketplace order tracker |
| `/account` | `CustomerAccount.vue` | Identity, wallet, order history, follows (a mega-page) |
| `/ride` | `RidePage.vue` | `meta.vertical:"rides"` — **gated off by default** (see §5) |
| `/send-package` | `SendPackagePage.vue` | `meta.vertical:"courier"` — live by default |
| `/track/:token` | `RecipientTrackPage.vue` | Public, no-auth package tracking |
| `/business`, `/demo`, `/get-started` | `Home.vue` / `DemoLanding.vue` / `LeadCapture.vue` | Owner-acquisition funnel |
| `/directory` | → redirect to `marketplace` | The old orphaned discovery surface, now redirected |

### 1b. Tenant storefront — `CustomerLayout`, `meta.interface:"customer"` (tenant subdomain)
Where QR/dine-in scanners land. The guard bounces these routes to `demo` on the platform host.
| Route | Page | Notes |
|---|---|---|
| `/t/:tableSlug` | `Menu.vue` | Dine-in QR table link |
| `/m/:menuSlug`, `/browse`, `/browse/:slug`, `/browse/:category/:dish` | `Menu.vue` / `MenuSelect.vue` / `CategoryPage.vue` / `DishPage.vue` | Storefront catalog browsing |
| `/cart` | `Cart.vue` | Storefront cart + checkout |
| `/orders/:orderNumber`, `/find-my-order` | `OrderStatus.vue` / `FindMyOrder.vue` | Storefront order tracking |
| `/reserve`, `/r/:token` | `ReservationPage.vue` / `ReservationManage.vue` | Table reservations |

**Consumer capabilities:** one platform identity (`accounts.Customer`) + one global wallet & loyalty; cross-restaurant order history via the public `CustomerOrderRef` mirror; follow/"my businesses" (`CustomerTenantFollow`); in-app notifications inbox; referrals. See `PRODUCT_VISION` for the flywheel gaps that remain.

---

## 2. Restaurant owner + staff (the POS)

### 2a. Owner — `/owner/*`, `OwnerLayout`, `meta:{requiresAuth, tenantEditorOnly, interface:"owner"}`
Guard: owner or admin-level; a `tenant_staff` user is redirected to `/waiter`.
| Route | Page | Notes |
|---|---|---|
| `/owner` | `OwnerHome.vue` | Dashboard / live focus |
| `/owner/onboarding` | `onboarding/Wizard.vue` | Setup wizard — steps in `frontend/src/onboarding/Step*.vue` (Start, Brand, Theme, SuperCategories, Categories, Dishes, Publish) |
| `/owner/orders` | `OwnerOrders.vue` | Orders board |
| `/owner/kitchen` | `OwnerKitchen.vue` | KDS — `requiresCapability:"kitchen"` |
| `/owner/tables` | `OwnerTables.vue` | `requiresCapability:"tables"` |
| `/owner/reservations` | `OwnerReservations.vue` | `requiresCapability:"reservations"` |
| `/owner/menu-builder`, `/owner/analytics` | `OwnerMenuBuilder.vue` / `OwnerAnalytics.vue` | Catalog + analytics |
| `/owner/z-report` | `OwnerZReport.vue` | Cashier close-shift / Z-report (`/owner/shift-close` redirects here) |
| `/owner/{profile,staff,promotions,loyalty,ratings,customers,notifications,wallet,launch}` | resp. pages | Config + growth surfaces (`OwnerStaffPage`, `OwnerWallet`, `OwnerLaunchSuccess`, …) |

### 2b. Staff / POS — `WaiterLayout`, `meta:{requiresAuth, tenantEditorOnly, interface:"waiter"}`
| Route | Page | Notes |
|---|---|---|
| `/waiter` | `WaiterPage.vue` | Waiter/cashier POS: tables, order items, payments, clock-in (a mega-page, ~3.7k lines) |
| `/waiter/join` | `WaiterJoin.vue` | `PlainLayout`, **public no-auth** staff-invite onboarding + PWA install |

Kitchen (KDS) and cashier (Z-report + cash drawer) are **owner-app routes** above — there's no separate cashier route. **Capabilities** (`tables`/`dine_in`/`waiter`/`kitchen`/`reservations`) are gated per tenant by `business_type` — see §4.

**POS depth (built):** order lifecycle + coursing/fire/station, seat-split, void/comp, transfer/merge, floor/tables, KDS with all-day counts + 86-board, combos/option-groups/happy-hour, two-level inventory (dish stock + ingredient BOM via `RecipeLine`), cash drawer + Z-report + shift, closed-loop wallet payments. **Reliability gaps** (offline is status-advance-only, `window.print()` only, last-write-wins concurrency, single drawer) are catalogued in `PRODUCT_VISION` Surface 1.

---

## 3. Driver

| Route | Page | Notes |
|---|---|---|
| `/driver` | `DriverPage.vue` | Single page: offers, active job, earnings, cash-out. Under `LandingLayout`; auth handled **in-page**, not by route meta. Ships in the consumer bundle (not yet a dedicated surface — see `PRODUCT_VISION` Surface 3). |

**Driver capabilities (built):** ranked-offer dispatch cascade (`accounts.DeliveryJob`), earnings + cash-out money hygiene (`DriverPayout`, `DriverCashoutRequest`), proof-of-delivery (code + photo + lockout). **The cash-out 6-digit code is a live bearer credential — never log it.**

---

## 4. Platform admin (sales console) — `AdminLayout`, `meta:{requiresAuth, adminOnly}`

| Route | Page |
|---|---|
| `/admin-console` | `AdminConsole.vue` (tenants + CRM **leads**) |
| `/admin-customers`, `/admin-wallets`, `/admin-analytics` | `AdminCustomers` / `AdminWallet` / `AdminPlatformAnalytics` |
| `/admin-drivers`, `/admin-delivery-jobs`, `/admin-delivery-zones` | driver/delivery ops |
| `/admin-rides`, `/admin-flash-sales` | `AdminRides` / `AdminFlashSales` |

**Standalone** (`PlainLayout`): `/signin`, `/forgot-password`, `/reset-password`, `/activate`, `/unauthorized`, `NotFound`.

---

## Backend apps & key models

| App | Schema | Key models |
|---|---|---|
| **`accounts`** | **public/shared** | `Customer` (platform identity + `wallet_balance`, loyalty), `User` (staff/owner/admin roles + `perm_*` flags), `WalletTransaction` (append-only ledger), `WalletChargeRequest`, `TenantFloatTransaction`, `DeliveryJob`, `DriverPayout`, `DriverCashoutRequest`, `DeliveryZone`, `RideRequest` (ride\|package), `CustomerOrderRef` (public mirror of tenant orders), `CustomerTenantFollow`, `CustomerRating`, `CustomerNotification`, `PlatformConfig`, `PlatformFlashSale` |
| **`tenancy`** | **public/shared** | `Tenant` (`plan`, `float_balance`, `lifecycle_status`, grace), `Domain`, `Plan` + `FeatureFlag`, **`Profile`** (1:1 tenant config incl. branding, delivery/commission, marketplace denorm fields, **`business_type` + `capabilities`**) |
| **`menu`** | **per-tenant** | `SuperCategory→Category→Dish`, `OptionGroup`/`DishOption`, `ComboComponent`, `HappyHour`, `Promotion`, `Order`/`OrderItem`/`OrderPayment`, dine-in (`TableSection`, `TableLink`, `Shift`, `DrawerSession`/`DrawerTransaction`, `WaiterCall`), inventory (`Ingredient`/`RecipeLine`), `AnalyticsEvent` |
| **`sales`** | **public/shared** | `Lead` (owner-acquisition + reservation funnel), `Subscription`, `Deal`, `TierUpgradeRequest`, `ProvisioningJob` + `ActivationToken`, `AdminAuditLog` |

> Only `menu` is tenant-scoped (schema-per-tenant). Everything else is public and **must be
> manually scoped by `tenant_id`/ownership** — see `ARCHITECTURE.md` §3.

## Key API endpoint groups

`backend/config/urls.py` (tenant + shared) and `backend/config/shared_api_urls.py` (public-only, spliced into both); every route also mirrored under `/api/v1/…`.

- **Auth/identity:** `/api/login`, `/api/session`, `/api/mfa/*`, `/api/customer/auth/{phone,google,email}`, `/api/customer/session`.
- **Menu/catalog (tenant):** DRF routers `/api/{super-categories,categories,dishes,dish-options,option-groups,tables,happy-hours}`; `/api/owner/menu/*`.
- **Orders (tenant):** `/api/place-order`, `/api/checkout-intent`, `/api/order-status/<n>`; owner `/api/owner/orders/*`; staff/POS `/api/staff/{orders,tables,clock-in,clock-out}`, `/api/owner/{drawer,z-report}`.
- **Wallet (public):** `/api/customer/wallet/*` (`pay-token`, `charge-requests/*`, `transfer`), `/api/customer/topup/{intent,webhook}` (PSP — dormant), `/api/owner/wallet/*`.
- **Driver/delivery (public):** `/api/driver/{register,status,earnings,jobs,cashout}/*`.
- **Rides/courier (public):** `/api/rides/*`, `/api/driver/rides/*`, `/api/track/<token>` (public recipient).
- **Marketplace (public):** `/api/marketplace/`, `/api/marketplace/menu/<slug>`, `/api/marketplace/order/*`.
- **Customer super-app (public):** `/api/customer/{services,active,notifications,orders,businesses,addresses,reservations}`, `/api/referral/<code>`.
- **Admin/sales (public):** `/api/admin/*`, `/api/admin-tenants/*` (lifecycle, live-orders, settings export/import), DRF `/api/leads`, `/api/provision-jobs`.
- **Onboarding/provisioning:** `/api/lead-provision*`, `/api/activate`, `/api/public/plans`.
- **Tenant meta:** `/api/meta/` (`TenantMetaView` — feeds the SPA its capabilities), `/api/profile/`, `/api/translate/`, `/api/uploads/image/`.

## Capability seam (super-app gating) — [ADR-0008](adr/0008-superapp-capability-seam.md)

Two orthogonal gates, **no per-vertical apps**:

1. **Per-tenant capabilities** — `Profile.business_type` (`restaurant`/`cafe`/`bakery`/`grocery`/`retail`/`pharmacy`) derives a `Profile.capabilities` map over `("tables","dine_in","waiter","kitchen","reservations")` (`backend/tenancy/models.py`). Restaurant/café = full; bakery = kitchen-only; grocery/retail/pharmacy = all off. Server helper `backend/tenancy/capabilities.py::tenant_capability_enabled`; exposed to the SPA via `/api/meta/`; the router gates owner routes with `meta.requiresCapability`.
2. **Platform verticals** — taxonomy `backend/accounts/verticals.py` (`food, shops, pharmacy, rides, courier, driver`); enabled by env `DJANGO_VERTICALS_ENABLED` → `settings.VERTICALS_ENABLED`. Vertical is *derived* from `business_type`/ride-kind/driver-flag. The router gates `/ride` and `/send-package` on `meta.vertical`. Frontend mirror: `frontend/src/lib/{verticals.js,services.js}`.
3. **One identity, one global wallet** across all verticals; `WalletTransaction.vertical` / `CustomerOrderRef.vertical` are **reporting tags only** — the balance is never partitioned.

## What's built vs. dormant (read this before assuming a feature is live)

| Capability | State |
|---|---|
| **Payment provider (Stripe/PSP)** | **Dormant behind a flag.** The closed-loop prepaid wallet is the real payment rail. `PSP_TOPUP_ENABLED` defaults **off** (`settings.py`); the top-up intent/webhook views return `{"enabled": false}` when off. Owner-gated to activate (needs a PSP account). |
| **Rides vertical** | **Built but dark-launched.** `rides` is deliberately **excluded** from the default `DJANGO_VERTICALS_ENABLED` (`food,shops,pharmacy,courier,driver`), so `/ride` is gated off and `services.js` marks it `coming_soon`. Full impl exists (`RideRequest`, `ride_views.py`, `sweep_ride_requests`, tests). **Courier (`/send-package`) IS live** by default. |
| **Retail / pharmacy catalog** | **Stubbed on the restaurant model.** Shops/pharmacy ride on `menu.Dish` + a 4-key `attributes` JSON (`sku,barcode,brand,unit`). Business types gate features, but real depth (variants, tax class, dosage, the `Dish→Item` rename) is deferred (RISK **DATA-3**). |
| **Realtime (WebSockets)** | **Optional.** Channels activates only if installed (`HAS_CHANNELS` probe); otherwise the app falls back to polling. WS carries *hints*, clients refetch over HTTP (`ARCHITECTURE.md` §8). |
| **Tenant billing / dunning** | **Modeled, not automated.** `Tenant.lifecycle_status` + grace, `sales.Subscription`/`Deal`/`TierUpgradeRequest` exist and are admin-driven; there is **no automated payment collection** (consistent with the no-PSP posture). |
| **Superseded page** | `OwnerShiftClose.vue` is preserved as a file but its `/owner/shift-close` route **redirects to** `owner-z-report` (the two were merged). Not a live surface. (`OwnerBilling.vue` is **not** orphaned — it's the "billing" tab rendered inside `OwnerProfile.vue`.) |

## Load-bearing config toggles (behavior-changing env vars)

The full env list lives in `backend/.env.example`, `frontend/.env.example`, and
`coolify.env.{staging,production}.sample`. These are the toggles that **change what the app does**
— `backend/config/settings.py` holds the authoritative default:

| Env var | Default | Effect |
|---|---|---|
| `DJANGO_DEBUG` | `False` (settings) | Prod must keep it False — `docker/entrypoint.sh` is fail-closed and refuses to boot with `DEBUG=True`. `.env.example` sets `True` for local dev. |
| `DJANGO_SECRET_KEY` | `change-me` (example) | Prod **requires** a real random value — entrypoint hard-fails without it. |
| `DJANGO_VERTICALS_ENABLED` | `food,shops,pharmacy,courier,driver` | CSV of live platform verticals. **`rides` is deliberately excluded** — add it to re-enable `/ride`. |
| `PSP_TOPUP_ENABLED` | off | Activates the dormant Stripe top-up seam (also needs `PSP_STRIPE_SECRET_KEY` + `PSP_STRIPE_WEBHOOK_SECRET`). |
| `CELERY_BROKER_URL` | unset | **Unset → Celery OFF**: async tasks run inline on a bounded `ThreadPoolExecutor` (queued work lost on restart). Set it (usually = `REDIS_URL`) to turn on the durable queue + Beat. |
| `DJANGO_SESSION_COOKIE_DOMAIN` | `.{TENANT_DOMAIN_SUFFIX}` | The **shared cookie** across all tenant subdomains (super-app SSO) — the reason every public-schema query must scope by `tenant_id` (`ARCHITECTURE.md` §3/§5). |
| `USE_ASGI` | ASGI/uvicorn | `USE_ASGI=0` falls back to gunicorn/WSGI (`ARCHITECTURE.md` §10). |

WebSockets are **not** an env toggle — Channels auto-activates via a `HAS_CHANNELS` import probe; absent, the app falls back to polling.
