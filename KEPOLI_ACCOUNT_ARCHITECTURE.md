# Kepoli — Super-App Account Architecture & Roadmap

> **Status:** ✅ IMPLEMENTED (P0–P4 shipped; see `KEPOLI_NEXT.md` C13). Red-teamed against the
> live code before build. Deferred (non-blocking): P3c reservation `Customer` FK; a dedicated
> per-service route split (the order/wallet filters deliver the scoped views without it).
> **Author:** architecture pass, grounded in a read-only map of the live code (2026-06-19).
> **Relationship to other docs:** `KEPOLI_ARCHITECTURE.md` is the tenancy/super-app contract;
> this is the **account/identity/data-scoping** contract under it. `KEPOLI_NEXT.md` is the
> shipping ledger; phases below land as `Cn` rows there.

---

## 1. The requirement

> "The user should have an account **general** and one **for each service**, where it only
> sees the data relative to that service. But some data needs to be **global** — like the
> wallet — and others."

Decoded: **one identity, one wallet, many scoped service contexts.**

- A **general account** = the global identity + the primitives shared by every service
  (wallet, saved addresses, referral, security/notification channel).
- A **per-service account** = a lightweight *profile + scoped view* per vertical. In a service
  surface the user sees **only that service's** activity and preferences.
- **Global data stays global** — above all the **wallet is ONE balance**. Per-service is a
  *view/scoping* layer over shared primitives, **NOT** a separate login or a split wallet.

> **Why one identity, not separate accounts per service:** the wallet, referral graph, and
> `Customer` row (referenced across **136 files / ~1,655 sites**) are keyed to a single identity.
> Splitting identity per service would fragment the wallet (breaking the "wallet must be global"
> requirement), duplicate verification, and force a 136-file rewrite. This is the model every mature
> super-app uses (Grab, Gojek, WeChat): **one account, global wallet, per-service scoped surfaces.**

---

## 2. The three-layer model

| Layer | What it is | Examples | Storage |
|---|---|---|---|
| **L1 — Global account** | One identity + primitives shared by every service | identity (phone/email/google), **wallet balance + ledger**, saved addresses, referral, push channel, security/account settings | `Customer` row + existing public-schema models (**unchanged**) |
| **L2 — Service profile** | A thin `(customer, vertical)` record: per-service prefs + state | per-service notification toggles, default address for *this* service | **NEW** `CustomerServiceProfile` table (additive) |
| **L3 — Service activity** | Existing activity **tagged with `vertical`** so each surface shows only its own | food/shop orders, rides, courier jobs; wallet transactions (for per-service *spend* views — still one balance) | **ADD `vertical`** to `CustomerOrderRef` + `WalletTransaction` (nullable, backfilled) |

**The wallet is L1 and stays L1.** The `vertical` tag on `WalletTransaction` (L3) is **reporting
metadata only** — it never partitions the balance. `wallet_balance` stays one field;
`credit_wallet`/`debit_wallet` atomicity, locking, and idempotency are untouched.

---

## 3. Canonical vertical taxonomy (reconciled with live code)

Today the vertical set lives in three disconnected places: `VERTICALS_ENABLED`
(`config/settings.py:792`, default `food,shops,pharmacy,courier,driver`), the `SERVICES`
registry (`services.js`), and `business_type` on `tenancy.Profile`. The roadmap introduces ONE
canonical map, mirrored backend + frontend, **matching the tokens already live** (so it does not
break the env var or the registry — `pharmacy` stays its own token, NOT folded into `shops`).

| `vertical` | Consumer meaning | Derived from |
|---|---|---|
| `food` | Restaurants & cafés | tenant `business_type` ∈ {restaurant, cafe} |
| `shops` | Grocery, bakery, retail | `business_type` ∈ {grocery, retail, bakery} |
| `pharmacy` | Parapharmacie | `business_type` = pharmacy |
| `rides` | Passenger ride-hailing | `RideRequest.kind = RIDE` (gated `coming_soon` today) |
| `courier` | Send-a-package | `RideRequest.kind = PACKAGE` |
| `driver` | The earn side (deliver/drive) | `Customer.is_driver` — same identity, "work" context |

Money-movement rows with **no consumer vertical** (`TOPUP`, `TRANSFER_IN/OUT`, `ADJUSTMENT`,
`BONUS`) are tagged `null` and treated as **global** in spend views — this is expected, not a gap.

**Deliverable:** `backend/accounts/verticals.py` (the canonical `business_type → vertical` map +
`order/ride → vertical` helpers + the enabled set) and a `frontend/src/lib/verticals.js` mirror.
`services.js` and `VERTICALS_ENABLED` consume this instead of each redefining the set. The map must
agree with the marketplace lens (`?type=food|shop`) and `deliveryVocab.js`/`useVocabulary.js`.

---

## 4. Backend data-model changes (all additive / non-breaking)

