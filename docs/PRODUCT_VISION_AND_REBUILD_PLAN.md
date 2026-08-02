# Kepoli — Product Vision & Rebuild Plan

> Draft v1 · 2026-08-02 · synthesized from a 4-lens read of the live codebase (Business/POS,
> Consumer, Driver, Platform/flywheel). **This is a plan for review — several load-bearing choices are
> the owner's to make (see "Decisions to force").** It is deliberately blunt.

## The one-paragraph verdict

The hard, un-fakeable foundations are **done well**: a **platform-level customer identity + one global
wallet** (`accounts.Customer` in the public schema), a disciplined **money ledger**, a real
**capability/vertical seam**, an unusually **deep restaurant POS** feature set, and a **solid dispatch
backend**. The gap to the vision is **not code quality** — it's that the **flywheel's connective tissue
was never built** and the **product surfaces don't leverage the strong backbone**. This is **not a
rebuild**; it's a *connect + expose + harden* program. The single highest-leverage fix is that **the QR
acquisition flywheel is broken at the source** — and it needs no payment provider to fix.

---

## The vision (as understood)

Kepoli's moat vs. pure marketplaces is that it ships a **real POS businesses use daily**. The flywheel:

```
Partner runs the POS daily  →  customer scans a QR at the business  →  becomes a PLATFORM customer
      →  reorders through the marketplace  →  platform captures the transaction (velocity of money)
```

Three surfaces, one platform "in the middle": **Business (POS)**, **Consumer**, **Driver**. Build
restaurant first (hardest, subsumes most business needs), then generalize.

---

## Core finding: strong foundation vs. missing connective tissue

