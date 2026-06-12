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
- [ ] **Loyalty not adjusted on item void** — voiding a paid item refunds wallet but
      earned points aren't clawed back per-item. Documented MVP in R2 view docstring.
- [ ] **Multi-branch** (one owner, several locations under one account) — large;
      tenants are single-location today.
- [ ] **Auto-print on new order** — needs kiosk browser / local agent / network
      ESC-POS printer. Manual print button shipped long ago.
- [ ] **Course sequencing** (fire starters before mains) — audit service-flow item,
      below top-8 cut.

- [ ] **Void/cancel restock lock merge** — StaffVoidOrderItemView + _restock_cancelled_order
      each issue two sequential select_for_update queries (combo dish by slug, components
      by pk) inside one atomic block; placement/append use a single merged query. Merge
      into one Q(slug__in)|Q(pk__in) lock to be fully deadlock-safe. Low practical risk
      (components can't be combos; void slug set is size 1). Source: combos review minor.
- [ ] **DishViewSet.destroy double-fetch on ProtectedError path** — get_object() called
      again in the except block; could use exc.protected_objects instead. Cosmetic.
      Source: combos review minor.
- [ ] **Winback audience dedupe batching** — _build_audience checks _already_nudged
      per-customer (one EXISTS query each) until 50 eligible are found; a tenant with
      thousands of recently-nudged lapsed customers pays that scan hourly at local 11:00.
      Batch into one customer_id__in query (needs the 6 tests patching _already_nudged
      reworked). Source: my post-review read of the winback batch.
- [ ] **winback_inactive_weeks=0 silently coerces to 4** — `or 4` fallback swallows an
      explicit 0 written via admin/raw DB (serializer rejects it). Cosmetic-defensive.
      Source: winback review minor.
- [ ] **revenue.py order_ids materialization** — split helper pulls all period order
      PKs into Python; switch to a subquery join for 90-day windows on busy tenants.
      Source: rev/stock review minor.
- [ ] **Auto-reset clears deliberate zeros** — the 5am reset re-enables ALL stock_qty=0
      dishes, including manually-zeroed ones (same semantics as the manual button, and
      the cron is opt-in — acceptable; a stock_auto_zeroed marker would distinguish).
      Source: rev/stock review minor.

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
- [x] Win-back automation: Profile.winback_* (tenancy/0038) + accounts.WinbackNudge
      durable 90-day dedupe (accounts/0042) + send_winback_nudges hourly cron
      (tenant-local 11:00, mark-BEFORE-send ordering, suppressed-send slot reclaim,
      50/run cap, campaigns-format /order/<slug> deep link) + owner card on
      Promotions + EN/FR/AR — winback commit.
- [x] Happy-hour / time-based pricing: menu.HappyHour rules (menu/0052; days/window/
      percent 1–90/category scope/max 8, overnight wrap), menu/pricing.py effective-price
      helper used by EVERY price surface — Dish serialization (context-injected, no N+1),
      marketplace menu, and all 3 placement paths (customer/marketplace/staff append,
      tenant-local time, price locked at placement for scheduled orders) — owner manager
      on Promotions page, customer strikethrough + "−N% until HH:MM" chip, cart
      stale-price guard (overnight-aware via starts_at), EN/FR/AR — happy-hour commit.
- [x] Combos / meal deals: ComboComponent (CASCADE/PROTECT, max 8, no nesting either
      direction), OrderItem.combo_components placement snapshot, all-or-nothing component
      stock decrement in tenant + marketplace checkout + staff append (single merged lock),
      snapshot-based restock on void + cancel, combo_unavailable + delete→409, builder in
      StepDishes, customer badge/Includes/savings chip, kitchen/waiter/receipt sub-lines,
      EN/FR/AR — combos commit.
- [x] Receipt shows split payments (ledger lines + paid/remaining on thermal) — sweep-1.
- [x] Strict stale_options 400 in checkout + append (incl. cross-dish ids; cart toast) — sweep-1.
- [x] Per-intent settle idempotency key (minted at chooser open, cleared on success incl. charge-sheet path) — sweep-1.
- [x] Merged order.save in StaffOrderPaymentView — sweep-1.
- [x] Campaign cap mutex (cache.add lock; transient case now campaign_locked) — sweep-1.
- [x] Digest mixed-day (ledger+legacy) regression test — sweep-1.
- [x] Payments endpoint request-level idempotency (backend mechanism: client key →
      cache short-circuit + cache.set after commit) — R4 split-bill commit.
- [x] Owner→customers announcements (manual campaigns: opt-out pref, 2/day cap,
      tenant-scoped audience, history) — campaigns commit.
- [x] Digest cash formula for split-bill: ledger-derived wallet/cash with legacy
      fallback — campaigns commit.
