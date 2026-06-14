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
- [~] **Admin PII-read audit logging** — RESOLVED for rides in OPS-5c (AdminRideListView now
      logs RIDE_PII_VIEWED + IsPlatformAdmin + AdminPIIThrottle). Delivery-equivalent admin PII
      GETs (if any remain) still to confirm. [scout OPS-5b → fixed OPS-5c]
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

### OPS-6b — A11Y / SEO / FIRST-IMPRESSION POLISH (scout OPS-6 cluster)
- [ ] **<html lang="en"> hardcoded; dir only set after JS hydration (a11y/SEO, WCAG 3.1.1)**
      — AT + non-JS crawlers see English/LTR before locale.js fixes it. Set lang/dir
      synchronously (cookie-driven inline script) or SSR. (index.html:2; locale.js:27). [scout OPS-6]
- [ ] **JSON-LD always @type "Restaurant"** regardless of business_type — pharmacy/grocery/
      bakery/retail/cafe mis-indexed. Add BUSINESS_TYPE_SCHEMA_MAP. (useSeoMeta.js:208). [scout OPS-6]
- [ ] **og:site_name overwritten with tenant name** — every social share drops Kepoli platform
      attribution. Restore BRAND_NAME for og:site_name; tenant stays in og:title. (useSeoMeta.js:178).
      [scout OPS-6]
- [ ] **Wizard step-nav has no forward-progression guard** — a tenant can jump to Publish with
      an empty menu/no brand; StepPublish warns but doesn't block. Track highestCompleted +
      disable Publish until canPublish. (Wizard.vue:44; StepPublish.vue:41). [scout OPS-6]
- [ ] **Activate.vue: <main> nested in <section> (HTML-invalid) + decorative card shows the
      post-activation success string as pre-activation copy** (confusing). (Activate.vue:3/17/24).
      [scout OPS-6]
- [ ] **a11y keyboard: Cart map dialog doesn't move focus in on open; Menu.vue review carousel
      not keyboard-reachable (hidden scrollbar, no tabindex)**. Standard APG dialog focus +
      tabindex/arrow handlers. (Cart.vue:883/1101; Menu.vue:277). [scout OPS-6]
- [ ] **Pharmacy option has no "parapharmacie / no Rx" disclaimer** in the wizard — qualified
      leads churn post-signup. One-line hint. (StepPublish.vue:107). [scout OPS-6]
- [ ] **<noscript> is English-only** for an ar/fr SaaS — stack all three + a support link.
      (index.html:38). [scout OPS-6]
- [ ] **StaffChangePasswordView has no throttle** — session-gated current-password brute-force.
      Add a per-user/IP throttle (auth-endpoint pattern). (accounts/views.py:1194). [review OPS-6 minor]
- [ ] **Print rule .ui-command-deck button{display:none} also hides OwnerLaunchSuccess buttons**
      — scope the @media print block to analytics panels only. (tailwind.css ~2885;
      OwnerLaunchSuccess.vue:60). [review OPS-6 minor]
- [ ] **Cart loyalty_/schedule_/promo_not_found branches still pass raw data.detail to customers**
      — extend the OPS-6 generic-message mapping to these named branches. (Cart.vue:1951/1982/1987).
      [review OPS-6 minor]
- [ ] **priceZeroWarningBody says "the following" but lists no dish names** — backend
      publish_warnings returns only a count; either list slugs or reword. (messages.js;
      tenancy/serializers.py:210). [review OPS-6 minor]
- [ ] **email_delivery_drill --help still references menu.ibnbatoutaweb.com** (dev-ops CLI help
      default, not user-facing) — cosmetic. (email_delivery_drill.py:37). [grep OPS-6]

