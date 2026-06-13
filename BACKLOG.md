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

> **2026-06-13: the OPS program supersedes ad-hoc backlog pulls.** Next work comes
> from KEPOLI_ARCHITECTURE.md §4d (OPS-1 → OPS-6), evidence base in OPS_AUDIT.md.
> Items below stay as the catch-net; several are absorbed by OPS batches
> (revenue.py materialization → OPS-4; perform_update atomicity → OPS-3).

## Restaurant (current focus — candidates for post-v1.0)
- [ ] **Multi-branch** (one owner, several locations under one account) — large;
      tenants are single-location today.
- [ ] **Auto-print on new order** — needs kiosk browser / local agent / network
      ESC-POS printer. Manual print button shipped long ago.
- [ ] **DishViewSet.perform_update marker clear not atomic** — serializer.save() and the
      stock_auto_zeroed=False clear are two writes outside one atomic block; a checkout
      zeroing the dish in that microsecond window loses its marker. Wrap in atomic.
      Source: sweep-2 review minor.
- [ ] **Clawback test asserts points_earned decrement weakly** — string-contains check on
      update call args instead of asserting points_earned=<exact value>. Tighten.
      Source: sweep-2 review minor.

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

## Scout notes (SaaS-expert audit — every OPS batch appends; triage at ship)
These are an expert-lens scout's findings (not batch reviews). Each maps to a future
OPS batch or a security pass. file:line in the scout output; verify before acting.
- [ ] **Section assignment accepts any user_id (no tenant-membership check)** — PATCH
      /api/owner/sections/<id>/ inserts arbitrary user_ids into SectionServer; a foreign
      id taints _can_access_order routing. Fix = whitelist filter(id__in, tenant_id).
      SECURITY. (menu/views.py ~6444). → OPS-5 / security pass. [scout OPS-1]
- [ ] **CustomerOrderConsumer accepts any order_number (enumeration)** — ws/order/<n>/
      joins the group with no ownership check; exposes live payment_status flips by
      guessing order numbers. Low-sensitivity (status pings) but real. Mitigation:
      require delivery_code / customer-session credential. (realtime/consumers.py:64).
      SECURITY. → OPS-5 / security pass. [scout OPS-1]
- [ ] **Plan limits unenforced on write** — Plan.max_dishes / max_staff_accounts checked
      only by the periodic enforce_subscriptions sweep, not at DishViewSet.create /
      StaffCreateView. A tenant can exceed plan caps until the sweep runs. Monetization
      boundary. (tenancy/models.py:12). → OPS-5 (billing ops). [scout OPS-1]
- [ ] **_can_access_order = 3 serial queries inside select_for_update** — held row lock
      spans the section-resolution queries on every staff mutation; lock-queue at rush.
      Cache section assignment per-request or single combined query. (menu/views.py:3160).
      → OPS-4 (scale). [scout OPS-1]
- [ ] **Section-access logic copy-pasted 3×** — StaffOrderListView inline, _can_access_order,
      waiter_views._section_slugs_for all reimplement (my_slugs, claimed_slugs) differently;
      a future section-semantics change will miss one. Extract one helper. (menu/views.py
      :3160/:3268; waiter_views.py:85). → fold into whichever OPS batch next touches sections.
      [scout OPS-1]
- [ ] **WaiterCall throttle is per-IP** — shared restaurant NAT collapses the 10/min bucket
      across all tables → real customers get 429. Key on (tenant + table_slug) instead.
      (waiter_views.py:45; throttles.py:32). → OPS-3 (throttle scoping). [scout OPS-1]
- [ ] **StaffMessage unbounded + no created_at index** — staff chat grows forever, Meta
      ordering ('-created_at') has no index. Add prune cron + db_index. (menu/models.py:341).
      → OPS-4 (retention). [scout OPS-1]
- [ ] **StaffShiftSummaryView materializes orders in Python for avg prep** — 3 round-trips
      (aggregate, per-row iterate, currency) where ExpressionWrapper+Avg is one query.
      (menu/views.py:3419). → OPS-2 (shift summary is already in scope there). [scout OPS-1]
- [ ] **Order.table_slug vs table_label dual keys** — waiter UI groups by label, routing
      uses slug; renaming a TableLink splits historical orders into two groups. No migration
      on rename, no rename warning. Partially mitigated by OPS-1 table dropdown. (models.py
      :401; WaiterPage.vue:1238). → OPS-6 (onboarding/table mgmt). [scout OPS-1]

## Done (moved from above)
<!-- - [x] item — commit hash -->
- [x] OPS-1 "kitchen never goes dark": StaffBulkReadyView (kitchen-cap gated, atomic
      +select_for_update) + StaffTableListView; useWakeLock (KeepAlive-correct release/
      re-acquire) on kitchen+waiter; reconnect-forever WS with live/polling chip + idle
      state; targeted single-order refresh (full-poll fallback for new orders); 86 board
      in kitchen topbar (refetches every open); bulk mark-ready; table dropdown w/ custom
      escape hatch; manifest landscape (owner+waiter); kitchen KeepAlive w/ onActivated/
      onDeactivated lifecycle (poll+clock+WS+wakelock paused while parked). Review found
      8 majors+3 minors; fix agent died on network → I applied all in code (kitchen-cap
      guard+test, wakelock deactivate-release, disconnect idle+attempts-reset, single
      connect path, clock pause, 86 refetch, modal close, waiter manifest). Scout: 1
      resolved (waiter manifest), 9 → Scout notes above. Backend 3244 green. — ops1 commit.
- [x] Menu-builder save fired 500+ requests (user-reported): saveAndNext re-saved
      EVERY dish (PUT + options GET/sync + groups GET/sync each) on every click.
      Now dirty-tracked via per-dish JSON snapshots taken at load + after save —
      only changed rows persist. — dirty-save commit.
- [x] Course sequencing (dine-in fire control): Category.course 0–4 default →
      OrderItem.course snapshot at all 3 placement paths → Order.fired_course cursor
      (default 1) + POST /api/staff/orders/<id>/fire-course/ (section-gated, monotonic,
      select_for_update); waiter + kitchen fire buttons with HELD·C2 amber chips,
      owner orders consistent display; categoryApi whitelist carried course;
      display+control only (no blocking of void/ready/payment) — courses commit.
- [x] Correctness sweep 2 (8 items): loyalty clawback on item void (proportional from
      stored points_earned — rate-change-proof, composes with cancel via decrement);
      payments outstanding<=0 reconcile guard (200 "reconciled", no phantom row);
      void/cancel restock merged into ONE Q(slug)|Q(pk) select_for_update with combined
      single-increment per dish; DishViewSet.destroy true single-fetch; winback audience
      dedupe batched to one query; winback weeks=0 defensive default; revenue.py
      subquery instead of materialized PKs; Dish.stock_auto_zeroed marker (menu/0053)
      so the 5am cron only re-enables checkout-zeroed dishes (set at all 6 auto-zero
      sites, cleared on restock/owner-write/bulk-reset/cron) — sweep-2 commit.
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
