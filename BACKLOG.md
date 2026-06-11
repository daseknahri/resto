# Kepoli Backlog — deferred / missing / revisit-later

Working rule: **every batch appends here** — review findings we consciously defer,
audit leftovers, MVP decisions that need revisiting, ideas out of current scope.
Each item: source + why deferred. Reviewed in full during R5 (and periodically after).
Done items get moved to the bottom section with the commit hash, not deleted.

> **v1.0 triage (2026-06-11):** full backlog reviewed before tagging restaurant-v1.0.
> No item below blocks the release — every entry is a conscious deferral with a
> workaround or limited blast radius. The R5 review's 1 critical + 5 majors were
> all FIXED pre-tag (void×cancel refund block, split-bill×void stranding, owner
> cancel atomicity, kitchen voided-items, cash-cancel warning, section bypass).

## Restaurant (current focus — candidates for post-v1.0)
- [ ] **`amount <= 0` guard in payments endpoint when ledger > total** — the R5
      fix flips such orders to PAID at void time, but a direct API path that
      creates the state would still strand; consider a reconcile sweep assertion.
      Source: R5 review follow-on thought.
- [ ] **Receipt shows split payments** — printed receipt should list the OrderPayment
      ledger rows (paid cash 120 / wallet 80). Source: R4 scope cut.
- [ ] **Loyalty not adjusted on item void** — voiding a paid item refunds wallet but
      earned points aren't clawed back per-item. Documented MVP in R2 view docstring.
- [ ] **option_ids silent-drop** — invalid option ids are skipped (item lands at base
      price) in both PlaceOrderView and the R2 append view. Consider strict 400 in both
      at once. Source: R2 review minor.
- [ ] **Per-INTENT idempotency key in waiter settle** — postPayment now sends a key
      per call (protects transport retries; double-taps blocked by UI guards), but a
      user who manually retries after a timeout-that-committed gets a NEW key and can
      record a duplicate equal-amount partial. Per-intent keying (key minted when the
      settle chooser opens) closes it. Source: R4 review major, refined.
- [ ] **Merge the two order.save() calls in StaffOrderPaymentView** when a wallet
      partial also flips PAID (cosmetic in-memory inconsistency inside the atomic
      block). Source: R4 review minor.
- [ ] **Combos / meal deals** (bundle pricing) — audit growth item, not in top-8.
- [ ] **Happy-hour / time-based pricing** — availability_schedule exists per dish;
      price scheduling does not. Audit growth item.
- [ ] **Campaign cap TOCTOU** — two concurrent POSTs can both pass the 2/day count
      check (owner double-click) and land a 3rd campaign. Owner-only, low blast
      radius; fix with a short cache-mutex around count+create. Source: campaigns
      review minor.
- [ ] **Digest mixed-day regression test** — ledger+legacy orders in the same day
      is computed correctly but untested as a combined case. Source: campaigns
      review minor.
- [ ] **Win-back automation** — auto-nudge customers inactive N weeks (the
      automated half of the campaigns feature; manual announcements shipped).
- [ ] **Multi-branch** (one owner, several locations under one account) — large;
      tenants are single-location today.
- [ ] **Auto-print on new order** — needs kiosk browser / local agent / network
      ESC-POS printer. Manual print button shipped long ago.
- [ ] **Course sequencing** (fire starters before mains) — audit service-flow item,
      below top-8 cut.

## Verticals (parked by strategy — doc §4b)
- [ ] **Store pick-flow**: substitutions + out-of-stock at pick time + refund deltas.
      THE grocery feature. Doc §5c deferred list.
- [ ] **Basket-size → vehicle targeting** for big grocery orders. Doc §5c.
- [ ] **Cold-chain / fragile cargo flags** on deliveries/packages. Doc §5c.
- [ ] **Prescription flows** — explicitly OUT of scope (pharmacy = parapharmacie only).
- [ ] **Dish→Item schema rename** — lands last, rehearsed on a schema clone. Doc §3.
- [ ] **Cafe-specific delivery wording** — cafés deliberately read as restaurants in
      deliveryVocab.js; revisit only if cafés need their own voice.

## Rides / courier
- [ ] **Pre-dispatch reminder push** for scheduled trips ("your ride is in 30 min").
- [ ] **Courier fares share ride fares** — MVP decision (ride_views.py docstring);
      split into courier_* PlatformConfig fields when pricing diverges.
- [ ] **ride_per_minute default 0** — enable/tune once live trip data exists.
- [ ] **Car-doc expiry** — licence/insurance have no expiry date / re-verification
      cycle; admin approval is one-shot.
- [ ] **Admin PII-read audit logging** — AdminRideListView returns rider/driver phones
      with no audit log entry (delivery equivalents too). Compliance, review minor.
- [ ] **code_locked_until unindexed** — only matters if a future sweep/admin query
      filters on it. Review minor, explicitly "not a current issue".

## Platform / ops
- [ ] **Notification provider-level retry** — senders record 'failed' but don't raise,
      so Celery retry never triggers. Old Phase-4 follow-up.
- [ ] **Stripe wallet top-up seam** — build when owner has a PSP account (owner said
      not yet). Webhook → credit_wallet with event-id idempotency. Doc Phase 3.
- [ ] **Driver bank-transfer payouts** — needs a PSP. Memory note.
- [ ] **nginx bot-branch syntax** — could not run `nginx -t` locally (no docker);
      verify container start + checklist curls on the NEXT deploy, then tick this.
- [ ] **Local Postgres dev environment** — 25 DB-backed tests error locally (auth
      fail); a docker-compose dev DB would let the full suite run everywhere.
- [ ] **_batch_business_types singleton calls** — 4 single-job endpoints pay one extra
      Profile query each. Review minor, functionally correct.
- [ ] **SEO beyond OG** — sitemap, per-tenant meta description for Google (the OG view
      serves social bots only; googlebot isn't routed to it by design — decide whether
      it should be).

## Done (moved from above)
<!-- - [x] item — commit hash -->
- [x] Payments endpoint request-level idempotency (backend mechanism: client key →
      cache short-circuit + cache.set after commit) — R4 split-bill commit.
- [x] Owner→customers announcements (manual campaigns: opt-out pref, 2/day cap,
      tenant-scoped audience, history) — campaigns commit.
- [x] Digest cash formula for split-bill: ledger-derived wallet/cash with legacy
      fallback — campaigns commit.