| ✅ Already built well (keep, build ON) | ❌ Missing / broken (the actual work) |
|---|---|
| Platform-level `Customer` identity + one global wallet (cross-tenant) | The **QR → platform-customer** conversion (scans stay anonymous) |
| Excellent append-only wallet **ledger** (locks, idempotency, reconcile) | A **live money rail** — commission is recorded, never captured; no payout/off-ramp |
| Deep restaurant **POS** (coursing, seat-split, comps, drawer, Z-report, KDS, BOM) | POS **reliability** as a terminal (offline order/payment, printing, concurrency, multi-drawer) |
| Strong **dispatch** backend (ranked-offer cascade, money invariants) | A **dedicated driver surface** + real-time (WS, native push, offline queue) |
| Capability/vertical **seam** + cross-tenant order index (`CustomerOrderRef`) | A **"my businesses / follow"** relationship model (doesn't exist) |
| One host-dispatched SPA; auth/identity unification (AUTHZ-1/IDENTITY-1) done | **One coherent consumer app** (today it's two front-ends sharing a login) |

**All four lenses independently reached the same conclusion:** the substrate is flywheel-ready; the
three moments that make it spin — *capture the customer, make the business discoverable, capture the
transaction* — are each opt-in, generic, or offline.

---

## The flywheel: three broken legs (the heart of the plan)

### Leg 1 — QR → acquisition · **BROKEN BY DEFAULT** (the #1 lever)
A table QR encodes a bare tenant-subdomain URL (`<tenant>/t/<table>`) → lands in the **anonymous
per-tenant storefront**. Dine-in orders bypass the sign-in wall (`Cart.vue`) and place with
`Order.customer = None`; the mirror signal early-returns on null customer (`menu/signals.py`), so the
visit **never enters `CustomerOrderRef`**, is **not reorderable**, and captures only an *optional name —
no phone*. **The anonymous majority of QR diners never become platform customers.** This is the single
biggest leak and the cheapest to fix (no PSP needed).

### Leg 2 — discovery · **opt-in and cold**
The marketplace lists only tenants with `directory_opt_in=True` (**default off**) — a business can run
the POS forever and never appear. Search is shallow `icontains`; the marketplace **never reads a
customer's actual order relationships** ("businesses you've visited / near you" doesn't exist). A second,
**orphaned** discovery surface (`Directory.vue`) duplicates it and bounces users out to bare subdomains.

### Leg 3 — transaction capture · **recorded, not captured**
Commission is a **reporting snapshot** on the order (`commission_amount`) that is **never debited** — a
receivable invoiced offline. There is **no live money rail**: the Stripe top-up on-ramp is coded but
dormant, there is **no off-ramp/payout at all**, and **no card path on orders**. "Velocity of money" is
aspirational until a PSP is live and commission settles from a platform-held balance.

---

## Surface 1 — Business / POS (the differentiator; restaurant-first)

- **Have:** genuinely deep restaurant POS — order lifecycle, coursing/fire/station, seat-split,
  void/comp, transfer/merge, table/floor, KDS with all-day counts + 86-board, menu/combos/option
  groups/happy-hour, two-level inventory (dish stock + ingredient BOM), cash drawer + Z-report + shift,
  closed-loop wallet payments, WS-as-invalidation + polling. Money integrity is careful.
- **Want:** a POS a busy venue **trusts all day** and that **converts the guest**.
- **Gaps:** offline covers only status-advance — **new orders & payments are online-only**; **browser
  `window.print()`, no ESC/POS / kitchen printer / drawer-kick / per-station routing**; last-write-wins
  concurrency (terminals stomp each other); **single, owner-only drawer**, no PIN/fast-switch, no
  multi-register/**multi-location**; **no card/PSP**; and the flywheel leak — **staff order entry
  captures only a name, not a customer identity** (the highest-trust, in-venue moment doesn't convert).
  Generalization to non-food is **cosmetic** (hide features + rename nouns) → shops get a "catalog shop,"
  not real retail (no SKU/barcode-scan/variants/weight-pricing/returns/PO); pharmacy needs its own build.
- **Build right (phased):** (1) offline-first order entry + payment (reuse the proven status-advance
  queue) + unconditional service-worker + ticket concurrency + cashier-usable/multi-drawer + PIN;
  (2) hardware: ESC/POS print bridge + card terminal/PSP; (3) **in-venue customer capture** (phone/QR
  lookup + one-tap link on the staff path — closes the flywheel); (4) **SKU-first catalog** abstraction
  over `Dish` + retail checkout mode, then per-vertical inventory, then pharmacy as its own capability.

## Surface 2 — Consumer (the part that feels unplanned)

- **Have:** a real cross-tenant identity + global wallet/loyalty/referrals; a personalized hub
  (`SuperAppHub` — continue/order-again/usage-sorted grid); cross-restaurant reorder via
  `CustomerOrderRef`; marketplace with filters; account with unified history.
- **Want:** **one** consumer app to discover/search businesses, order, and stay connected to daily-used
  places — built on the identity that already exists.
- **Gaps:** it's **two front-ends sharing a login** — a per-tenant storefront (where QR scanners land)
  and a platform super-app — with **fragmented state** (two carts, per-host recent-orders,
  **localStorage-only favorites**, two checkout flows, two order-status pages). **No server-side
  "follow / my businesses" model at all.** Search is substring-only, no cross-business dish search, no
  "for you / near you, open now" feed off the existing indexes. **Loyalty is incoherent** (global balance,
  per-tenant rules) and likely has an **auth defect** in redeem/history (verify: `menu/views.py`
  loyalty views read `request.user.customer_id` with no customer auth wired). The tenant storefront shows
  a *different, localStorage-first* history than the hub. Communication with businesses is one-way only.
- **Build right (phased):** (0) fix loyalty auth + delete the orphaned Directory; (1) **QR soft-identity
  capture** + a server **`CustomerBusiness` (follow/favorite)** written by the order signal — the missing
  keystone; (2) promote the hub to the true home with **"My businesses"** at the center; (3) **unify the
  two front-ends + one cart**; (4) real relevance search + cross-business dish search + a personalized
  feed; (5) two-way "from businesses you follow" updates + coherent "your Kepoli points."

## Surface 3 — Driver (own, optimized)

- **Have:** strong ranked-offer **dispatch cascade**, solid earnings/cash-out money hygiene,
  proof-of-delivery (code + photo + lockout), a mobile-hardened active-job hero.
- **Want:** a lean app a driver trusts all day on mobile data.
- **Gaps:** it's **one 2,200-line page inside the consumer bundle** (not a dedicated surface);
  **polling-only (no WebSocket)**; offers rely on **fragile web-push** (backgrounded/iOS-limited);
  **no offline queue** for status taps; **no batching/multi-drop, no in-app navigation**; **raw customer
  phone exposure** (no masked calling); force-goes-**offline after every delivery**; continuous
  high-accuracy GPS + 3-endpoint polling drains battery.
- **Build right (phased):** (1) reliability — **WebSocket** offers/status + **native push** + **offline
  action queue** + stop forced-offline + adaptive GPS; (2) carve out a **dedicated `/driver` surface**
  (own layout + code-split bundle) + masked calling + nav polish; (3) professional dispatch — road/ETA +
  acceptance-weighted ranking + **batching/multi-drop** + driver-growth surface.

---

## Cross-cutting architecture

- **Two planes in tension.** Only `menu` is tenant-scoped (schema-per-tenant); identity/wallet/drivers/
  marketplace live in `public`, joined to tenant orders by a **FK-less `(tenant_id, order_number)`** pair.
  Schema-per-tenant makes the **POS plane** clean but **fights** every cross-tenant super-app query — so
  the architecture quietly **optimizes the POS (called secondary) over the marketplace (called primary)**.
- **Surfaces aren't structurally separated** — one host-dispatched SPA; the driver app ships in the
  consumer bundle. Fine early; a scaling/clarity cost later.
- **Catalog is food-shaped** (`Dish` + a 4-key JSON blob = "a restaurant model in a shop costume",
  DATA-3). Breadth (rides ≈ 1.7k LOC, retail/pharmacy shells) was built before depth, earning no revenue.

---

## Phased roadmap (cross-surface, sequenced by leverage)

- **Phase 0 — Quick wins / correctness (days):** ✅ loyalty redeem/history auth defect fixed + real
  tests (PR #99); delete/redirect the orphaned Directory; stop the driver's force-offline-after-delivery.
- **Phase 1 — Close the flywheel (the strategic unlock):** QR **soft-identity capture** + backfill-link
  the just-placed order; server **`CustomerBusiness`** follow model written by the order signal;
  **auto-list a tenant in the marketplace on menu-publish**; bridge `CustomerOrderRef` → discovery
  ("businesses you've visited / near you"); **in-venue customer capture on the staff POS path**.
- **Phase 2 — POS terminal-grade reliability:** offline-first order entry + payment; unconditional SW +
  runtime cache + background sync; ticket concurrency; cashier/multi-drawer + PIN.
- **Phase 3 — Consumer coherence:** promote the hub to the true home with "My businesses"; unify the two
  front-ends + one cart; present the same unified history on the tenant storefront.
- **Phase 4 — The money rail:** activate the PSP on-ramp; build settlement/payout (Stripe Connect or
  local acquirer); **settle commission from a platform-held balance** (makes "velocity of money" real);
  card-on-order + pay-at-table.
- **Phase 5 — Driver surface:** WS + native push + offline queue; carve out the dedicated `/driver`
  bundle; masked calling; then batching + smarter dispatch.
- **Phase 6 — Vertical generalization:** SKU-first catalog + retail checkout + per-SKU inventory
  (cafe/bakery already reachable → grocery/retail → pharmacy last, as its own capability).
- **Cross-cutting:** hardware print bridge (with Phase 2); continue `OrderService` extraction (STRUCT-1)
  before building on `PlaceOrderView`; decide the tenant-ceiling → schema model early (it governs the substrate).

---

## Decisions to force (owner-only — settle these before deep building)

1. **POS vs. marketplace primacy.** The architecture currently bets on the POS; the vision calls the
   marketplace the main product. Which is it? (Governs the schema/isolation decision below.)
2. **Tenant ceiling → schema model (MULTITENANCY-1).** Low-hundreds of premium POS tenants → keep
   schema-per-tenant. Thousands, marketplace-first → plan a migration to shared-schema + Postgres RLS.
3. **QR / dine-in identity policy.** Enforce sign-in (convert everyone) vs. keep frictionless anonymous
   dine-in (the current deliberate choice — and the flywheel's biggest leak). Recommended middle path:
   frictionless order **+ one-tap soft capture that backfill-links** the order.
4. **Money custody.** Does the platform take custody of funds (PSP + payouts, commission settled
   in-flow) or stay a closed-loop/offline bookkeeper? Determines whether "velocity of money" is real.
5. **Marketplace default:** opt-in (today) vs. **auto-list on publish** (recommended — the flywheel needs it).
6. **Commission basis:** pre- vs. post-discount (a live mismatch exists between the applied basis and the
   payout statement).

---

## Decisions (locked 2026-08-02)

- **Scale: thousands, marketplace-first.** Eventual target = shared-schema + Postgres RLS
  (MULTITENANCY-1) — an owner-gated XL migration, NOT done now. Meanwhile: prioritize the
  marketplace/consumer/flywheel plane (already in the public schema → migration-neutral) and avoid
  choices that worsen a future migration. Do not do the schema migration autonomously.
- **Money: stay closed-loop / offline bookkeeper for now.** Phase 4 (PSP on-ramp + payout/settlement
  rail) is **deferred**. Keep commission as a recorded receivable.
- **QR identity: frictionless + one-tap soft-capture** (order without a wall, then one-tap phone-OTP
  that backfill-links the just-placed order). Chosen as the build default.
- **Execution: continuous autonomous build**, owner delegated ("do all of them, make the right
  decisions, work with agents, until the project stands on its feet"). Sequence:
  **Phase 0 → Phase 1 (flywheel) → Phase 3 (consumer coherence, bumped up for marketplace-first) →
  Phase 2 (POS reliability) → Phase 5 (driver) → Phase 6 (verticals).** Phase 4 deferred. Each item
  gate-verified + PR'd; big/risky/owner-gated items (schema migration, PSP, hardware) surfaced, not done blind.

## Immediate quick wins surfaced during the assessment
- ✅ **DONE (PR #99) — Loyalty redeem/history was non-functional for real customers** — auth wiring
  defect in `menu/views.py` loyalty views (ran `IsAuthenticated` with no customer auth class and read
  `request.user.customer_id`, but the Customer principal's PK is `.id`) → every signed-in customer
  404'd. Fixed to `CustomerSessionAuthentication` + `IsCustomer` + `customer_or_none`; the four masking
  test files now force-authenticate a real Customer principal, plus a class-level auth-contract guard.
- **Orphaned `Directory.vue` / `/api/directory/`** — a duplicate discovery surface linked from nowhere
  that bounces users out of the app. Delete or redirect into the marketplace.
- **Driver force-offline after every delivery** — a per-drop re-tap; make continuous availability the default.