### OPS-5d — SECURITY (scout OPS-5c cluster; next security batch)
The OPS-5c scout (SaaS-expert lens) surfaced these while we hardened uploads/SSRF/PII.
Several are HIGH. file:line in scout output; verify before acting.
- [ ] **Celery `run_management_command` = arbitrary command execution (HIGH)** — accounts/tasks.py
      :100-104 passes any `name` straight to `call_command`; the task is registered by name and the
      default broker (redis://redis:6379/0) has NO auth, so anyone who can LPUSH to Redis can run
      `shell`/`dbshell`/`flush`/`migrate` with full DB creds (the inline-thread fallback runs in the
      web process too). Fix: (1) set Redis `requirepass`/ACL + validate the URL at startup; (2) replace
      the generic task with per-command tasks OR an allowlist of permitted command names. [scout OPS-5c]
- [ ] **Google One-Tap auto-links without `email_verified` (account takeover, HIGH)** —
      _verify_google_token (accounts/views.py:299-316) checks aud+sub but NOT the email_verified
      claim, and CustomerGoogleAuthView (548-558) silently links the Google identity to an existing
      phone-registered Customer by email → an unverified-email Google account can take over a Kepoli
      customer. Fix: `if not data.get('email_verified'): return None`. One line. [scout OPS-5c]
- [ ] **AdminWalletBonusView bulk-credit double-credit race (money)** — accounts/views.py:1609-1640:
      idempotency `exists()` pre-check and the balance `UPDATE(F+1)` are not atomic; two concurrent
      POSTs with the same idempotency_key both clear the guard and both run the UPDATE (the unique
      idempotency_key only blocks the 2nd ledger insert — balances still inflate). Fix: SELECT FOR
      UPDATE on a sentinel / `cache.add` mutex (campaign-cap pattern), or bulk_create-first then
      UPDATE only on success. [scout OPS-5c]
- [ ] **CORS_ALLOWED_ORIGIN_REGEXES default allows `*.localhost:5173` in prod** — settings.py:408-414
      default regex stays active if DJANGO_CORS_ALLOWED_ORIGIN_REGEXES is blank → any localhost:5173
      origin gets credentialed cross-origin access to the prod API. Fix: change in-code default to ''
      and add the var (empty) to coolify.env.example with a comment. [scout OPS-5c]
- [ ] **uvicorn `--forwarded-allow-ips='*'` lets DRF throttles read spoofable XFF** —
      docker/entrypoint.sh:41; DRF's SimpleRateThrottle.get_ident() trusts XFF unboundedly, so
      _IPThrottle subclasses (OrderHandoff/CheckoutIntent, menu/throttles.py) can be reset per-request
      by sending `X-Forwarded-For: <random>`. Fix: pin --forwarded-allow-ips to the docker bridge
      subnet OR make _IPThrottle use the trusted-proxy-aware _client_ip helper. [scout OPS-5c]
- [ ] **Customer session can be layered onto a staff session (cross-persona fixation)** —
      OTP/email/Google auth write customer_id into the SAME Django session without checking
      request.user.is_authenticated (accounts/views.py:411-418/548/837); a staff/owner can mint a
      customer identity on their privileged session. Fix: refuse the customer_id write when
      request.user is an authenticated staff user; consider a separate customer cookie name. [scout OPS-5c]
- [ ] **CustomerReservationsView no throttle + returns cancel_token** — accounts/views.py:711-766 is
      AllowAny, unthrottled, and returns each reservation's cancel_token UUID; a session holder can
      bulk-harvest tokens and learn which restaurants a customer booked. Fix: add a throttle (~60/hr)
      and stop returning cancel_token in the list (cancel via the emailed link). [scout OPS-5c]
- [ ] **public_urls.py serves /media/ via Django static_serve in prod** — config/public_urls.py:14-18
      adds django.views.static.serve unconditionally on the non-DEBUG public host: no Cache-Control/
      security headers, holds an fd open, historically traversal-friendly. Nginx already owns /media/
      end-to-end. Fix: remove the route (or guard behind SERVE_MEDIA_FROM_DJANGO). [scout OPS-5c]
- [ ] **DJANGO_SUPERADMIN_PASSWORD still passed as `--password` CLI arg** — docker/entrypoint.sh:26-29
      funnels the secret through argv (visible in /proc/<pid>/cmdline, docker inspect, deploy logs)
      even though ensure_platform_admin already prefers PLATFORM_ADMIN_PASSWORD env. Fix: set
      PLATFORM_ADMIN_PASSWORD in entrypoint and drop --password; rename in coolify.env.example.
      [scout OPS-5c] (deploy-config; complements the OPS-5b in-code env path)
- [ ] **DJANGO_ADMIN_URL default 'admin/' + hardcoded nginx /admin/ block** — settings.py:675 +
      frontend/nginx.conf:126-138: admin path is discoverable and a two-step env+rebuild to change.
      Fix: add DJANGO_ADMIN_URL to coolify.env.example + envsubst the nginx location so it tracks the
      Django setting. [scout OPS-5c]

### OPS-5c — SECURITY/OPS FOLLOW-UP — SHIPPED (the items below are DONE; see Done section)
- [ ] **is_staff STILL bleeds elsewhere? — RESOLVED in OPS-5b** for menu/permissions
      (user_can_edit_tenant/menu), tenancy/api _can_edit_tenant, sales IsTenantEditor (all
      dropped is_staff). If any new gate copies the old triple-check, fix it. [scout OPS-5b → fixed]
- [ ] **Image-upload content-type trust (SECURITY)** — _optimize_image except-fallback
      (tenancy/api.py ~127) stores raw bytes with the client-supplied content_type; a JPEG/SVG
      polyglot can be served verbatim. Pillow transcode is the real sanitiser — on fallback,
      reject or force application/octet-stream. Same on driver-doc upload (ride_views.py ~908).
      [scout OPS-5b]
- [ ] **AdminRideListView / AdminCarApprovalView: permission_classes=[] + manual check, no
      throttle, no audit on PII GET (SECURITY)** — ride_views.py ~1232/1301; mirror the OPS-5/5b
      pattern (IsPlatformAdmin + AdminPIIThrottle + audit). authentication_classes=[] also drops
      DRF CSRF. [scout OPS-5b]
- [ ] **OSRM SSRF** — DELIVERY_OSRM_URL passed verbatim to requests.get (tenancy/routing.py
      ~81/131); validate scheme + non-RFC1918 host (or allowlist) at settings parse. [scout OPS-5b]
- [ ] **IsTenantEditor lifecycle scope** — RESOLVED via is_staff drop, but confirm tenant
      LIFECYCLE endpoints (suspend/cancel) use IsPlatformAdmin not IsTenantEditor. [scout OPS-5b]
- [ ] **DriverDocUploadView no throttle** — AllowAny 8MB uploads + admin-email on each; add a
      per-session throttle (ride_views.py ~945). [scout OPS-5b]
- [ ] **AnalyticsEventIngestView throttle IP-scoped** — CDN/shared-NAT collapses the 600/hr
      bucket; key on (tenant, ip) like WaiterCallThrottle. (menu/views.py ~1047). [scout OPS-5b]
- [ ] **PasswordResetToken / ActivationToken never pruned** — add a prune cron (delete used
      >7d). (accounts/models.py ~514). [scout OPS-5b]
- [ ] **TRUSTED_PROXY_COUNT not declared in settings.py** — read via getattr default 1 in 2
      places; declare it explicitly + comment the Coolify topology (Traefik+nginx may be 2).
      Also: get_request_ip miscount fallback returns spoofable XFF[0] — clamp safely.
      (middleware.py ~137; sales/audit.py ~29). [scout OPS-5b + review minor]
- [ ] **SESSION_SAVE_EVERY_REQUEST not set** — 90-day window is ABSOLUTE not sliding; read-heavy
      staff get logged out mid-shift. One line: SESSION_SAVE_EVERY_REQUEST=True. [scout OPS-5b]
- [ ] **AdminWalletBonus balance_after stale-read** under concurrent wallet writes (documented
      limitation; per-customer credit_wallet or returning-UPDATE for exactness). [review OPS-5b minor]
- [ ] **Plan-limit returns HTTP 400 not 402** — still deferred; SPA axios behavior unaudited.
      [review OPS-5/5b minor]

### OPS-5b — ADMIN SECURITY HARDENING — SHIPPED (the items below are DONE; see Done section)
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
- [x] OPS-5c "security follow-up" (8 items, all verified by me in code): (1) image-upload
      content-type hardening — ImageUploadView rejects non-image/SVG/ICO content types up front
      and _optimize_image now RAISES on a Pillow decode failure → 400 instead of echoing the
      client content_type (polyglot guard); stored type is always the server-derived WEBP.
      (2) Ride-admin PII views restored to OPS-5/5b standard — AdminRideListView + AdminCarApprovalView
      now IsPlatformAdmin (DRF session auth + CSRF) + AdminPIIThrottle, and AdminRideListView logs
      RIDE_PII_VIEWED on the GET (new Actions member, sales/0021). (3) OSRM SSRF guard
      (tenancy/routing.py) — _validate_osrm_url blocks non-http(s) schemes + 169.254.169.254 metadata
      (incl. IPv6 aliases) + loopback while INTENTIONALLY allowing RFC-1918 (docker-internal OSRM is
      the primary topology); falls back to the haversine estimate on a blocked/invalid URL; reviewer
      caught the redirect gap → both requests.get now pass allow_redirects=False so a compromised OSRM
      can't 302 to the metadata IP. (4) prune_auth_tokens cron (PasswordResetToken + ActivationToken,
      used-or-expired & >30d) + daily beat schedule; I switched it to a single Q-filter so the reported
      counts are accurate (no UNION double-count). (5) TRUSTED_PROXY_COUNT declared explicitly in
      settings; get_request_ip (audit) + _client_ip (middleware) fall back to REMOTE_ADDR (not
      spoofable XFF[0]) when the count exceeds the XFF length. (6) SESSION_SAVE_EVERY_REQUEST=True
      (sliding 90-day window so staff aren't logged out mid-shift). (7) DriverDocUpload (per-session,
      10/hr) + AnalyticsEvent (per tenant+ip) throttle scoping; I removed the now-orphaned
      analytics_events scope. New test_ops5c_security.py (28 tests: SSRF block/validate/redirect,
      prune, proxy-miscount, analytics keying) + ride/image tests. Reviewer found 3 major (redirect
      guard, missing test file, unasserted ride audit) — all fixed + verified by me. CAR_DOCS_VIEWED
      enum left as forward-looking (no car-docs GET endpoint yet; migration already paid). Backend
      3502/0, migrations clean, no frontend touched. Scout → OPS-5d cluster above (Celery RCE, Google
      email_verified takeover, wallet-bonus race, CORS localhost regex, +6). — ops5c commit.
