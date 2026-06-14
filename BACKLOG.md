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

### OPS-5b — ADMIN SECURITY HARDENING (next batch; scout OPS-5 cluster)
- [ ] **IsPlatformAdmin admits any Django is_staff user → money endpoints (PRIV-ESC, HIGH)**
      — sales/permissions.py:11 returns True for is_staff, so any /admin/-capable Django
      user can POST wallet bonus / fund-tenant / vouchers / ride-fare settings. Intended
      gate is is_platform_admin (role PLATFORM_SUPERADMIN). Fix: drop is_staff from
      IsPlatformAdmin (keep is_platform_admin + is_superuser). One line, but audit every
      admin view that relied on it. [scout OPS-5]
- [ ] **Admin auth pattern triplication** — 15+ admin views use 3 inconsistent gates
      (IsPlatformAdmin class / inline is_platform_admin / inline that also admits is_staff).
      Consolidate on IsPlatformAdmin (after the fix above) + add a test that every
      /api/admin/ URL rejects a TENANT_OWNER. [scout OPS-5]
- [ ] **AdminCustomerList/Detail: full PII directory, no throttle, no read-audit, is_staff
      gate** — accounts/views.py:1687/1744. Add per-admin throttle + log_admin_action on
      GET + IsPlatformAdmin. SECURITY/compliance. [scout OPS-5]
- [ ] **Missing audit on admin writes** — is_driver toggle (accounts/views.py:1813), manual
      delivery-job create (5858/5909) have no log_admin_action; tenant deletion request
      (tenancy/api.py:437, GDPR) has no audit + no TENANT_DELETION_REQUESTED action. Add
      actions + log calls. [scout OPS-5]
- [ ] **plan_feature_flags_updated logged as raw string not in Actions enum** — invisible to
      audit queries filtering Actions.choices. Add the enum member. (sales/views.py:1435).
      [scout OPS-5]
- [ ] **Audit-log IP spoofable** — get_request_ip takes XFF[0] (client-controlled), no
      trusted-proxy config. Use rightmost-trusted / django-ipware. (sales/audit.py:10;
      middleware.py:128). [scout OPS-5]
- [ ] **AdminWalletBonus bulk-credit leaves balance_after=NULL** — breaks ledger
      reconstruction; per-customer credit_wallet or a returning-UPDATE. (accounts/views.py
      :1512). [scout OPS-5]
- [ ] **Dish/staff plan-limit is a read-then-create RACE** — concurrent creates overshoot
      the cap (no lock). select_for_update sentinel or DB constraint. (menu/views.py:587;
      accounts/views.py:1014). [scout OPS-5]
- [ ] **ensure_platform_admin password as CLI arg** — visible in /proc + shell history +
      deploy logs. Read from env/stdin. (commands/ensure_platform_admin.py:9). [scout OPS-5]
- [ ] **Health endpoint leaks MEDIA_ROOT absolute path** to unauthenticated callers — return
      'ok' not str(path). (config/api.py:171). [review OPS-5 minor]
- [ ] **Plan-limit returns HTTP 400 not 402** — contract said 402/403 for entitlement
      boundary; clients may mis-classify. (menu/views.py:602; accounts/views.py:1019).
      [review OPS-5 minor]

### Earlier scout notes
- [ ] **Section assignment accepts any user_id (no tenant-membership check)** — RESOLVED in
      OPS-5 (menu/views.py:7432 whitelist filter(id__in, tenant)). [scout OPS-1 → fixed OPS-5]
- [ ] **CustomerOrderConsumer accepts any order_number (enumeration)** — RESOLVED in OPS-5
      (realtime/consumers.py _check_order_ownership: session/delivery_code gate; anonymous
      residual risk documented). [scout OPS-1 → fixed OPS-5]
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
- [~] **StaffShiftSummaryView materializes orders in Python for avg prep** — RESOLVED in
      OPS-2 (ExpressionWrapper+Avg single query; currency folded into a values_list scan).
      [scout OPS-1 → fixed OPS-2]