### 4.1 Tag activity with `vertical`
- **`CustomerOrderRef`** (public cross-tenant order index) → add `vertical CharField(16, db_index, blank)`.
  **It is written in exactly ONE place** — the `post_save` signal on `menu.Order` in
  `menu/signals.py` (~L25–70), which already swallows errors best-effort. So tagging is a **one-line
  change to that signal's `defaults` dict** (derive `vertical` from the tenant's `business_type`),
  **not** three order-path edits. The `backfill_order_index`-style command sets it for existing rows.
- **`WalletTransaction`** → add `vertical CharField(16, db_index, null)`. **This is the real work of
  P1:** `credit_wallet`/`debit_wallet` (`accounts/wallet_service.py`) take **no `vertical` param today**,
  so the column must be threaded through ~15–20 call sites across `menu/views.py`, `accounts/views.py`,
  `accounts/ride_service.py`, `accounts/driver_service.py`, and management commands — otherwise every
  new row writes `null` and the migration achieves nothing. Vertical sources per type:
  - food/shop/pharmacy `PAYMENT`/`REFUND` → from the order's `business_type` (or its `tenant_id` → Profile).
  - driver `EARNING` → from **`DeliveryJob.business_type`** (already denormalized on the job, no
    cross-schema lookup) or `RideRequest.kind` for ride/courier; tag `driver`.
  - `CASHOUT` → `driver`. `TOPUP`/`TRANSFER_*`/`ADJUSTMENT`/`BONUS` → `null` (global).
  - **Balance math, locking, and idempotency keys are unchanged.** Idempotent retries replay the
    existing row as-is (they do **not** rewrite `vertical`).
  - Backfill is best-effort: rows with `tenant_id` map cleanly; the rest stay `null` (acceptable).

### 4.2 Per-service profile — **explicit columns only**
**NEW `CustomerServiceProfile`** — `unique_together (customer FK, vertical)`, lazily created, all
nullable/defaulted: `notify_updates` (bool, default True), `notify_promotions` (bool, default True),
`default_address` (FK `SavedAddress`, null). **No open-ended `prefs` JSON, no `onboarded_at` /
`last_active_at`** — first/last-activity is derived from indexed `CustomerOrderRef` queries (single
source of truth), not a second write path.
- **Reconcile with the existing `CustomerTenantOptOut`** (`accounts/models.py:1162`, per-(customer,tenant)
  promo opt-out already consulted in `accounts/push.py`): precedence is **suppress-if-either** — a promo
  is sent only if the per-tenant opt-out is absent **and** the vertical's `notify_promotions` is True.
  `push.py` must consult both; `CustomerServiceProfile.notify_*` is the vertical-wide default, the
  per-tenant opt-out is the per-restaurant override.
- Legacy flat `Customer.notify_*` booleans remain the **global default** when no service profile exists.
- **Erasure:** `erase_customer` must scrub `CustomerServiceProfile` rows and `CustomerOrderRef.vertical`.

### 4.3 Wire `enabled_verticals` (no new food/shop gating)
`getServices(enabledVerticals)` already exists in `services.js` but is **unused** — wire it into the
hub + router so a disabled vertical is hidden/gated in the UI, and keep the existing `_vertical_gate`
on rides/courier. **Do NOT add a gate to food/shops** — those are always-on revenue surfaces; an
always-open gate is pure ceremony (cut).

### 4.4 Reservations linkage — **new bookings only**
Add an optional `Customer` FK to `sales.Lead`, set **at booking time when a customer session exists**.
**Do not** backfill existing reservations from phone/email — that match is many-to-one and ambiguous.
`CustomerReservationsView` keeps its phone/email match as the fallback.

---

## 5. Session / identity model

- **Keep ONE customer session** (`request.session["customer_id"]`) and the cross-persona fixation
  guard (`_staff_session_conflict` + `cycle_key()`). **No new login surfaces.**
- Add a client-side **service context** ("which service am I in", from the route) used to scope reads
  and pick the L2 profile. It is **not** an auth boundary.
- `GET /api/customer/session/` grows a `services` block: per-vertical summary (enabled?, last-activity,
  count — all computed from indexed `CustomerOrderRef`/`RideRequest` queries) so hub + account render
  per-service state in one round-trip.
- Driver stays the same identity with `is_driver`; the driver "context" is just another surface.

---

## 6. Frontend model

- **Service-context layer** in `useCustomerStore`: expose `enabledVerticals` (wire the already-fetched
  `platform.enabled_verticals`), an `activeService` from the route, and per-service summaries.
- **Account split into L1 + L2:**
  - **Global** (`/account`): wallet (one balance) + **per-service spend breakdown**, identity/profile,
    saved addresses, referral, security, data export/erasure.
  - **Per-service**: each service gets a scoped "home/activity" — its own order/trip history (via the new
    `?vertical=` filter), its own preferences (L2), its own default address.