- [x] OPS-6 "first impressions + onboarding + polish" — COMPLETES THE OPS PROGRAM
      (OPS-1..6). Killed the hardcoded dev domain (doro.menu.ibnbatoutaweb.com) from every
      customer-facing surface → config-driven brand domain/email in lib/brand.js
      (VITE_BRAND_DOMAIN/VITE_SUPPORT_EMAIL + Kepoli fallbacks; only a dev CLI --help example
      remains). Config-driven pricing SCAFFOLD with clearly-marked placeholder amounts (owner
      sets real numbers in one place — decision-gated) + distinct badge i18n keys (was one
      'available' for 3 concepts). Empty-state CTAs on quiet-but-published Orders. Polish sweep:
      formatCurrency everywhere (incl. MarketplaceOrderStatus — review major), app-locale dates
      (no toLocaleString(undefined)), RTL logical-property fixes, Cart no longer leaks raw
      backend detail to customers (generic i18n message), analytics @media print stylesheet,
      PWA icons split any/maskable. Onboarding: CSV import surfaced IN the dish wizard (wired to
      existing OwnerMenuImportView), category-delete shows dish_count + warns, in-app staff
      change-password (POST /api/staff/change-password/, current-pw verified + Django validators
      + session kept), per-table QR print, price-0 publish warning (publish_warnings on Profile;
      0 still allowed — free items legit). Review: 1 major (MarketplaceOrderStatus currency)
      fixed + verified by me; dev-domain eradication grep-verified. Backend 3474/0, frontend
      90/build green. Scout → OPS-6b a11y/SEO/UX cluster above. — ops6 commit.