- [ ] **Order.table_slug vs table_label dual keys** — waiter UI groups by label, routing
      uses slug; renaming a TableLink splits historical orders into two groups. No migration
      on rename, no rename warning. Partially mitigated by OPS-1 table dropdown. (models.py
      :401; WaiterPage.vue:1238). → OPS-6 (onboarding/table mgmt). [scout OPS-1]
- [ ] **revenue.py STILL materializes ledger_order_ids as a Python set** — the comment AND
      the sweep-2 "Done" entry claim a subquery, but menu/revenue.py:49 does
      `set(ledger_qs.values_list('order_id'))` then uses it in filter/exclude IN-lists. At
      90-day × busy-tenant scale this is a Postgres IN-list cliff. The false "Done" claim is
      itself the risk (next reviewer trusts it). Replace set() with a `.values('order_id')`
      subquery. (menu/revenue.py:39/49/52/63). → OPS-4. [scout OPS-2] **(corrects a false
      sweep-2 Done claim.)**
- [ ] **Order.paid_at unindexed** — Z-report (menu/views.py:6347) + daily digest range-query
      paid_at; Order.Meta.indexes has (status,created_at)/(status,updated_at) but not paid_at.
      Add Index(status, paid_at) in the same migration as the next Order change. (models.py
      :435/529). → OPS-4. [scout OPS-2]
- [ ] **Marketplace commission mixed-basis** — commission = food_subtotal × 0.10 (PRE-discount
      GMV) but the statement reports revenue as Sum(Order.total) (POST-discount), so net_payout
      makes the effective take-rate look >10% whenever a discount applies. Document the basis
      OR apply the rate to post-discount food. No config governs it. (accounts/views.py:3020;
      menu/views.py:7391). → OPS-5 (billing). [scout OPS-2]
- [ ] **Commission rate hardcoded 0.10, no per-tenant override, no rate snapshot on Order** —
      can't offer a negotiated/promo rate without a code change for ALL tenants, and historical
      orders can't be re-audited (no rate_applied column). (accounts/views.py:3020;
      models.py:452). → OPS-5 (billing). [scout OPS-2]
- [ ] **Commission statement buckets by UTC month** — created_at__year/month with no tzinfo →
      a late-night month-boundary order lands on the wrong monthly invoice for non-UTC tenants.
      (menu/views.py:7384). → OPS-5 / tz-cleanup. [scout OPS-2]
- [ ] **legacy split cash = total − wallet silently clamped at 0** — if a tip is added after a
      wallet settle, legacy_cash can go negative and max(0) hides it, so cash+wallet no longer
      reconciles to gross. A pro ledger should assert reconciliation, not clamp. (revenue.py
      :63/77). → OPS-4 (reconciliation assertions). [scout OPS-2]
- [ ] **OrderItem has no voided_by_user_id** — Z-report voided_by is always null; can't surface
      per-staff void rates / loss-prevention. Mirror Order.handled_by_user_id (1 field + 1-line
      migration). (models.py:582). → fold into next OPS batch touching voids. [scout OPS-2]
- [ ] **Order CSV "subtotal" column includes tip + nets discounts** — subtotal = total −
      delivery_fee, but total includes tip; an owner summing the column to get food sales is
      off by total tips. Also no commission_amount column. (menu/views.py:6199). → OPS-6
      (CSV/reporting polish). [scout OPS-2]
- [ ] **Z-report voids loop + dashboard/CSV N+1** — voids loop materializes items with a
      select_related('order') join per row (use annotate + DB Sum for the total); OwnerOrderExport
      iterates order.items.all() twice + payments per row without prefetch. Perf at scale.
      (menu/views.py:6388/6184). → OPS-4. [scout OPS-2 + review-major]
- [ ] **Dashboard SPA still shows gross wallet_revenue/cash_revenue, not payment_split** —
      backend now documents payment_split as the drawer-accurate figure (sales/views.py:2482)
      but OwnerDashboard cash/wallet display should migrate to it for consistency with the
      Z-report. (OwnerDashboard*.vue). → OPS-6 (polish). [review OPS-2 major, documented]