- **Order history** gains a Food / Shops / Pharmacy / Rides / Courier filter (today it's one flat list).
- **Wallet** keeps the single balance hero and **adds** a "spent on food / shops / rides …" breakdown
  from `WalletTransaction.vertical` (null rows = "other/global").
- **Router** gates service routes on `enabledVerticals` (today `/ride` loads even if rides are disabled).
- **SuperAppHub** becomes per-service-aware (last-used, badges) instead of a static launcher.

---

## 7. Non-breaking migration strategy & money guardrails

1. **Wallet is one global balance — non-negotiable.** `vertical` is reporting metadata; no per-vertical
   balances; no change to balance math, locking, or idempotency keys (which stay schema-namespaced).
2. **Additive only.** Every new column nullable/defaulted; every new model a new table. `Customer` gains
   **no required columns** — protecting the 136-file blast radius.
3. **Backfill, then read — with deploy choreography.** Order: (1) migrate nullable columns; (2) deploy
   write-tagging (signal + wallet call sites); (3) run backfill (a **long cross-schema scan** — it reads
   each tenant's `Profile.business_type`); (4) only then ship `?vertical=` read filters. The order-ref
   signal swallows errors by design, so during a rolling deploy some rows write `null` — acceptable
   because "all" (unfiltered) stays the default until step 4.
4. **Legacy fallbacks preserved.** Flat `notify_*` remain the global default; "all orders / all
   transactions" keep working with `?vertical=` optional.
5. **One identity, one session** — the cross-persona security fix is preserved; no new auth surface.
6. **Per-tenant identity sacred** and **no `Dish→Item` rename** — unchanged from `KEPOLI_ARCHITECTURE.md`.

---

## 8. Phased roadmap

Each phase is independently shippable, gated by backend pytest + the four frontend gates
(`verify:i18n / lint / build / test`). Money-touching change is isolated to P1 and strictly additive.

| Phase | Scope | Risk | Breaking? |
|---|---|---|---|
| **P0 — Taxonomy & seam** | `verticals.py` + `verticals.js` single source; `services.js` & `VERTICALS_ENABLED` consume it; wire the unused `getServices(enabled)` into hub/router. No data change, no new food/shop gate. | Low | No |
| **P1 — Tag the data** | `vertical` on `CustomerOrderRef` (one-line in the `menu/signals.py` signal) + `WalletTransaction` (thread a `vertical` param through ~15–20 wallet call sites; driver earnings from `DeliveryJob.business_type`/`ride.kind`); backfill commands. Reads unchanged. | **Med (money-adjacent; many call sites)** | No |
| **P2 — Service profiles** | `CustomerServiceProfile` (explicit cols); lazy create; per-service notification prefs reconciled with `CustomerTenantOptOut` (suppress-if-either); session `services` block; erasure scrub. | Low | No |
| **P3 — Scoped reads & API** | `?vertical=` on orders + wallet transactions; per-service summaries; reservation `Customer` FK on new bookings. | Low | No |
| **P4 — Frontend service contexts** | Service-context store; account split into global L1 + per-service L2; scoped order history + wallet spend breakdown; router vertical-gating; hub personalization. | Med (UX surface) | No |

**P0–P4 deliver the request end to end.** (KYC state machine and driver-profile extraction are
**explicitly cut** from this roadmap — see §10 — to keep it focused on account scoping.)

---

## 9. Open decisions for the owner

1. **Per-service account UX shape** — (a) dedicated per-service dashboards (`/food`, `/rides`, … each a
   "home", plus a global `/account` for wallet/identity), or (b) one `/account` with service tabs/filters.
   *Recommendation: (a)* — best matches "an account for each service", with the global account as the L1 hub.
2. **Per-service notification preferences** now (P2) vs. global only? *Recommendation: yes, now* — cheap, high value, and we already have `CustomerTenantOptOut` to reconcile with.
3. **Per-service loyalty** — `Customer.loyalty_points` is a **single global pool today, yet points are
   earned per-tenant** (each restaurant runs its own program). That is already inconsistent with "each
   service sees only its own data". *Recommendation: defer*, but flag it — a service context that shows a
   loyalty balance will show the global pool until this is redesigned.
4. **Verticals in scope** — confirm consumer verticals = food, shops, pharmacy, rides, courier, driver;
   rides stays `coming_soon`/gated until licensed supply exists. *Recommendation: confirm.*

---

## 10. Explicitly OUT of scope / deferred

- **Splitting the wallet** into per-vertical balances (violates the global-wallet requirement).
- **Separate logins/identities** per service (fragments wallet + identity; 136-file rewrite).
- **Global KYC state machine** (`CustomerVerification`) — a real idea, but it's a driver-onboarding +
  high-value-wallet redesign that's wired through admin/dispatch; **filed separately**, not in this roadmap.
- **Driver-profile extraction** (moving `Customer.driver_*` into a `DriverProfile`) — cosmetic, large blast
  radius; **cut** (leave driver fields on `Customer`).
- **Tagging `menu.Order` (tenant schema) with `vertical`** — consumer history is served from
  `CustomerOrderRef` (public), so it's not needed now; per-tenant *admin* vertical analytics would need it
  later. Noted, deferred.
- **Anonymous/guest order history** — orders placed with no `customer_id` aren't in `CustomerOrderRef`
  (the signal skips them), so they won't appear in per-service history. Known limitation, unchanged.
- **`Dish→Item` rename** and **per-tenant branding** — unchanged from `KEPOLI_ARCHITECTURE.md`.
- Any change to wallet balance math, idempotency, or locking.