- [x] OPS-5b "admin security hardening": IsPlatformAdmin PRIV-ESC fixed — dropped is_staff
      (Django /admin/ flag) from the gate AND, completing it, from menu.permissions
      user_can_edit_tenant/user_can_edit_menu + tenancy.api _can_edit_tenant + sales
      IsTenantEditor (a Django staff user could previously write to ANY tenant's menu/profile/
      lifecycle); ensure_platform_admin verified to set role+is_superuser so real admins still
      pass. Admin-auth consolidated onto IsPlatformAdmin (incl. AdminPlatformAnalyticsView +
      AdminDeliveryZoneDetailView — review majors) + URL-sweep test rejects TENANT_OWNER. PII
      read audit+throttle (CUSTOMER_PII_VIEWED) on AdminCustomer list/detail; admin-write
      audits (CUSTOMER_DRIVER_TOGGLED, DELIVERY_JOB_CREATED, TENANT_DELETION_REQUESTED) +
      PLAN_FEATURE_FLAGS_UPDATED/PLATFORM_SETTINGS_UPDATED enum members (was raw strings) +
      choices migration; audit-log IP now trusted-proxy-aware (rightmost, not spoofable XFF[0]);
      plan-limit dish/staff create now atomic+locked (race fixed, 0=unlimited preserved);
      AdminWalletBonus populates balance_after; ensure_platform_admin reads PLATFORM_ADMIN_PASSWORD
      env (not CLI arg); health endpoint no longer leaks MEDIA_ROOT path. Review found 4 majors
      (2 unconsolidated views, raw-string action, 2 weak tests) — fix agent applied; I then
      personally COMPLETED the priv-esc (the is_staff bleed at 4 more helpers the batch missed)
      + verified the boundary both directions + fixed the one test that asserted the old insecure
      access (test_staff_returns_true → test_staff_only_returns_false). Backend 3459/0,
      frontend 90/build green. Scout → OPS-5c cluster above (image-upload polyglot, ride-admin
      PII views, OSRM SSRF, token prune, session-sliding, throttles). — ops5b commit.
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