- [ ] **Promotion max_uses overspend race (REVENUE LEAK)** — PlaceOrderView checks
      `use_count >= max_uses` OUTSIDE the lock (menu/views.py:2345), then F()-increments
      inside atomic with no cap enforcement; N concurrent checkouts all pass the pre-check
      and the promo is applied N times past the cap. Same in marketplace (accounts/views.py
      ~2963/3172). Fix: `filter(pk=..., use_count__lt=max_uses).update(use_count=F+1)` and
      treat 0-rows as cap-exceeded (single atomic op, no extra latency). HIGH — money.
      [scout OPS-3]
- [ ] **PlaceOrderThrottle still IP-scoped** — OPS-3 scoped StaffOrderList + WaiterCall per
      user/table but PlaceOrderView (staff-placed orders via waiter app) still keys on IP →
      shared restaurant NAT collapses the bucket at rush. Apply the StaffOrderListThrottle
      pattern (user.pk for authed staff, IP for anon customers). (throttles.py:25). → OPS-4
      or quick follow-up. [scout OPS-3]
- [ ] **Status-advance idempotency_key sent but not consumed server-side** — client sends it
      on the status PATCH; OwnerOrderStatusUpdateView never reads it. The target-idempotency
      BFS ("already_advanced" 200) covers the stale-superseded-retry case (verified), so this
      is belt-and-suspenders, not a correctness gap. Optional: cache (key→status) inside the
      atomic for true at-least-once. LOW. (menu/views.py:5890). [scout OPS-3]
- [ ] **Offline queue drop-policy + no TTL** — queue caps at 50 dropping OLDEST (arguably the
      most urgent; per-order dedup limits the blast radius) and entries carry queuedAt but no
      TTL/expiry, so a stale op could in theory replay next session (idempotency keys make
      replay safe; only a stale cancel vs a reused integer PK is risky, and Postgres doesn't
      reuse PKs). Add an 8h/service-day TTL drop on load + consider drop-newest. MEDIUM.
      (waiter.js queue cap + _loadQueue). [scout OPS-3]
- [ ] **WalletTransaction refund idempotency/aggregate scans unindexed (tenant_id,type,...)**
      — cancel-refund EXISTS check + Z-report/digest REFUND aggregate scan WalletTransaction
      without a covering index; fine now, a scan at 10k+ orders. Add (tenant_id, type,
      created_at) index. → OPS-4 (scale). [scout OPS-3]
- [ ] **StaffOrderPaymentView cache.set after atomic block** — the cache idempotency marker is
      written post-commit; Redis-down loses it but the DB OrderPayment unique-key backstop
      (added OPS-3) now covers replay. Document the DB constraint as the primary backstop so a
      future refactor doesn't drop it. LOW. (menu/views.py:4796). [scout OPS-3]

- [ ] **customer_phone btree index is dead for icontains search** — OPS-4 added a plain
      btree on Order.customer_phone but the two search paths use `customer_phone__icontains`
      (LIKE '%..%'), which a btree can't serve; only the exact-match CRM/win-back paths
      benefit. Fix: pg_trgm GIN trigram index, OR rewrite search to digits[-9:] exact-match
      (CustomerOrdersByPhoneView already does this at menu/views.py:3184). (migration 0058).
      → OPS-4 follow-up / search-perf. [scout OPS-4]
- [ ] **OrderItem.voided_at unindexed — Z-report full-scans items every shift close** — add
      partial Index(voided_at) WHERE is_voided=True to OrderItem.Meta. (models.py:608/635;
      Z-report query menu/views.py:6730). → next OrderItem migration. [scout OPS-4]
- [ ] **DirectoryView/MarketplaceView N+1 cross-schema** — per-tenant schema switch + rating
      aggregate + promo scan inside the serialization loop (100+ cross-schema queries/cold
      request; 90s cache is a bandage). Denormalize Profile.rating_avg/rating_count via
      post_save signal/cron. (accounts/views.py:2243/2418). → marketplace-perf batch. [scout OPS-4]
- [ ] **OwnerRatingListView no pagination** — qs[:500] JSON (silently truncates, exposes a
      COUNT that diverges) + uncapped CSV. Add cursor/offset pagination + CSV date fence.
      (menu/views.py:7431/7466). → OPS-4 follow-up. [scout OPS-4]
- [ ] **CustomerRating (public) no retention prune** — write-only, grows with platform order
      volume; add a prune cron like the OPS-4 ones. (accounts/models.py:506). → retention. [scout OPS-4]
- [ ] **OwnerCustomerListView still materializes all customers before paginating** — segment
      label is Python-derived so segment filter + sort + pagination happen in Python over the
      full 3k-row aggregate; push the segment predicate (last_order_at < cutoff) to SQL for
      true DB-level pagination. (menu/views.py:8458/8601/8670). → customer-perf follow-up. [scout OPS-4]
- [ ] **Z-report by_staff = 2 OrderPayment queries** — amount + count can collapse to one
      .annotate(Sum, Count(distinct)). (menu/views.py:6761/6783). → perf. [scout OPS-4]
- [ ] **_staff_order_payload calls order.items.all() twice** — materialize once
      (list(order.items.all())) to remove a latent double-query for unprefetched callers.
      (menu/views.py:3789/3805). → perf. [scout OPS-4]
- [ ] **OwnerOrderExport 5000-row hard cap, silent truncation** — no `truncated`/count signal;
      add a header or chunked cursor export. (menu/views.py:6516/6547). → reporting. [scout OPS-4]

## Done (moved from above)
<!-- - [x] item — commit hash -->
- [x] OPS-5 "platform cockpit": Sentry tenant tags (backend middleware + SPA
      setTenantContext); health checks (Celery/channel-layer/media, 503 on hard-fail);
      admin read-only support live-orders (GET /api/admin/tenants/<id>/live-orders/,
      IsPlatformAdmin + audit now ATOMIC with the read so a failed audit rolls back the
      response — review major) + AdminConsole "view live orders" modal + renewal-date
      (subscription_end_date) column; plan-limit enforcement on dish/staff create (0=unlimited
      sentinel verified) + dish-limit upgrade toast; billing invoice_amount/currency on
      approve; SECURITY: section-assignment tenant-membership whitelist (fail-CLOSED, review
      major fixed the destructive fail-open) + CustomerOrderConsumer ownership/delivery-code
      gate (anonymous residual risk documented); backups/restore/rollback runbook
      (LAUNCH_CHECKLIST §9). migration sales/0019. **Brutal hardware ordeal: thermal
      black-screens; ROOT CAUSE was a runaway test (unmocked .exists() spun the
      username-dedup loop → MemoryError + CPU peg + heat) — fixed; once fixed the full suite
      ran in 44s. Verified via branch + foreground after.** Backend 3414 green; frontend 90
      tests/build green. Scout found a HIGH priv-esc (IsPlatformAdmin admits is_staff) + 9
      more → OPS-5b admin-security-hardening above. — ops5 (branch ops5-platform-cockpit → main)
- [x] OPS-4 "scale fences": OwnerOrderListView two-mode (active hot path = status-fenced,
      no full-table scan / no JOIN-COUNT; history = paginated {results,has_more,limit,offset}
      envelope, date-fenced) — date fence kept OFF the active path (review-major fixed);
      OwnerCustomerListView server-side pagination + DB search (name/phone/email — email
      restore was a review-major) + single GROUP BY; indexes Order(customer_phone),
      Order(status,paid_at), WalletTransaction(tenant_id,type,created_at) (menu/0058,
      accounts/0043); revenue.py + return-rate Python-set → subquery (results byte-identical,
      the FALSE sweep-2 claim now actually true); retention crons prune_notification_logs
      (180d) / prune_winback_nudges (120d > 90d dedupe) / prune_staff_messages (90d +
      created_at index) + beat + LAUNCH_CHECKLIST; **PROMOTION max_uses OVERSPEND RACE fixed
      (money): atomic filter(use_count__lt=max_uses).update(F+1) in BOTH PlaceOrderView +
      MarketplacePlaceOrderView, code-promo→400 / auto-promo→strip+full-price on cap; I
      verified the unlimited sentinel is null (not 0) so unlimited promos take the
      unconditional branch — no use_count<0 trap**; PlaceOrderThrottle per-user (staff) / IP
      (anon); frontend Orders active/history tabs + Customers paginated search. Review: 2
      majors (date fence, email search) fixed + verified by me; promo race + both paths +
      sentinel verified in code. Scout: 9 → Scout notes (notably the customer_phone btree is
      DEAD for icontains — needs trigram). NOTE: first launch died on a backtick-in-contract
      script bug (0 agents) — fixed + re-ran. Backend 3360 green; frontend 90. — ops4 commit.
- [x] OPS-3 "integrity on flaky wifi": DB-backed idempotency — Order.idempotency_key
      (menu/0056) + OrderPayment.idempotency_key (menu/0057), both conditional-unique
      (NULLs allowed); PlaceOrderView AND MarketplacePlaceOrderView pre-check + persist +
      IntegrityError-refexh-winner (marketplace was MISSING — review critical, fixed);
      OwnerOrderStatusUpdateView atomic+select_for_update + idempotent-by-target (BFS
      "already_advanced" 200 so a stale superseded retry isn't a scary 400);
      OwnerOrderBulkStatusView now also atomic+locked (review/scout major); mark-paid
      idempotency (cache.set moved inside atomic; DB already-PAID guard is the real Redis-
      down backstop); StaffOrderPaymentView persists the key + catches IntegrityError →
      returns existing row. Frontend: waiter offline queue persisted to localStorage
      (kepoli.waiterQueue.v1) + rehydrated, each op carries its idempotency_key; flush
      hygiene (permanent-4xx drop+toast, 409 refetch-self-heal, transient exp-backoff) —
      replaces re-queue-forever. Throttles scoped per-user (staff) + per (tenant+table)
      (waiter-call). Review found a real marketplace double-charge critical + bulk-lock
      major; fix agent applied; I verified both in code + the BFS + ran gates. Scout: BFS
      note over-stated (verified), 6 → Scout notes (incl. a promo-overspend REVENUE LEAK).
      Backend 3302 green; frontend 90 tests green. — ops3 commit.
- [x] OPS-2 "end-of-day money truth": Profile.service_day_cutover_hour (tenancy/0039) +
      service_day_window helper (DST-correct local end-datetime, not +timedelta); owner
      Z-report (GET /api/owner/z-report[.csv]) — collected cash/wallet via shared
      split_revenue_for_orders (COMPLETED+PAID+paid_at window), refunds, voids (reason),
      tips, per-staff (windowed on order__paid_at to reconcile), net + net_cash_position,
      print + CSV; OrderPayment method-correction endpoint (audit fields, does NOT move
      money — relabels only, menu/0055); revenue-truth fix (dashboard+digest cash/wallet
      split now PAID-only, not in-flight; refunds_issued line added); TruncDate tenant-tz +
      owner/waiter "today" tenant-tz; shift summary cash/wallet split + single-query avg
      prep; void_reason/recorded_by surfaced in order detail + CSV. **MONEY REVIEW found 3
      CRITICALS (cross-tenant refund leaks ×2 — WalletTransaction is shared-schema, queries
      lacked tenant_id AND refund rows were written without it; by_staff windowed on
      OrderPayment.created_at not paid_at) + 6 majors. Fix agent applied them; I then
      verified EVERY fix in code personally: tenant_id now written at all 4 refund-creation
      sites + filtered in both report queries; by_staff/collected/shift all PAID+paid_at;
      DST window; correction moves no money.** Backend 3284 green; frontend gates green.
      Scout: 1 resolved (shift-summary perf), 11 → Scout notes (incl. catching a FALSE
      sweep-2 "Done" claim about revenue.py). — ops2 commit.
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
