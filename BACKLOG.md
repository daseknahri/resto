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

## ⭐ PRODUCTION-READINESS ROADMAP (multi-agent audit, owner asked for "production-grade startup")
**Verdict: ~85% production-grade on CODE (money/tenancy/idempotency core is strong + CI-tested vs real Postgres),
NOT yet on OPERATIONS.** Full audit (architecture map + 7 dimension audits + synthesis) ran 2026-06; the deployed
app is Django `backend/` + Vue `frontend/` via `docker-compose.coolify.yml` (manual Coolify redeploy) — the Node
`platform/` stack is DEAD scaffold. `ci.yml` DOES run the Django suite vs Postgres + Vue lint/build on push+PR
(my earlier "no CI" premise was wrong). Ranked, mostly NON-gated:
- [~] **R1 (P0) Automate DB backups + rehearse restore** — SCRIPTS SHIPPED (56e4be1): install_backup_cron.sh
      (daily backup cron + on-fail alert + off-VPS --remote-copy-cmd hook), backup_freshness_probe.sh (dead-cron
      watchdog: alarms if newest dump missing/>26h), runbook §8 restore-drill checklist. Verified bash -n + live
      sandbox (marker isolation, alert-on-failure, dry-run/remove). OWNER GATE: install crons on VPS + run the §8
      RESTORE DRILL once before launch — that drill (needs VPS/Docker/Postgres) is the actual R1 completion gate.
- [x] **R2 (P1) Kill dead deploy.yml — DONE (ea20ebf)** — deleted .github/workflows/deploy.yml: it fired every
      push to main and exclusively served the DEAD platform/ scaffold (built platform/apps/* → ghcr platform-*
      images nothing consumes + an uninvited, NON-CI-gated Coolify webhook). Real app deploys via manual Coolify
      Redeploy building from source (unaffected); ci.yml remains the gate. OWNER-GATED follow-ups (surfaced, not
      assumed): (a) want push-to-deploy? → I'd add a CI-gated webhook-only workflow (workflow_run after ci.yml, no
      image build since Coolify builds from source); (b) enable branch protection on main requiring CI-green. Do
      NOT rebuild a build-and-push workflow (Option A) — Coolify building from source is simpler + already works.
- [~] **R3 (P1) Sweeps + Celery worker default-on** — sweep_delivery_jobs/enforce_subscriptions/expire_charge_requests
      only run if an operator hand-wires them; CELERY_BROKER_URL not in required env → beat idle by default, silent.
      (making it required is owner-gated; the heartbeat/alert half is in flight, see R4).
- [x] **R4 (P1) Celery beat heartbeat → health detects dead worker — DONE (prod-harden-1)** — new
      accounts.tasks.write_beat_heartbeat (beat every 60s, cache.set celery_beat_heartbeat ttl 300); _check_celery
      now reports degraded on missing/stale heartbeat once the broker is set + past a 240s boot grace (dev/no-broker
      preserved; +locmem guard so a per-process-cache SKIP_DEPLOY_CHECK edge can't false-flag). Backend 3889/0.
- [~] **R5 (P1) AddIndexConcurrently on hot tables + rehearse migrate/rollback — PREREQ+GUIDE DONE (0fe4c9d)** —
      django.contrib.postgres added to SHARED_APPS (enables AddIndexConcurrently; verified no migration + 3952
      passed). backend/MIGRATIONS.md = canonical guide: the per-tenant ACCESS-EXCLUSIVE-×N lock problem, the
      atomic=False/CONCURRENTLY convention, ready-to-apply conversions for the 3 recent pure-AddIndex migrations
      (menu/0058 Order = top priority, accounts/0043, tenancy/0042) + rollback. CONVERSION GATED on a staging
      rehearsal (OWNER): can't verify atomic=False is txn-free in django-tenants 3.6.0's --tenant loop + new-tenant
      auto_create_schema without Postgres → a wrong conversion breaks onboarding. GO/NO-GO checklist in the doc.
      [unblocked once R20 staging exists]
- [x] **R6 (P1) Dependency CVE patch + scanning + Dependabot — DONE (prod-harden-deps-ci)** — PATCHED the
      vulnerable deps (not just added a scanner): Django 4.2.11→4.2.30 (~20 advisories incl. CVE-2024-45231 /
      CVE-2025-59682 / CVE-2026-25673-4, stayed on 4.2 LTS), DRF 3.14→3.15.2, python-dotenv 1.0.1→1.2.2, Pillow
      10.4→12.2.0 (image CVEs; _optimize_image verified, 11 image tests green), axios 1.7.7→1.18.0, + dev tooling
      vitest 2→3.2.6 / vite 5→6.4.3 / eslint→9.39.4 / postcss + esbuild override (cleared the CRITICAL vitest +
      HIGH esbuild/eslint dev advisories). Added BLOCKING ci.yml gates: pip-audit -r requirements.txt (backend) +
      npm audit --audit-level=moderate full-tree (frontend) — both verified to FAIL on a planted CVE; + an
      informational full npm audit step. Added .github/dependabot.yml (pip/npm/github-actions weekly). pip-audit &
      npm audit both report 0 vulns; backend 3889/0/28, frontend 124 tests, all gates green. [scout prod-readiness]
- [x] **R7 (P1) MFA on cross-tenant admin/owner + per-account lockout — COMPLETE (R7a 6a9a5e2 + R7b daac51b/0ba18b6)** —
      R7a: per-account login lockout in LoginSerializer (10 fails → 15-min ATOMIC FIXED-window cache.add+incr; review
      caught+fixed a slow-drip DoS; fail-open on cache error; per-PK key). R7b: full TOTP MFA — pyotp + UserTOTPDevice
      (accounts/0044, PBKDF2 single-use backup codes) + setup/confirm/verify/disable/status endpoints + flag-gated
      LoginView 202 second-factor + frontend enrollment (QR + backup codes) & login verify step. DEFAULT-OFF
      (MFA_REQUIRED_ROLES empty + opt-in enrollment ⇒ live login byte-for-byte unchanged); reviews caught+fixed TOTP
      replay-within-window, pending-session fail-closed, narrowed login DB-except, side-effect-free /mfa/status/.
      OWNER: set DJANGO_MFA_REQUIRED_ROLES to enforce per role when ready. R7a follow-up DONE: all
      lockout counters now use atomic cache.add()+cache.incr() — voucher (accounts/views.py), cashout
      confirm (driver_service.py), MFA (mfa_views.py), and the last holdout (cashout LOOKUP, menu/views.py)
      migrated from racy get+set in this session.
- [x] **R8 (P1) Fix frontend Sentry release tag — DONE (with prod-harden-load)** — sentry.js now reads
      VITE_SENTRY_RELEASE first (the var the Dockerfile/compose actually inject), fallback VITE_APP_VERSION.
      Frontend lint+build green. **DEPLOY STEP (owner/ops):** set VITE_SENTRY_RELEASE=$SOURCE_COMMIT as the frontend
      build arg in Coolify so the SPA release tag populates with the git SHA (enables regression-by-release triage).
- [x] **R9 (P1) Paginate Marketplace + Directory (backend) — DONE (prod-harden-pagination)** — ?q= search moved
      into SQL (.filter(Q name|tagline|cuisine|city icontains) on the FULL queryset before slicing — finds any tenant,
      no longer Python-windowed over [:200]); backward-compatible page/page_size + has_more (+marketplace total) added
      to both views (default page_size=100 = old cap so the un-updated frontend is unaffected; explicit page_size
      clamped [1,50]); sort applied to the full set before the page slice; cache key varies by page/q; single-flight +
      post-cache recompute intact. Backend 3949/0; +14 tests.
- [x] **R9b (P2) Frontend load-more — DONE (c006520) + R9c polish (c57881e)** — Marketplace + Directory "Load more"
      consumes page/has_more, carries the same filter params, appends results, race-guarded, aria-live. Initial fetch
      now page_size=20. R9c: hide the button over a client-side-filtered-empty grid + named MKT_PAGE_SIZE. 124 fe tests.
      **R9d (minor, deferred): add page-level load-more unit tests (SPA has no Directory/Marketplace page tests yet).**
- [x] **R10 (P1) Run frontend vitest + verify:i18n in CI — DONE (prod-harden-deps-ci)** — ci.yml frontend job now
      runs verify:i18n + lint + test + build (was only lint+build); the 124 vitest tests + i18n key-completeness
      now gate every push/PR. [non-gated]
- [ ] **R11 (P1) Prove uptime/cert-expiry/disk alerting is wired (not just scripted)** — webhooks default empty;
      no cert-expiry or disk monitor. [owner-gated: VPS webhook activation]
- [x] **R12 (P2) Namespace loyalty-redeem idempotency key by schema — DONE (prod-harden-1)** — loyalty key now
      f"loyalty:{schema}:{raw}" at all 3 sites (read/create/replay); within-schema dedup preserved, same client key
      now succeeds independently across tenants. Scout CONFIRMED this was the LAST un-namespaced money key (others
      key off globally-unique public-schema PKs). New DB test (2-schema same-key) runs in CI. [scout prod-readiness]
- [x] **R13 (P2) Non-root containers + bounded ASGI request timeout — DONE (prod-harden-containers, 8824fa1)** —
      backend USER 10001 (chown /app), frontend nginx UID 101 on :8080, compose user: on api/worker/beat.
      BoundedHTTPMiddleware bounds HTTP only (websockets + the /api/marketplace/track/ SSE stream exempt;
      HTTP_REQUEST_TIMEOUT default 120s) + uvicorn keep-alive/graceful-shutdown. entrypoint media-writable
      fail-fast (S3-aware, bypass flag) + SECURITY_LOG_FILE non-root note. Review caught+fixed a critical (SSE
      severed by a naive timeout). Verified bash -n + py_compile + full suite 3952 passed. OWNER: pre-chown the
      media_data volume to 10001:10001 once; image build/boot is the deploy-time gate.
- [x] **R14 (P2) Bound inline-notification threads + cache-stampede lock — DONE (prod-harden-load)** —
      accounts/tasks.py enqueue() inline fallback now submits to a module-level bounded ThreadPoolExecutor
      (max_workers=4) that closes the DB connection in finally (no per-thread conn leak); Celery-on path unchanged.
      accounts/views.py _public_list_get_or_build single-flights the marketplace/directory rebuild (per-cache-key
      cache.add lock, bounded 2s follower wait, 10s lock TTL, always returns a payload). Backend 3898/0. +17 tests.
- [x] **R14b (P2) Route last raw threads through the bounded pool + single-flight the menu cache — DONE (prod-harden-load-2)** —
      push_charge_request + the AT_RESTAURANT "driver arrived" push now route through accounts.tasks.enqueue (new
      charge_request shared_task; web_push_tenant reused) — no raw threads remain on those paths. Factored a generic
      tenancy/cache_utils.get_or_build_single_flight (DRY: the marketplace/directory helper now delegates to it) and
      applied it to the per-tenant MENU list cache (the hottest public path — every QR scan). Backend 3913/0; +15 tests;
      fixed 2 review minors (dead import, non-200 status re-emit). [scout prod-harden-load]
- [x] **R14c (P3) Single-flight the /api/meta/ cache — DONE (3632e0d)** — TenantMetaView now builds via
      get_or_build_single_flight; live is_open_now recompute still runs every request after the cache; key/TTL/bust
      paths unchanged; 10 meta-cache tests updated; 4005 passed.
- [x] **R15 (P2) payments logger + request_id→Sentry tag — DONE (prod-harden-observability)** — dedicated "payments"
      logger at wallet_service credit/debit/transfer/float failures + the swallowed driver-payout failure (alertable,
      still reaches Sentry); RequestLoggingMiddleware sets a guarded request_id Sentry tag (log↔error pivot). **Review
      caught + fixed a SECRET LEAK** (insufficient-funds log emitted the raw reference = the live cash-out 6-digit code
      → now logs only _ref_kind namespace). Docs note for the owner Sentry steps (traces rate + alert rules). 3925/0;
      +12 tests. [scout prod-readiness]
- [x] **R15b (P2) Extend payments logger to 3 more money-failure paths — DONE (prod-harden-money)** —
      MarketplacePlaceOrderView inline-debit failure, ride_service._do_settle (failure + InsufficientFunds cash-fallback),
      and driver_service.confirm_cashout float-credit leg now log to the payments channel (driver_service reuses the
      shared wallet_service._ref_kind so the raw cash-out code is never logged). Money behavior unchanged. Backend 3935/0.
- [~] **R16 (P2) Wallet currency guard DONE; route-through-wallet_service refactor deferred (prod-harden-money)** —
      GUARD shipped: PlaceOrderView + MarketplacePlaceOrderView refuse a wallet debit on a non-MAD order (400
      currency_unsupported) before any debit; a no-op for MAD (every order today). Also corrected the order-currency
      default from "USD" → "MAD" (a MAD-only app shouldn't default unspecified currency to USD; makes the guard a true
      no-op for blank-currency dishes). **R16b DONE (6f0f575):** the 2 inline checkout wallet debits (PlaceOrderView +
      MarketplacePlaceOrderView) + the unverified-wallet sweep now route through wallet_service.debit_wallet with
      schema-namespaced per-order idempotency keys (orderpay_checkout/mktpay:{schema}:{order.id}) — adds the missing
      wallet-level idempotency that closed a double-submit double-charge window; allow_partial preserves min()-charge;
      prepay gate intact; sweep re-check now under lock. Adversarial money review APPROVE; lockout-atomic (cashout/
      voucher → add+incr, 732ed8d) shipped too. **R16c DEFERRED (money-replay caveat): the loyalty-redeem inline wallet
      CREDIT is currently CORRECT (IntegrityError-rollback on the unique key). Naive split to credit_wallet is a BUG —
      credit_wallet is idempotent-returns-existing, so on replay points would double-deduct while the credit is skipped.
      Needs an idempotency short-circuit + DB verification; not worth a money regression for consistency on correct code.** (MAD-only is the owner's confirm.)
- [~] **R17 (P2) Container image scanning (Trivy) + digest-pin bases + SBOM — fs SCAN DONE (1e671c1)** —
      .github/workflows/security-scan.yml: trivy fs (vuln+secret+config) on push/PR/weekly-cron, fail HIGH/CRITICAL,
      ignore-unfixed, SARIF→Security tab; .trivyignore seeded empty; dependabot docker ecosystem (backend+frontend).
      Catches secrets + Dockerfile/compose misconfig (R13 non-root regression guard) the dep-audits miss. First CI
      run is the gate. **R17b DEFERRED (needs a Docker daemon, none here): trivy IMAGE scan of built backend/frontend
      images for OS base-CVEs + base-image DIGEST-PINNING (FROM ...@sha256:) — dependabot docker will track digests
      once pinned. SBOM gen also R17b.**
- [~] **R18 (P2) PII erasure/export tooling + retention cron — ERASURE DONE (ed37761)** — `manage.py erase_customer
      <id>` anonymizes a customer IN-PLACE across public + ALL tenant schemas (never deletes the row — CASCADE FKs
      would destroy the ledger; financial rows retained). Dry-run default, --force-erase to write, --force bypasses
      Phase-0 guards (open orders/pending charges/nonzero balance); per-tenant failures FAIL CLOSED (no false success
      audit). CUSTOMER_ERASED audit (sales/0022). Adversarial model-grep review caught + I fixed 5 missed PII fields
      (DriverPayout/WalletChargeRequest/ReservationTimelineEvent notes, RideRequest driver-FK + delivery_code,
      DeliveryJob customer_driver_note) + an over-scrub. 3981 passed. **R18b DEFERRED (owner-policy): retention
      windows/jurisdiction (GDPR export-before-erase, CCPA delay), hard-delete-vs-anonymize, export_customer command,
      auto-erasure scheduling. NOTE: WORKFLOW DIED on a transient API ConnectionRefused after impl — recovered by
      hand-review + own gates (the review/gates phases never ran); standard dead-workflow recovery.**
- [x] **R19 (P2) Police patch(create=True) + import-smoke / real-model money tests — DONE** — test_import_smoke.py
      walks every importable module under accounts/menu/tenancy/sales/realtime/config and asserts each imports cleanly
      (>50-module sanity floor; KNOWN_BROKEN registry for pinned landmines). test_no_unannotated_create_true.py scans
      every tests/*.py file and fails if any create=True lacks a # create-true-ok: <reason> annotation. All existing
      create=True occurrences annotated with justifications. 3 tests pass. [non-gated]
- [ ] **R20 (P3) Provision staging env** — unblocks rehearsing R1/R5 off-prod. [owner-gated: cost/setup]
- [x] **R21 (P3) Dockerized dev Postgres — DONE** — docker-compose.dev.yml: postgres:16-alpine
      matching the backend default DATABASE_URL (user/pass/5432/resto) with healthcheck + named
      volume. Usage in file header: `docker compose -f docker-compose.dev.yml up -d` then pytest.
      CI continues to cover the DB tests via ci.yml; this makes them runnable locally too. [non-gated, S]
- [ ] **R22 (P3) Load/stress harness (k6/locust)** — every scaling trigger (PgBouncer/workers/TTL) is an unmeasured guess.
- [x] **R23 (P3) Incident-response runbook — DONE (d20a02c)** — infra/INCIDENT_RUNBOOK.md: SEV1/2/3 + first-5-min
      triage + 8 grounded playbooks (deploy/rollback, DB restore, Redis, backup, migration, security, load, disk),
      links R1 scripts + MIGRATIONS.md, owner TODOs marked. All referenced paths/commands verified. **pytest.ini
      intentionally KEPT — it IS load-bearing: my local `pytest -q` (3981 passed) relies on it; the "vestigial"
      premise was wrong. Removing it would break local runs. Owner-gated bits (on-call/escalation/URLs) = TODOs.**
- [~] **R24 (P3) Code-split i18n locales + responsive image srcset — i18n DONE (prod-harden-frontend-perf, a84cc7d)** —
      FR (195kB) + AR (221kB) catalogs now lazy dynamic-import()'d into separate chunks, out of the entry bundle;
      EN bundled for first paint. Resilient to a failed chunk fetch (retry-evict + setLocale keeps current locale).
      Images already had loading/decoding + sized containers (no CLS); LCP heroes eager+fetchpriority. Gates green
      (124 fe tests). REMAINING → R24b: responsive image srcset needs a server-side thumbnail/CDN-proxy pipeline
      (raw /media/ uploads have no size variants) — deferred.

## Restaurant (current focus — candidates for post-v1.0)
- [ ] **Multi-branch** (one owner, several locations under one account) — large;
      tenants are single-location today.
- [ ] **Auto-print on new order** — needs kiosk browser / local agent / network
      ESC-POS printer. Manual print button shipped long ago.
- [x] **DishViewSet.perform_update marker clear not atomic** — DONE: both writes now
      wrapped in transaction.atomic() (commit after 3bb05b9).
- [x] **Clawback test asserts points_earned decrement weakly** — DONE: replaced string-
      contains check with exact assertEqual on pe_values (commit after 3bb05b9).

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
- [x] **Admin PII-read audit logging — FULLY DONE** — AdminRideListView (OPS-5c) + now
      AdminDeliveryJobListView: added AdminPIIThrottle + log_admin_action(DELIVERY_JOB_PII_VIEWED).
      New AdminAuditLog.Actions.DELIVERY_JOB_PII_VIEWED (TextChoices, no migration needed).
      +2 tests (has_pii_throttle + pii_audit_log_recorded). All admin PII endpoints now audited.
- [ ] **code_locked_until unindexed** — only matters if a future sweep/admin query
      filters on it. Review minor, explicitly "not a current issue".

## Platform / ops
- [x] **Notification provider-level retry — SMS DONE** — SmsProviderError (RuntimeError subclass)
      added to menu/sms.py; raised on Twilio non-2xx / network exceptions; permanent failures
      (no credentials, invalid phone) return False without raising (no pointless retry). The
      existing autoretry_for=(Exception,) on the Celery task now naturally retries transient
      SMS failures up to 3× with exponential backoff. +2 utility tests +2 task tests. Push/
      WhatsApp/email senders still swallow (lower-critical channels, future follow-up if needed).
- [ ] **Stripe wallet top-up seam** — build when owner has a PSP account (owner said
      not yet). Webhook → credit_wallet with event-id idempotency. Doc Phase 3.
- [ ] **Driver bank-transfer payouts** — needs a PSP. Memory note.
- [ ] **nginx bot-branch syntax** — could not run `nginx -t` locally (no docker);
      verify container start + checklist curls on the NEXT deploy, then tick this.
- [x] **Local Postgres dev environment** — DONE (docker-compose.dev.yml, R21 above).
- [ ] **_batch_business_types singleton calls** — 4 single-job endpoints pay one extra
      Profile query each. Review minor, functionally correct.
- [x] **SEO beyond OG** — DONE (sitemap.xml via config/sitemap.py + robots.txt Sitemap:
      directive; structured data enrichment, hreflang, noindex on personal routes — all in OPS-6c).

## Scout notes (SaaS-expert audit — every OPS batch appends; triage at ship)
These are an expert-lens scout's findings (not batch reviews). Each maps to a future
OPS batch or a security pass. file:line in the scout output; verify before acting.

### OPS-6c — SEO / A11Y / PWA DEPTH — ALL SHIPPED (verified against code)
All items below verified as DONE by reading the actual source (not commit hashes — code-verified).
- [x] **meta-robots personal pages** — DONE: INDEXABLE_ROUTE_NAMES allowlist in useSeoMeta.js;
      all non-listed routes emit noindex,nofollow; personal/transactional routes excluded.
- [x] **sitemap.xml + robots.txt Sitemap directive** — DONE: robots.txt has `Sitemap: /sitemap.xml`;
      backend has config/sitemap.py serving the sitemap view.
- [x] **hreflang alternates for en/fr/ar** — DONE: useSeoMeta.js emits reciprocal hreflang links
      (HREFLANG_LOCALES) on every indexable route.
- [x] **Product/MenuItem/Offer/BreadcrumbList structured data** — DONE: useSeoMeta.js emits
      BreadcrumbList on menu/category/dish pages; MenuItem/Product + Offer on dish pages;
      business node enriched with openingHoursSpecification, priceRange, geo, aggregateRating.
- [x] **DishCard role=button invalid ARIA** — DONE: article is not role=button; real hidden
      <button> provides the accessible name; qty/add buttons are properly nested siblings.
- [x] **Skip-to-content focus** — DONE: CustomerLayout.vue:123 and OwnerLayout.vue:306 both
      have tabindex="-1" on #main-content.
- [x] **Wizard aria-live step change** — DONE: Wizard.vue removed broad live region; terse
      stepAnnouncement + stepPanelRef.focus() on step change.
- [x] **Customer PWA install button mobile** — DONE: button has no hidden/sm:inline-flex classes;
      visible on all breakpoints when pwaCanInstall.
- [x] **theme-color meta static** — DONE: stores/theme.js setThemeColorMeta() syncs the meta
      tag to tenant brand on profile load; App.vue wires it.
- [x] **Customer app-manifest maskable icon** — DONE: app-manifest.json already references
      /icon-maskable-192.png and /icon-maskable-512.png with purpose:"maskable" separately.

### OPS-6b — A11Y / SEO / FIRST-IMPRESSION POLISH — SHIPPED (the items below are DONE; see Done section)
- [x] **<html lang="en"> hardcoded; dir only set after JS hydration** — DONE: public/locale-boot.js
      sets html lang+dir synchronously from stored/browser locale before Vue hydration. [scout OPS-6]
- [x] **JSON-LD always @type "Restaurant"** — DONE: BUSINESS_TYPE_SCHEMA_MAP in useSeoMeta.js
      maps business_type to the correct schema @type. [scout OPS-6]
- [x] **og:site_name overwritten with tenant name** — DONE: og:site_name uses PLATFORM_NAME
      constant in useSeoMeta.js. [scout OPS-6]
- [x] **Wizard step-nav has no forward-progression guard** — DONE: highestCompleted ref +
      forward-jump guard in Wizard.vue (lines 118-177). [scout OPS-6]
- [x] **Activate.vue: <main> nested in <section> (HTML-invalid)** — DONE (verified): no
      `<main>` in Activate.vue; structure is div>div>section+div. Decorative cards show
      title/description (not the success copy). [scout OPS-6]
- [x] **a11y keyboard: Cart map dialog + Menu.vue review carousel** — DONE: Cart.vue has APG
      dialog pattern (role=dialog aria-modal + focusable query + restore-on-close, lines 917/1122);
      Menu.vue carousel has tabindex=0 + aria-label + arrow-key handler (lines 279-284). [scout OPS-6]
- [x] **Pharmacy option has no "parapharmacie / no Rx" disclaimer** — DONE: StepPublish.vue
      shows pharmacyParapharmacieHint block when business_type == 'pharmacy'. [scout OPS-6]
- [x] **<noscript> is English-only** — DONE: index.html noscript has FR, AR, and support
      mailto link. [scout OPS-6]
- [x] **StaffChangePasswordView has no throttle** — DONE: StaffChangePasswordThrottle on
      accounts/views.py:1449. [review OPS-6 minor]
- [x] **Print rule .ui-command-deck button{display:none} also hides OwnerLaunchSuccess buttons**
      — DONE: `button:not(.print-keep)` rule in tailwind.css:2893-2901 excludes .print-keep. [review OPS-6 minor]
- [x] **Cart loyalty_/schedule_/promo_not_found branches still pass raw data.detail** — DONE:
      all three code branches return localized t() strings with explicit "Never surface raw
      backend detail" comments (Cart.vue:2034/2064/2071). [review OPS-6 minor]
- [x] **priceZeroWarningBody says "the following" but lists no dish names** — DONE: message
      was reworded to "Some published items have no price set…Review your prices" — no
      "the following" phrasing remains. [review OPS-6 minor]
- [x] **email_delivery_drill --help still references menu.ibnbatoutaweb.com** — DONE: help
      text now says "for example https://menu.example.com". [grep OPS-6]

### OPS-5x SECURITY PROGRAM — COMPLETE (2026-06-14)
OPS-5/5b/5c/5d/5e/5f/5g/5h shipped. The OPS-5h final convergence scout audited every money/auth/IDOR/
tenant-isolation surface (incl. uncommitted changes) and found NO new exploitable issue — it verified
the wallet idempotency-namespacing rule is applied consistently (schema-namespaced for menu/TENANT_APPS
schema-local ids; bare-but-safe for accounts/SHARED_APPS globally-unique PKs), session rotation, OTP
toll-fraud guard, CSPRNG, cash-out IDOR lockout, and log scrubbing. The money/IDOR fences have converged.
Any FUTURE security finding starts a fresh batch; there is no pending security cluster.

### OPS-5h — SECURITY — SHIPPED (the items below are DONE; see Done section)
The OPS-5g scout EXPLICITLY confirmed the core money/IDOR/wallet-idempotency surface is clean after
5c→5g (wallet_service locks + replay assertions; schema-namespaced order-pay/orderpay/voiditem;
loyalty customer-scoped; voucher/loyalty throttled; cash-out lockout; push-sub scoped; WS ownership;
OG cache-key; admin PII gated; SSRF allow_redirects=False; upload re-encode). These 5 are the
ADJACENT remainder — close them and the OPS-5x security program is done; then pivot to Phase-A eng.
- [x] **Customer login session fixation — no cycle_key** — DONE: cycle_key() called immediately before
      setting customer_id on phone-OTP, Google, email-OTP, and the staff-conflict-cleared path. Session
      rotation prevents anonymous/planted session ids surviving the anon→authenticated-customer jump.
- [x] **OTP request SMS-bombing / Twilio toll fraud — IP-only throttle, no per-recipient cap/cooldown** —
      DONE: per-recipient counter + short resend cooldown in cache (key on phone/email), independent of the
      IP throttle; a re-request no longer resets attempts=0. Direct revenue drain path closed.
- [x] **Auth OTP uses random.randint (non-CSPRNG)** — DONE: phone + email OTPs now use
      secrets.randbelow(900000)+100000 (mirrors menu/views.py:1911 _generate_delivery_code). Mersenne
      Twister replaced on the full-login-credential path.
- [x] **Cancel-refund idempotency on a NON-namespaced order_number (missed instance — money-loss)** —
      DONE: _refund_wallet_for_cancelled_order now routes through credit_wallet with
      f"cancelrefund:{schema}:{order.id}" (schema-namespaced) like all sibling refund paths.
- [x] **Cash-out code + customer phone logged in cleartext via get_full_path()** — DONE:
      RequestLoggingMiddleware scrubs SENSITIVE_QUERY_PARAMS (code/phone/token/credential/delivery_code)
      via _safe_path() before logging; live bearer credentials and PII no longer appear in app logs /
      Sentry breadcrumbs.

### OPS-5g — SECURITY — SHIPPED (the items below are DONE; see Done section)
The OPS-5f scout CONFIRMED the previously-fixed dimensions are clean (WS auth, driver/ride state
machines re-check approval, admin money caps, core wallet service, profile allowlist, IP throttles)
and said the remaining gaps cluster on (1) tenant-schema-derived idempotency keys and (2) the two
unthrottled redemption endpoints. Closing these should largely complete the money/IDOR hardening.
- [x] **Cross-tenant idempotency-key collision on customer/staff order-payment + refund keys (HIGH)** —
      DONE: all three paths schema-namespaced: CustomerOrderPayWalletView → f"orderpay_checkout:{schema}:{order.id}",
      order-payment debit → f"orderpay:{schema}:{payment.id}", void refund → f"voiditem:{schema}:{item_id}".
      The OPS-5f customer_id ownership assertion was already in credit_wallet/debit_wallet; namespace
      closes the remaining cross-tenant collision window.
- [x] **Loyalty-redeem replay trusts a client-supplied GLOBAL key with no customer filter (IDOR)** —
      DONE: both replay lookups in CustomerLoyaltyRedeemView now filter customer=_customer; throttle added
      (CustomerLoyaltyRedeemThrottle). Attacker can no longer supply another customer's key to get their
      redemption amount disclosed.
- [x] **Voucher redemption no throttle + no failed-attempt lockout (brute-force to money)** —
      DONE: VoucherRedeemThrottle added to CustomerWalletRedeemVoucherView; exponential lockout on
      consecutive invalid codes mirrors driver_cashout_confirm pattern.
- [x] **Voucher codes use a non-CSPRNG (random.choices, Mersenne Twister) for a bearer money token** —
      DONE: WalletVoucher.generate_code() now uses secrets.choice (mirrors the rest of the codebase).
- [x] **Wallet-paid rides take no hold/escrow at booking** — DONE: _do_settle (ride_service.py:128+)
      calls debit_wallet which holds a select_for_update lock on the rider row and re-checks the balance
      atomically inside the completion transaction — this is the authoritative re-verification; a rider who
      drained their wallet after booking is caught here. InsufficientFunds falls back to cash with an
      explicit payments_logger.warning and cash_fallback=True flag (rider-visible in serialization).
- [x] **OG bot endpoint cache key trusts spoofable X-Forwarded-Host + raw ?path (cache fan-out/poisoning)** —
      DONE: _og_cache_key(tenant, path) in og_views.py uses the resolved tenant.id (not spoofable Host)
      and a sanitized + bounded (128 chars) path. Non-allowlisted hosts are rejected before caching.

### OPS-5f — SECURITY — SHIPPED (the items below are DONE; see Done section)
The OPS-5e scout surfaced these (file:line in scout output; verify first). Several are HIGH.
- [x] **MarketplacePlaceOrderView DishOption price manipulation (HIGH money/IDOR)** —
      accounts/views.py:3065 builds options_map = DishOption.objects.filter(id__in=all_option_ids) with
      NO option→dish binding check, no published gate, no sign check, then unconditionally does
      unit_price += opt.price_delta (3090-3094). price_delta has no MinValueValidator (negative deltas are
      legit "remove X" modifiers), so a customer can attach a foreign/negative-delta option id to a cheap
      dish to drive the wallet-PREPAID unit_price/total DOWN, even below zero. EVERY other order path
      validates opt_dish_slug==dish.slug (menu/views.py:1649-1655/1810-1818/2186-2191) — this path is the
      regression. Fix: enforce option↔dish membership + reject mismatches like the other builders. [scout OPS-5e]
- [x] **DeliveryRatingView customer branch — no order-ownership check + no throttle (IDOR)** —
      accounts/views.py:5104 (AllowAny), the role=='customer' branch (5157-5163) only checks a session
      customer_id EXISTS, never that it owns the order, then writes customer_driver_rating/note. Driver
      (5164-5168) + restaurant (5172-5178) branches ARE gated — the customer branch is the oversight
      (sibling to the OPS-5e CustomerOrderRate fix). Reputation manipulation / stored-text, overwritable.
      Fix: require session-customer ownership + throttle (mirror CustomerOrderRateThrottle). [scout OPS-5e]
- [x] **Driver money/state endpoints gate on is_driver only, NOT driver_approved** —
      DriverPositionUpdateView (accounts/views.py:4478), DriverJobListView (4518), DriverJobDeclineView
      (4697), DriverJobStatusUpdateView (4885), ride DriverRideStatusView (ride_views.py:798). A driver
      APPROVED → accepted a job → then REJECTED can still advance it to DELIVERED via the status endpoint,
      triggering _credit_driver_earnings (require_verified=False) → banks EARNINGs after de-approval. Fix:
      re-check driver_approved at the money-emitting state transition, not only at accept. [scout OPS-5e]
- [x] **transfer_between_customers (P2P) replay branch missing the ownership assertion** —
      wallet_service.py:315-322 returns the existing tx on an idempotency hit with no sender/recipient
      check (OPS-5e added the assertion to credit_wallet/debit_wallet/credit_tenant_float/transfer_to_customer
      but not this one). Gated behind WALLET_P2P_ENABLED (off) so latent. Fix: mirror the customer-match
      assertion. [scout OPS-5e]
- [x] **OwnerWalletChargeView below-threshold instant charge — no amount cap, no throttle** —
      menu/views.py:9558 (IsAuthenticated + _can_edit_tenant_order, no throttle_classes); sub-threshold
      charges debit instantly with only the 5-min QR pay-token as consent (9663-9667). A compromised/abusive
      waiter session can fire many sub-threshold debits against a present customer within the token window.
      Fix: per-actor/customer throttle + an absolute amount/velocity cap on the instant-charge path. [scout OPS-5e]
- [x] **CustomerWalletRedeemVoucherView bypasses the wallet ledger service + no customer row lock** —
      accounts/views.py:2243 locks the voucher row but read-modify-writes customer.wallet_balance + a manual
      WalletTransaction directly (2269-2279) instead of credit_wallet, WITHOUT select_for_update on the
      Customer → lost-update race vs any concurrent wallet_service op. Fix: funnel through credit_wallet (or
      lock the customer row). Violates the single-funnel invariant in wallet_service.py:1-15. [scout OPS-5e]
- [x] **Password-reset host-header poisoning + reset doesn't invalidate sessions** —
      build_frontend_base_url falls back to request.get_host() (X-Forwarded-Host-honouring, USE_X_FORWARDED_HOST
      on) for tenant-less users (accounts/views.py:124-126); the reset link token is built from it (256-258).
      Also PasswordResetConfirmSerializer.save() (serializers.py:118-125) doesn't rotate/invalidate existing
      sessions → a stolen session survives a reset. Fix: build the link from a server-authoritative host
      (like og_views now does); terminate other sessions on reset. [scout OPS-5e]

### OPS-5e — SECURITY — SHIPPED (the items below are DONE; see Done section)
The OPS-5d scout surfaced these (file:line in scout output; verify first). Several are HIGH.
- [x] **Driver cash-out codes platform-global, no throttle, no tenant scoping (HIGH money/IDOR)** —
      create_cashout_request (accounts/driver_service.py:122-138) mints a 6-digit code unique only
      among PENDING globally; confirm_cashout (141-187) + OwnerDriverCashoutLookupView/ConfirmView
      (menu/views.py:4886-4942) look it up by code across ALL tenants with NO tenant scope and credit
      the CONFIRMING tenant's float while debiting the driver — and neither owner endpoint has a
      throttle. Any waiter can brute-force (1e6, unmetered) another driver's cash-out into their own
      float. Fix: bind the cash-out to the driver's intended tenant (or driver-scans-restaurant),
      throttle the confirm endpoint per-user, and lock the request after N bad attempts (mirror the
      delivery-code lockout DriverJobStatusUpdateView:4869-4883). [scout OPS-5d]
- [x] **MarketplaceOrderStatusView IDOR — full order + financial data to anyone with the order number
      (HIGH)** — accounts/views.py:3566-3655 is AllowAny/auth=[] and only gates delivery_code/can_cancel
      on ownership; the body (items, totals, payment_status, wallet_amount_paid, loyalty, promo,
      scheduled_for) is returned for ANY order to ANY caller. Order numbers are ORD-+token_hex(3) = 24
      bits, only barrier is 300/hr/IP → enumerable harvest of customer order history + financials. Same
      shape on the direct-checkout status path. Fix: require session-customer ownership for the detailed
      body (as cancel/pay already do) OR an unguessable per-order access token issued at placement.
      [scout OPS-5d]
- [x] **OwnerWalletChargeView trusts caller-supplied idempotency_key vs a global non-tenant-scoped
      ledger key (money)** — menu/views.py:9587/9638 reads idempotency_key from the body; debit_wallet
      replays the FIRST WalletTransaction with that key WITHOUT re-checking amount/tenant/customer
      (wallet_service.py:134-136). Because the key namespace is global + attacker-chosen, tenant A can
      pre-insert a row under a guessable key so tenant B's later charge with the same key silently
      replays A's tx (write-suppression / mis-attribution). Also AdminFundTenantView (accounts/views.py
      :1729) + above-threshold WalletChargeRequest.get_or_create (menu/views.py:9605). Fix: server-
      namespace idempotency keys (prefix tenant_id+endpoint) AND assert stored row amount/tenant/customer
      match before returning the replay. [scout OPS-5d]
- [x] **CustomerOrderRateView no ownership check + no throttle (review fraud)** — menu/views.py:7231-7319
      AllowAny, no throttle; "any caller who knows the order number can rate it once". With 24-bit order
      numbers + the public status endpoint confirming COMPLETED orders, an attacker can submit fraudulent
      ratings against competitors. Fix: require session-customer ownership of the order to rate + add a
      per-IP/session throttle. [scout OPS-5d]
- [x] **CustomerPushSubscribeView endpoint-keyed upsert allows subscription hijack (IDOR)** —
      accounts/views.py:1464-1478 update_or_create(endpoint=endpoint, defaults={customer_id:...}) — a
      customer submitting an endpoint already owned by another customer overwrites its customer_id,
      stealing future pushes. Fix: scope uniqueness/update to (customer_id, endpoint) or reject when an
      existing row's customer_id differs. [scout OPS-5d]
- [x] **TranslateView echoes upstream provider raw error body to the client (info disclosure)** —
      tenancy/api.py:379-384 returns the OpenRouter HTTPError body (200 chars) to the tenant editor,
      leaking quota/account/model metadata. Fix: generic 'provider_error' to the client, log the body
      server-side only. [scout OPS-5d minor]
- [x] **OGView reflects request Host (X-Forwarded-Host) into canonical/og:image/cache-key** —
      accounts/og_views.py:103/108/116/161; ALLOWED_HOSTS constrains it but multi-alias hosts can prime
      the Host-keyed cache + bake a non-authoritative host into og:url/og:image. Fix: derive canonical/
      image from the resolved tenant's Domain, normalize the host in the cache key. [scout OPS-5d minor]
- [x] **is_staff in capability FLAGS (not gates)** — accounts/views.py:75 can_access_admin_console +
      :79 all_access still include user.is_staff. The actual admin endpoints are is_staff-free (OPS-5b/
      5d) so this only affects UI-visibility hints, but converge them onto is_superuser/is_platform_admin
      for consistency so a staff-only user isn't shown an admin console that 403s. [grep OPS-5d follow-up]

### OPS-5d — SECURITY — SHIPPED (the items below are DONE; see Done section)
The OPS-5c scout (SaaS-expert lens) surfaced these while we hardened uploads/SSRF/PII.
Several are HIGH. file:line in scout output; verify before acting.
- [x] **Celery `run_management_command` = arbitrary command execution (HIGH)** — accounts/tasks.py
      :100-104 passes any `name` straight to `call_command`; the task is registered by name and the
      default broker (redis://redis:6379/0) has NO auth, so anyone who can LPUSH to Redis can run
      `shell`/`dbshell`/`flush`/`migrate` with full DB creds (the inline-thread fallback runs in the
      web process too). Fix: (1) set Redis `requirepass`/ACL + validate the URL at startup; (2) replace
      the generic task with per-command tasks OR an allowlist of permitted command names. [scout OPS-5c]
- [x] **Google One-Tap auto-links without `email_verified` (account takeover, HIGH)** —
      _verify_google_token (accounts/views.py:299-316) checks aud+sub but NOT the email_verified
      claim, and CustomerGoogleAuthView (548-558) silently links the Google identity to an existing
      phone-registered Customer by email → an unverified-email Google account can take over a Kepoli
      customer. Fix: `if not data.get('email_verified'): return None`. One line. [scout OPS-5c]
- [x] **AdminWalletBonusView bulk-credit double-credit race (money)** — accounts/views.py:1609-1640:
      idempotency `exists()` pre-check and the balance `UPDATE(F+1)` are not atomic; two concurrent
      POSTs with the same idempotency_key both clear the guard and both run the UPDATE (the unique
      idempotency_key only blocks the 2nd ledger insert — balances still inflate). Fix: SELECT FOR
      UPDATE on a sentinel / `cache.add` mutex (campaign-cap pattern), or bulk_create-first then
      UPDATE only on success. [scout OPS-5c]
- [x] **CORS_ALLOWED_ORIGIN_REGEXES default allows `*.localhost:5173` in prod** — settings.py:408-414
      default regex stays active if DJANGO_CORS_ALLOWED_ORIGIN_REGEXES is blank → any localhost:5173
      origin gets credentialed cross-origin access to the prod API. Fix: change in-code default to ''
      and add the var (empty) to coolify.env.example with a comment. [scout OPS-5c]
- [x] **uvicorn `--forwarded-allow-ips='*'` lets DRF throttles read spoofable XFF** —
      docker/entrypoint.sh:41; DRF's SimpleRateThrottle.get_ident() trusts XFF unboundedly, so
      _IPThrottle subclasses (OrderHandoff/CheckoutIntent, menu/throttles.py) can be reset per-request
      by sending `X-Forwarded-For: <random>`. Fix: pin --forwarded-allow-ips to the docker bridge
      subnet OR make _IPThrottle use the trusted-proxy-aware _client_ip helper. [scout OPS-5c]
- [x] **Customer session can be layered onto a staff session (cross-persona fixation)** —
      OTP/email/Google auth write customer_id into the SAME Django session without checking
      request.user.is_authenticated (accounts/views.py:411-418/548/837); a staff/owner can mint a
      customer identity on their privileged session. Fix: refuse the customer_id write when
      request.user is an authenticated staff user; consider a separate customer cookie name. [scout OPS-5c]
- [x] **CustomerReservationsView no throttle + returns cancel_token** — accounts/views.py:711-766 is
      AllowAny, unthrottled, and returns each reservation's cancel_token UUID; a session holder can
      bulk-harvest tokens and learn which restaurants a customer booked. Fix: add a throttle (~60/hr)
      and stop returning cancel_token in the list (cancel via the emailed link). [scout OPS-5c]
- [x] **public_urls.py serves /media/ via Django static_serve in prod** — config/public_urls.py:14-18
      adds django.views.static.serve unconditionally on the non-DEBUG public host: no Cache-Control/
      security headers, holds an fd open, historically traversal-friendly. Nginx already owns /media/
      end-to-end. Fix: remove the route (or guard behind SERVE_MEDIA_FROM_DJANGO). [scout OPS-5c]
- [x] **DJANGO_SUPERADMIN_PASSWORD still passed as `--password` CLI arg** — docker/entrypoint.sh:26-29
      funnels the secret through argv (visible in /proc/<pid>/cmdline, docker inspect, deploy logs)
      even though ensure_platform_admin already prefers PLATFORM_ADMIN_PASSWORD env. Fix: set
      PLATFORM_ADMIN_PASSWORD in entrypoint and drop --password; rename in coolify.env.example.
      [scout OPS-5c] (deploy-config; complements the OPS-5b in-code env path)
- [x] **DJANGO_ADMIN_URL default 'admin/' + hardcoded nginx /admin/ block** — settings.py:675 +
      frontend/nginx.conf:126-138: admin path is discoverable and a two-step env+rebuild to change.
      Fix: add DJANGO_ADMIN_URL to coolify.env.example + envsubst the nginx location so it tracks the
      Django setting. [scout OPS-5c]

### OPS-5c — SECURITY/OPS FOLLOW-UP — SHIPPED (the items below are DONE; see Done section)
- [x] **is_staff STILL bleeds elsewhere? — RESOLVED in OPS-5b** for menu/permissions
      (user_can_edit_tenant/menu), tenancy/api _can_edit_tenant, sales IsTenantEditor (all
      dropped is_staff). If any new gate copies the old triple-check, fix it. [scout OPS-5b → fixed]
- [x] **Image-upload content-type trust (SECURITY)** — _optimize_image except-fallback
      (tenancy/api.py ~127) stores raw bytes with the client-supplied content_type; a JPEG/SVG
      polyglot can be served verbatim. Pillow transcode is the real sanitiser — on fallback,
      reject or force application/octet-stream. Same on driver-doc upload (ride_views.py ~908).
      [scout OPS-5b]
- [x] **AdminRideListView / AdminCarApprovalView: permission_classes=[] + manual check, no
      throttle, no audit on PII GET (SECURITY)** — ride_views.py ~1232/1301; mirror the OPS-5/5b
      pattern (IsPlatformAdmin + AdminPIIThrottle + audit). authentication_classes=[] also drops
      DRF CSRF. [scout OPS-5b]
- [x] **OSRM SSRF** — DELIVERY_OSRM_URL passed verbatim to requests.get (tenancy/routing.py
      ~81/131); validate scheme + non-RFC1918 host (or allowlist) at settings parse. [scout OPS-5b]
- [x] **IsTenantEditor lifecycle scope** — RESOLVED via is_staff drop, but confirm tenant
      LIFECYCLE endpoints (suspend/cancel) use IsPlatformAdmin not IsTenantEditor. [scout OPS-5b]
- [x] **DriverDocUploadView no throttle** — AllowAny 8MB uploads + admin-email on each; add a
      per-session throttle (ride_views.py ~945). [scout OPS-5b]
- [x] **AnalyticsEventIngestView throttle IP-scoped** — CDN/shared-NAT collapses the 600/hr
      bucket; key on (tenant, ip) like WaiterCallThrottle. (menu/views.py ~1047). [scout OPS-5b]
- [x] **PasswordResetToken / ActivationToken never pruned** — add a prune cron (delete used
      >7d). (accounts/models.py ~514). [scout OPS-5b]
- [x] **TRUSTED_PROXY_COUNT not declared in settings.py** — read via getattr default 1 in 2
      places; declare it explicitly + comment the Coolify topology (Traefik+nginx may be 2).
      Also: get_request_ip miscount fallback returns spoofable XFF[0] — clamp safely.
      (middleware.py ~137; sales/audit.py ~29). [scout OPS-5b + review minor]
- [x] **SESSION_SAVE_EVERY_REQUEST not set** — 90-day window is ABSOLUTE not sliding; read-heavy
      staff get logged out mid-shift. One line: SESSION_SAVE_EVERY_REQUEST=True. [scout OPS-5b]
- [x] **AdminWalletBonus balance_after stale-read** under concurrent wallet writes (documented
      limitation; per-customer credit_wallet or returning-UPDATE for exactness). [review OPS-5b minor]
- [x] **Plan-limit returns HTTP 400 not 402** — still deferred; SPA axios behavior unaudited.
      [review OPS-5/5b minor]

### OPS-5b — ADMIN SECURITY HARDENING — SHIPPED (the items below are DONE; see Done section)
- [x] **IsPlatformAdmin admits any Django is_staff user → money endpoints (PRIV-ESC, HIGH)**
      — sales/permissions.py:11 returns True for is_staff, so any /admin/-capable Django
      user can POST wallet bonus / fund-tenant / vouchers / ride-fare settings. Intended
      gate is is_platform_admin (role PLATFORM_SUPERADMIN). Fix: drop is_staff from
      IsPlatformAdmin (keep is_platform_admin + is_superuser). One line, but audit every
      admin view that relied on it. [scout OPS-5]
- [x] **Admin auth pattern triplication** — 15+ admin views use 3 inconsistent gates
      (IsPlatformAdmin class / inline is_platform_admin / inline that also admits is_staff).
      Consolidate on IsPlatformAdmin (after the fix above) + add a test that every
      /api/admin/ URL rejects a TENANT_OWNER. [scout OPS-5]
- [x] **AdminCustomerList/Detail: full PII directory, no throttle, no read-audit, is_staff
      gate** — accounts/views.py:1687/1744. Add per-admin throttle + log_admin_action on
      GET + IsPlatformAdmin. SECURITY/compliance. [scout OPS-5]
- [x] **Missing audit on admin writes** — is_driver toggle (accounts/views.py:1813), manual
      delivery-job create (5858/5909) have no log_admin_action; tenant deletion request
      (tenancy/api.py:437, GDPR) has no audit + no TENANT_DELETION_REQUESTED action. Add
      actions + log calls. [scout OPS-5]
- [x] **plan_feature_flags_updated logged as raw string not in Actions enum** — invisible to
      audit queries filtering Actions.choices. Add the enum member. (sales/views.py:1435).
      [scout OPS-5]
- [x] **Audit-log IP spoofable** — get_request_ip takes XFF[0] (client-controlled), no
      trusted-proxy config. Use rightmost-trusted / django-ipware. (sales/audit.py:10;
      middleware.py:128). [scout OPS-5]
- [x] **AdminWalletBonus bulk-credit leaves balance_after=NULL** — breaks ledger
      reconstruction; per-customer credit_wallet or a returning-UPDATE. (accounts/views.py
      :1512). [scout OPS-5]
- [x] **Dish/staff plan-limit is a read-then-create RACE** — concurrent creates overshoot
      the cap (no lock). select_for_update sentinel or DB constraint. (menu/views.py:587;
      accounts/views.py:1014). [scout OPS-5]
- [x] **ensure_platform_admin password as CLI arg** — visible in /proc + shell history +
      deploy logs. Read from env/stdin. (commands/ensure_platform_admin.py:9). [scout OPS-5]
- [x] **Health endpoint leaks MEDIA_ROOT absolute path** to unauthenticated callers — return
      'ok' not str(path). (config/api.py:171). [review OPS-5 minor]
- [x] **Plan-limit returns HTTP 400 not 402** — contract said 402/403 for entitlement
      boundary; clients may mis-classify. (menu/views.py:602; accounts/views.py:1019).
      [review OPS-5 minor]

### Earlier scout notes
- [x] **Section assignment accepts any user_id (no tenant-membership check)** — RESOLVED in
      OPS-5 (menu/views.py:7432 whitelist filter(id__in, tenant)). [scout OPS-1 → fixed OPS-5]
- [x] **CustomerOrderConsumer accepts any order_number (enumeration)** — RESOLVED in OPS-5
      (realtime/consumers.py _check_order_ownership: session/delivery_code gate; anonymous
      residual risk documented). [scout OPS-1 → fixed OPS-5]
- [x] **Plan limits unenforced on write** — Plan.max_dishes / max_staff_accounts checked
      only by the periodic enforce_subscriptions sweep, not at DishViewSet.create /
      StaffCreateView. A tenant can exceed plan caps until the sweep runs. Monetization
      boundary. (tenancy/models.py:12). → OPS-5 (billing ops). [scout OPS-1]
      DONE (verified code-read): DishViewSet.perform_create (menu/views.py:594) and
      OwnerStaffCreateView (accounts/views.py:1256) both enforce limits inside
      transaction.atomic() + select_for_update() to prevent TOCTOU race. Tests cover both.
- [ ] **_can_access_order = 3 serial queries inside select_for_update** — held row lock
      spans the section-resolution queries on every staff mutation; lock-queue at rush.
      Cache section assignment per-request or single combined query. (menu/views.py:3160).
      → OPS-4 (scale). [scout OPS-1]
- [x] **Section-access logic copy-pasted 3×** — StaffOrderListView inline, _can_access_order,
      waiter_views._section_slugs_for all reimplement (my_slugs, claimed_slugs) differently;
      a future section-semantics change will miss one. Extract one helper. (menu/views.py
      :3160/:3268; waiter_views.py:85). → fold into whichever OPS batch next touches sections.
      [scout OPS-1]
      SHIPPED 3d17795 — _can_access_order + StaffOrderListView now call waiter_views._section_slugs_for.
- [x] **WaiterCall throttle is per-IP** — DONE: WaiterCallThrottle (throttles.py) scoped per
      (tenant-schema + table_slug), not per IP. [scout OPS-1 → fixed OPS-3]
- [x] **StaffMessage unbounded + no created_at index** — DONE: created_at has db_index=True
      (menu/models.py:359); prune_staff_messages in MANAGEMENT_COMMAND_ALLOWLIST. [scout OPS-1 → fixed OPS-4]
- [~] **StaffShiftSummaryView materializes orders in Python for avg prep** — RESOLVED in
      OPS-2 (ExpressionWrapper+Avg single query; currency folded into a values_list scan).
      [scout OPS-1 → fixed OPS-2]
- [x] **Order.table_slug vs table_label dual keys** — FIXED: TableLinkSerializer.update()
      now pops the slug from validated_data so slug is immutable after creation. Label can still
      change freely; QR codes and historical order routing are unaffected. (menu/serializers.py:828).
      [scout OPS-1]
- [x] **revenue.py STILL materializes ledger_order_ids as a Python set** — DONE (verified
      code-read): revenue.py uses `orders_values_qs = order_qs.values("id")` + subquery
      `ledger_order_ids_sq = ledger_qs.values("order_id")` — no Python set materialization.
      [scout OPS-2 → fixed OPS-4]
- [x] **Order.paid_at unindexed** — DONE: `order_status_paid_at_idx` composite index on
      (status, paid_at) exists in menu/models.py Order.Meta.indexes. [scout OPS-2 → fixed OPS-4]
- [ ] **Marketplace commission mixed-basis** — commission = food_subtotal × 0.10 (PRE-discount
      GMV) but the statement reports revenue as Sum(Order.total) (POST-discount), so net_payout
      makes the effective take-rate look >10% whenever a discount applies. Document the basis
      OR apply the rate to post-discount food. No config governs it. (accounts/views.py:3020;
      menu/views.py:7391). → OPS-5 (billing). [scout OPS-2]
- [x] **Commission rate hardcoded 0.10, no per-tenant override, no rate snapshot on Order** —
      can't offer a negotiated/promo rate without a code change for ALL tenants, and historical
      orders can't be re-audited (no rate_applied column). (accounts/views.py:3020;
      models.py:452). → OPS-5 (billing). [scout OPS-2]
      DONE (verified code-read): Profile.marketplace_commission_pct (tenancy/models.py:434, default 0.10)
      + Order.commission_rate_applied (menu/models.py:465) snapshotted at checkout; statement exposes it per row.
- [x] **Commission statement buckets by UTC month** — DONE (verified code-read): view now
      builds [month_start, next_month_start) range in the tenant timezone (ZoneInfo) and filters
      created_at__gte/__lt on it (menu/views.py:8067-8083 with comment "A5"). [scout OPS-2]
- [ ] **legacy split cash = total − wallet silently clamped at 0** — if a tip is added after a
      wallet settle, legacy_cash can go negative and max(0) hides it, so cash+wallet no longer
      reconciles to gross. A pro ledger should assert reconciliation, not clamp. (revenue.py
      :63/77). → OPS-4 (reconciliation assertions). [scout OPS-2]
- [x] **OrderItem has no voided_by_user_id** — DONE (5b7e013): added IntegerField null/blank;
      migration 0061; StaffVoidOrderItemView stamps it; Z-report/CSV now exposes it. [scout OPS-2]
- [x] **Order CSV "subtotal" column includes tip + nets discounts** — DONE: subtotal now
      = total − delivery_fee − tip_amount (pure food net after discounts); commission_amount
      column added to CSV export. (menu/views.py OwnerOrderExportView). [scout OPS-2]
- [x] **Z-report voids loop + dashboard/CSV N+1** — voids loop materializes items with a
      select_related('order') join per row (use annotate + DB Sum for the total); OwnerOrderExport
      iterates order.items.all() twice + payments per row without prefetch. Perf at scale.
      (menu/views.py:6388/6184). → OPS-4. [scout OPS-2 + review-major]
      DONE (verified code-read): OwnerOrderExportView at line 6705 uses prefetch_related("items","payments");
      loop iterates items/payments once from prefetch cache. Z-report voids uses select_related("order")
      (single JOIN query); voids_total is in-Python but voids are <20/day so marginal.
- [x] **Dashboard SPA still shows gross wallet_revenue/cash_revenue, not payment_split** —
      DONE (defec65): OwnerDashboardRevenue.vue now shows payment_split (drawer-accurate) when
      available and falls back to gross cash/wallet split for pre-ledger data. [review OPS-2]

- [x] **Promotion max_uses overspend race (REVENUE LEAK)** — DONE (verified code-read):
      PlaceOrderView uses `filter(pk=.., use_count__lt=max_uses).update(use_count=F+1)` (atomic
      single-op); marketplace path mirrors it. [scout OPS-3 → fixed OPS-4]
- [x] **PlaceOrderThrottle still IP-scoped** — DONE: throttles.py PlaceOrderThrottle is
      "OPS-4 G: per-user for authenticated staff/owner, IP for anonymous customers". [scout OPS-3 → fixed OPS-4]
- [ ] **Status-advance idempotency_key sent but not consumed server-side** — client sends it
      on the status PATCH; OwnerOrderStatusUpdateView never reads it. The target-idempotency
      BFS ("already_advanced" 200) covers the stale-superseded-retry case (verified), so this
      is belt-and-suspenders, not a correctness gap. Optional: cache (key→status) inside the
      atomic for true at-least-once. LOW. (menu/views.py:5890). [scout OPS-3]
- [x] **Offline queue drop-policy + no TTL** — DONE (5b7e013): _loadQueue() in waiter.js now
      drops entries where queuedAt is present and older than 8 h on load (backwards-compat:
      entries without queuedAt are kept). [scout OPS-3]
- [x] **WalletTransaction refund idempotency/aggregate scans unindexed (tenant_id,type,...)** —
      DONE: composite index (tenant_id, type, created_at) exists in accounts/models.py
      WalletTransaction.Meta.indexes. [scout OPS-3 → fixed OPS-4]
- [x] **StaffOrderPaymentView cache.set after atomic block** — DONE (c0f9483): added doc comment
      to menu/views.py:4972 stating the DB OrderPayment.idempotency_key UNIQUE constraint is the
      PRIMARY backstop and must not be dropped; cache.set is intentionally post-commit. [scout OPS-3]

- [ ] **customer_phone btree index is dead for icontains search** — OPS-4 added a plain
      btree on Order.customer_phone but the two search paths use `customer_phone__icontains`
      (LIKE '%..%'), which a btree can't serve; only the exact-match CRM/win-back paths
      benefit. Fix: pg_trgm GIN trigram index, OR rewrite search to digits[-9:] exact-match
      (CustomerOrdersByPhoneView already does this at menu/views.py:3184). (migration 0058).
      → OPS-4 follow-up / search-perf. [scout OPS-4]
- [x] **OrderItem.voided_at unindexed — Z-report full-scans items every shift close** — DONE
      (commit 57c5482): migration 0060 adds partial Index(voided_at) WHERE is_voided=True.
- [x] **DirectoryView/MarketplaceView N+1 cross-schema** — per-tenant schema switch + rating
      aggregate + promo scan inside the serialization loop (100+ cross-schema queries/cold
      request; 90s cache is a bandage). Denormalize Profile.rating_avg/rating_count via
      post_save signal/cron. (accounts/views.py:2243/2418). → marketplace-perf batch. [scout OPS-4]
      DONE (verified code-read): B8 shipped rating denorm (Profile.rating_avg/rating_count via signal);
      B8-followup + promo-N+1 batches killed the promo N+1 (marketplace_promos denorm + in-memory eval).
      Listing loop is fully query-free (comments at accounts/views.py:2967/3215 confirm). [scout OPS-4]
- [x] **OwnerRatingListView no pagination** — DONE (commit 57c5482): proper page/page_size
      pagination (default 50, max 200) + ?from/?to date filters; has_more signal; CSV uncapped.
- [x] **CustomerRating (public) no retention prune** — DONE: prune_customer_ratings command
      (default 365 days) + added to MANAGEMENT_COMMAND_ALLOWLIST. [scout OPS-4]
- [x] **OwnerCustomerListView still materializes all customers before paginating** — DONE:
      segment parsed early; `_seg_having` dict pushed to DB as HAVING clause on `order_count` /
      `last_order_at` annotations for `new`/`at_risk`/`returning`; `all` unchanged. [scout OPS-4]
- [x] **Z-report by_staff = 2 OrderPayment queries** — DONE: collapsed to one .values()
      .annotate(cash_sum=Sum(filter=CASH), wallet_sum=Sum(filter=WALLET), order_count=Count(distinct)).
- [x] **_staff_order_payload calls order.items.all() twice** — DONE: materialized once
      (_items = list(order.items.all())) used for both items_count and items list.
- [x] **OwnerOrderExport 5000-row hard cap, silent truncation** — DONE (commit 57c5482):
      X-Kepoli-Export-Total and X-Kepoli-Export-Truncated headers added.

### B8-FOLLOWUP — MARKETPLACE SCALE + DENORM COHERENCE (scout B8 cluster)
B8 killed the RATING cross-schema N+1, but the scout found the loop isn't fully query-free + the denorm has
coherence gaps. None biting at current scale; do before many tenants / heavy marketplace traffic.
- [x] **Promo-badge N+1 — DONE (promo denorm)** — Profile.marketplace_promos (tenancy/0043) holds the
      tenant's is_active promo SCHEDULES, refreshed by a menu.Promotion signal + backfill_profile_promos +
      list-cache bust; the marketplace loop evaluates the window IN-MEMORY at request time
      (_promo_badge_from_denorm). Both public listing loops are now fully query-free (scout-confirmed).

### MARKETPLACE DENORM COHERENCE (scout promo-N+1 cluster) — MOSTLY SHIPPED (denorm-coherence batch)
- [x] **Capped-promo badge drift — DONE (denorm-coherence batch)** — recompute_tenant_promos now excludes
      capped promos (Q(max_uses__isnull=True) | Q(use_count__lt=F("max_uses")) — keeps unlimited+uncapped,
      drops capped), AND the checkout cap-strip (menu/views.py:2606) refresh_from_db's the post-increment
      use_count and calls recompute_tenant_promos ONLY when the redemption actually crosses the cap (gated so
      the common below-cap order doesn't do cross-schema work + a global list-cache bust; concurrency-safe vs
      the stale in-memory use_count). (menu/promos_denorm.py:73; menu/views.py:2606). [scout promo-N+1]
- [x] **Consolidate the duplicated _is_promo_active_now + tz mismatch — DONE (denorm-coherence batch)** — ONE
      shared rule now lives in menu/promos.py (promo_is_active(promo, *, now_local), stdlib-only, reads model
      OR denorm-dict); both _is_promo_active_now copies are thin wrappers delegating to it. The
      today=date.today()/utcnow() mismatch is fixed: the whole window (date bounds + weekday + HH:MM) derives
      from ONE tenant-local now_local. Checkout (menu/views.py) + badge (accounts/views.py) pass
      _profile_now(profile); promo windows now evaluate in TENANT-LOCAL time (correct for "Tue 14:00–16:00").
      Parametrized model-vs-dict + tz tests. (menu/promos.py; menu/views.py:1863; accounts/views.py:2559). [scout promo-N+1]
- [x] **Flash-sale cache coherence (bust-on-write half) — DONE (denorm-coherence batch)** —
      _bust_public_list_cache() now fires on every flash-sale mutation (AdminFlashSaleListCreateView.post,
      AdminFlashSaleDetailView.patch/.delete, OwnerFlashSaleOptInView.post[created]/.delete), best-effort, so
      a new/edited/ended/opted flash sale shows in the listing immediately instead of after the 90s TTL.
      (accounts/views.py). [scout promo-N+1] (the "live-eval vs baked-into-cache" half → LIST-CACHE COHERENCE
      cluster below, note "time-windowed badge/flash baked into cache")
- [ ] **Marketplace composite index for the full WHERE shape** — the hot query filters
      (directory_opt_in, is_menu_published, tenant__lifecycle_status) + optional city/cuisine/price_tier +
      order_by tenant__name; the existing indexes don't fully cover it. Consider an index matching the actual
      shape. (tenancy/models.py Profile.Meta). [scout promo-N+1] (marginal at current scale)
- [x] **90s list cache busted on rating change — DONE (B8-followup scale)** — _public_list_cache_key now
      embeds a GLOBAL version (public_list_ver); _bust_public_list_cache() (mirrors _bust_menu_cache) is
      called from recompute_tenant_rating after the Profile update, so a new rating refreshes the directory/
      marketplace listing immediately. (accounts/views.py; menu/ratings.py). NOTE: opt-in/out + publish
      toggles also change the listing and could bump the same version — small follow-up if wanted.
- [x] **min_rating index — DONE (B8-followup scale)** — composite profile_marketplace_rate_idx
      (directory_opt_in, is_menu_published, rating_avg) on Profile.Meta (tenancy/0042) backs the B8
      min_rating SQL filter.
- [~] **Denorm drift** — the owner-reply unnecessary-recompute half is FIXED (effd9f3+: the Rating post_save
      handler now early-returns when update_fields excludes 'score', so owner-reply saves skip the cross-schema
      recompute). RESIDUAL: out-of-ORM writes (admin bulk-edit / .update(score=) / raw SQL / DB restore) still
      bypass the signal → run the already-built backfill_profile_ratings command after any such change (note in
      a restore runbook). (menu/signals.py). [scout B8 — partially done]

### LIST-CACHE / DENORM COHERENCE (scout denorm-coherence cluster) — MOSTLY SHIPPED (list-cache-coherence batch)
The public marketplace/directory response is cached 90s keyed by a GLOBAL version; only rating + promo +
flash-sale writes currently bust it. Other writes change which rows/fields the listing shows but do NOT bust
the cache, and two readers derive the same field differently:
- [x] **Profile listing-field edits don't bust the list cache — DONE (list-cache-coherence batch)** —
      ProfileView.perform_update now bumps _bust_public_list_cache when set(validated_data) intersects a new
      LISTING_RELEVANT_FIELDS frozenset (tenancy/api.py; lazy import, best-effort), so an owner toggling
      directory_opt_in OFF or editing city/cuisine/delivery/tags/hours/business_type/logo/tagline refreshes
      the marketplace + directory immediately. An unrelated settings save does NOT bust.
- [x] **Tenant lifecycle_status changes don't bust the list cache — DONE (list-cache-coherence batch)** —
      the sales admin lifecycle toggle (AdminTenantLifecycleView, all 3 branches after save) and
      enforce_subscriptions (ONCE per --apply run if any suspend/reactivate) now bust the list cache, so a
      suspended-for-nonpayment tenant drops out of the listing immediately and a reactivated one reappears.
- [x] **Directory vs Marketplace disagree on is_open — DONE (list-cache-coherence batch)** — DirectoryView
      now uses _compute_is_open_now(profile) (was raw profile.is_open), matching MarketplaceView + the menu
      page; AND _compute_is_open_now's schedule eval was fixed from utcnow() to TENANT-LOCAL
      (profile.timezone → settings.TIME_ZONE → UTC) — same two-clock bug class as the promo fix.
- [x] **AdminTenantDeliveryView 500 + delivery-fee not busted — DONE (list-cache-coherence batch)** — scout
      caught it: the view did update_fields.append("updated_at") but Profile has NO updated_at field →
      save() raised ValueError → 500 on EVERY admin delivery edit (masked by a save=Mock() test). Removed the
      bogus append + added the list-cache bust (delivery_fee/delivery_minimum_order are listing-serialized).
- [x] **Menu template-apply business_type not busted — DONE (list-cache-coherence batch)** — ApplyTemplateView
      writes profile.business_type (listing-relevant) but bypassed ProfileView's bust; now busts the list cache
      after the profile save (menu/views.py). [scout list-cache-coherence]
- [x] **OPEN-STATE derivation consolidated (backend) — DONE (open-state-consolidation batch)** — NEW
      tenancy/openstate.py = the SINGLE window rule: schedule_open_now(schedule, now_local) (tri-state) +
      tenant_local_now(profile) (profile tz→settings.TIME_ZONE→UTC). All THREE backend derivations now delegate:
      menu/views.py _schedule_open, accounts/views.py _compute_is_open_now, tenancy/serializers.py
      get_is_open_now. **get_is_open_now's utcnow() bug is FIXED (now tenant-local)** + it gained the
      is_menu_temporarily_disabled guard so the menu page agrees with the listing card. Callers differ ONLY in
      extra guards (listings=temp_disable; menu-page=temp_disable+ClosureDate; order-gate=neither, a 503 blocks).
      Reviewer ran a 1071-case differential (0 mismatches vs the old rule). New test_openstate.py + rewritten
      test_profile_is_open_now.py. [scout list-cache-coherence]

### FRONTEND OPEN-STATE COHERENCE (scout open-state cluster) — DISPLAY VERDICT SHIPPED (frontend-open-state batch)
The backend ships an authoritative `is_open_now`; the frontend re-derived open/closed 4-5 ways. SHIPPED: ONE
shared isRestaurantOpenNow(profile) helper (businessHours.js) consuming is_open_now (graceful fallback to the
old client logic when absent); the storefront DISPLAY verdicts now delegate to it. ROUND 2 remains below.
- [x] **MenuSelect / Cart / CustomerLeadPage (+ Menu) display verdict — DONE (frontend-open-state batch)** — all
      consume isRestaurantOpenNow (is_open_now-first); the cross-tz bug + the Menu-vs-MenuSelect disagreement are
      fixed wherever is_open_now flows. New businessHours.test.js (9 cases). isCurrentlyOpenBySchedule kept as the
      absent-is_open_now fallback + label helper only. [scout open-state]
- [x] **Marketplace / Directory / MarketplaceMenuPage — NON-GAP (verified by scout)** — their raw-looking is_open
      is ALREADY the server-computed verdict (_compute_is_open_now, accounts/views.py:2666/2819/3088); do NOT waste
      a change "repointing" them to isRestaurantOpenNow (the list payload has no is_open_now field). [scout frontend-open-state]
- [x] **CustomerLayout storefront banner — DONE (frontend-open-state-followup)** — CustomerLayout.vue tenantNotice
      closed branch now tests `!isRestaurantOpenNow(profile)` (was raw `profile.is_open === false`), so the
      storefront-wide closed banner (renders on EVERY customer route, role=status; the de-facto closed indicator on
      CategoryPage which has no header) agrees with the Menu/MenuSelect/Cart headers. temp-disable still handled by
      its own branch above. Frontend gates green. [scout frontend-open-state]
- [x] **Add-to-cart→checkout-409 DEAD-END — DONE (frontend-closed-deadend batch, the owner's chosen item)** —
      new businessHours.js helpers canAddToCartNow / canPlaceImmediateOrderNow / classifyClosedOrderState
      (open|blocked|schedule) mirror the backend order gate on the SAME verdict (isRestaurantOpenNow). CategoryPage
      + DishPage now block dine-in (table-context) add-to-cart when closed-now (no order-ahead escape) while leaving
      pickup/delivery addable; Cart.vue disables immediate Place Order when closed-now + steers pickup/delivery to
      "Schedule for later" (dine-in shows a can't-order notice), and validateForm blocks the immediate-409 path.
      **Order-ahead PRESERVED: a scheduled pickup/delivery order (isScheduledOrder) classifies "open" and still
      places when closed-now.** 3 new i18n keys EN/FR/AR. **NOTE: the workflow DIED mid-run (5h, 0-byte output)
      after the impl wrote the files; I reviewed the on-disk changes myself (scope guard held — only dine-in newly
      blocked, no over-blocking) + ran the gates: verify:i18n + lint clean, 119 tests, build OK.** Frontend gates green.
      [scout frontend-open-state]
- [x] **Menu / MenuSelect "opens at" label regression — DONE (label-regression fix)** — re-added the
      getNextOpenInfo "Opens at {day} {time}" enrichment to the closed branch of Menu.vue + MenuSelect.vue
      statusLabel (MenuSelect also regained the currentLocale destructure), mirroring CustomerLeadPage. Reuses the
      existing menu.opensAt / menu.tomorrow keys (no new i18n). Frontend gates green (lint, 119 tests, i18n, build).
      [reviewer minor]
- [ ] **useSeoMeta.js openingHoursSpecification is a 5th independent schedule parser** — useSeoMeta.js:222-240
      emits JSON-LD opening hours verbatim with no shared contract with businessHours.js / openstate; lower
      severity (publishes raw weekly hours, can't drift on the clock) but must be hand-synced if the schedule
      shape evolves. [scout open-state] (marginal)
- [x] **Time-windowed is_open/promo_badge/flash baked into the 90s cache — DONE (marketplace-live-fields batch)** —
      DirectoryView + MarketplaceView now cache the EXPENSIVE work (SQL + per-tenant assembly) but recompute the
      time-sensitive verdicts (is_open, +promo_badge/flash_sale_active for marketplace) on EVERY request from raw
      inputs carried in the cached payload, via _refresh_marketplace_live_fields (deepcopy → no cache mutation;
      pure in-memory → no cache-hit DB; internal _raw_* keys stripped from the response). Reuses the single-source
      helpers (openstate.schedule_open_now / _promo_badge_from_denorm / is_live mirror). **Scout caught two
      follow-on bugs I fixed in the same batch: the recompute made is_open fresh but the ?open=1 FILTER + open-first
      SORT were still frozen → a now-closed row could sit inside an "open only" list (self-contradictory) or keep a
      top slot; the refresh pass now re-applies both on the fresh verdict** (open_only filter + open-first sort,
      threaded from the view; distance-sorted requests skip the re-sort). New RefreshLiveFieldsTests (7).
      Backend 3866/0. (accounts/views.py). [scout denorm-coherence + scout marketplace-live-fields]
- [x] **/api/meta/ is_open_now recomputed post-cache — DONE (meta-live-isopen batch)** — TenantMetaView now
      caches the serializer payload WITH internal _isopen_raw inputs and recomputes profile.is_open_now on every
      request (cache hit + fresh) via _refresh_meta_is_open_now (deepcopy → no cache mutation; no cache-hit DB —
      closure_today cached day-stable; _isopen_raw stripped from the response). Mirrors the marketplace recompute +
      reuses openstate.schedule_open_now (serializer get_is_open_now already delegates to it). So the menu/meta page
      agrees with the marketplace card. **ALSO (scout-caught, fixed same batch): ClosureDate create/delete busted NO
      cache + the recompute freezes closure_today → a same-day closure stayed invisible for ≤300s. Fixed:
      OwnerClosureDateListCreateView.post + OwnerClosureDateDeleteView.delete now _bust_tenant_meta_cache (new
      menu/views.py _bust_meta_cache_for_request helper).** New MetaIsOpenNowRecompute + integration tests + 2
      closure-bust tests. Backend 3878/0. (tenancy/api.py; menu/views.py). [scout marketplace-live-fields]
- [ ] **Marketplace/Directory listings ignore ClosureDate entirely (design gap)** — DirectoryView/MarketplaceView
      never read ClosureDate (it lives in the tenant schema; the listing runs in the public schema), so a tenant
      closed for a holiday still shows is_open=true on the marketplace card even though its menu page + order gate
      honor the closure. Closing this needs denormalizing "closed today" into the public Profile (like ratings/promos)
      — deferred; low frequency (whole-day holiday closures). (accounts/views.py). [scout meta-live-isopen]
- [ ] **Menu list cache bakes in happy-hour effective_price + ends_at (60s TTL, same class)** — menu/views.py:425
      caches the menu list 60s; DishSerializer.get_effective_price / get_happy_hour are clock-derived (from
      get_active_happy_hours(now_local) at build) and the version key bumps only on CMS writes, so a happy hour that
      opens/closes mid-window shows the wrong price for ≤60s. Same recompute-post-cache class as is_open; lower
      severity (60s, pre-launch). Fix = recompute effective_price/happy_hour post-cache or document the 60s drift.
      (menu/views.py:425; menu/serializers.py:330). [scout meta-live-isopen]
- [x] **Promo-badge fill-time tz fallback forks from the recompute fallback** — DONE: MarketplaceView fill
      loop now calls tenant_local_now(profile) (the canonical chain: timezone → settings.TIME_ZONE → UTC)
      instead of inlining ZoneInfo(profile.timezone or "UTC"). Fill and recompute clocks are now identical.
      (accounts/views.py:3228). [scout marketplace-live-fields]
- [x] **Recompute/bust on EVERY bounded-promo redemption — DONE (denorm-coherence batch)** — the checkout
      cap-strip now refresh_from_db's the post-increment use_count and only recompute_tenant_promos (which
      busts the GLOBAL list cache) when the redemption crosses the cap, not on every below-cap order.
      (menu/views.py:2606). [scout denorm-coherence + reviewer minor]

### OPS-6c-FOLLOWUP — A11Y — SHIPPED (route-focus + duplicate-main + breadcrumb + standalone-routes all DONE)
- [x] **Standalone routes skip-link / focusable <main> — DONE (a11y-standalone-routes batch)** — new
      frontend/src/layouts/PlainLayout.vue (chrome-less layout = skip-link + <main id="main-content" tabindex="-1">,
      reusing common.skipToMain) now wraps every no-layout route via the router parent-route mechanism: /signin,
      /waiter/join, /forgot-password, /reset-password, /unauthorized, /activate, the 8 /admin-* pages, and the 404.
      The 4 pages that shipped their own <main> (Activate/ResetPassword/Unauthorized/NotFound) had it demoted to
      <div> so each rendered page has exactly ONE main (focusGuard now lands there). **Scout-caught + folded in:
      ErrorBoundary's error fallback had NO main/skip target either (the one remaining instance) → wrapped it in
      <main id="main-content" tabindex="-1"> + focus-on-error (an error isn't a route nav, so focusGuard can't fire).**
      New PlainLayout.test.js (4) + ErrorBoundary.test.js; removed 2 now-orphaned heading ids (NotFound/Unauthorized).
      Frontend gates green (lint, 124 tests, i18n, build). [scout OPS-6c-followup]

### FRONTEND CACHE/DRY — DEFERRED (assessed, low value; documented rather than refactored)
- [ ] **Menu list cache bakes happy-hour effective_price/ends_at (60s) — DEFER (cosmetic)** — same recompute-
      post-cache class as is_open, BUT checkout is LIVE-priced (menu/pricing.py applies happy-hour at order time on
      all 3 placement paths), so the 60s menu-list display lag never mis-charges — it's cosmetic. Recompute-post-cache
      would touch the nested menu hot path for ~zero money impact; NOT worth the risk pre-launch. Accept the 60s drift
      (or shorten the menu TTL) if it ever matters. (menu/views.py:425; menu/serializers.py:330). [scout meta-live-isopen]
- [ ] **useSeoMeta.js openingHoursSpecification is a 5th schedule parser — DEFER (not a bug)** — emits correct RAW
      weekly hours (no clock-drift), just doesn't share the openstate/businessHours contract. Pure DRY; refactoring
      structured-data carries its own risk for zero user-facing gain. Consolidate only if the schedule shape evolves.
      (useSeoMeta.js:222). [scout open-state] (marginal)

### EMAIL-PROGRAM HARDENING — REQUIRED BEFORE SENDING MARKETING EMAIL AT SCALE (scout B1 cluster)
B1 added email to win-back + campaigns (reaches the email-having majority). Before this sends real
marketing mail to real customers, the deliverability/compliance basics must be in place — the app is not
live yet so none of this is actively harming, but it gates turning the email program on for real.
- [x] **One-click unsubscribe — DONE (B1-followup, see Done section)** — send_marketing_email now sends via
      EmailMessage with RFC 8058 List-Unsubscribe (https + mailto) + List-Unsubscribe-Post one-click headers
      + a visible body link; a public CSRF-exempt/no-auth tokenized endpoint (Django signing, no model field)
      sets notify_promotions=False. The 406-in-prod content-negotiation trap was caught + fixed.
- [x] **Sending to UNVERIFIED emails (email_verified exists but is never checked)** — both audiences select
      .exclude(email='') and ignore Customer.email_verified, so mistyped/stale addresses get blasted → hard
      bounces → shared-domain blocklisting that also kills transactional mail (OTP/reset/order-status). Gate
      the email audiences on email_verified=True (or a syntactic+MX precheck); verify email at capture.
      NOTE: verified-only TRADES reach for deliverability — decide alongside this cluster. (email_verified
      accounts/models.py:16; send_winback_nudges.py audience; menu/views.py:10461-10469). [scout B1]
      SHIPPED 3079e27 — email_verified=True added to winback audience, promo campaign audience, and
      per-customer campaign_email guard (accounts/push.py send_campaign_email_sync).
- [ ] **No bounce / spam-complaint feedback loop / suppression list** — record_notification logs only SMTP
      handoff; nothing ingests async bounces/FBL complaints or suppresses a dead/complaining address, so the
      same address is retried every campaign + every 90-day winback cycle. Add a CustomerEmailSuppression
      model fed by an ESP webhook + check it in every audience query. (needs the owner's ESP/webhook).
      [scout B1]
- [ ] **notify_promotions is a single GLOBAL cross-tenant opt-out** — one BooleanField on the shared
      Customer gates promos from ALL tenants; unsubscribing from one restaurant silently kills (or re-floods)
      every restaurant's promos. Consider per-(customer,tenant) opt-out for marketplace customers.
      (accounts/models.py notify_promotions; both audiences). [scout B1]

### COMMISSION LEDGER / REVENUE-RECOGNITION REDESIGN (scout A5-followup cluster)
The A5/A5-followup scouts keep surfacing deeper statement issues → the commission statement should become a
proper IMMUTABLE INVOICE LEDGER computed on a COLLECTED basis, with food+delivery commission unified. NOT
live-critical yet (marketplace is PSP-blocked, statement bills no real money), and #4 carries an OWNER policy
decision — do this as one design pass BEFORE marketplace billing goes live, not more incremental patches.
- [ ] **Statement not point-in-time immutable** — it recomputes from live mutable order state every fetch
      (filters by current status; void mutates commission_amount in place with no history). A later cancel/
      void of a prior-month order silently rewrites that month's already-"invoiced" total. Add an immutable
      monthly invoice snapshot (billed_at + frozen line/total rows) once issued. (menu/views.py:7984-7993;
      4305). [scout A5-followup] **(the core redesign)**
- [ ] **COD / unpaid orders billed commission before cash is collected** — statement has no payment_status
      filter, so an UNPAID COD order (A4) in a live status is billed commission at placement; a COD no-show
      that never reaches a terminal status is billed indefinitely. Move to a COLLECTED/PAID basis (accrue
      commission against collected revenue). NOTE: collected-vs-placement basis is an OWNER policy decision.
      (menu/views.py:7984-7993; accounts/views.py:3496-3515). [scout A5-followup]
- [x] **Delivery commission not reversed on cancel/void (asymmetry)** — A5-followup reversed FOOD commission
      but DeliveryJob.platform_commission (snapshotted at placement) is never reversed on cancel/refund, so a
      refunded delivery order keeps a stale platform_commission. Mirror the food reversal for delivery.
      (accounts/views.py:3833-3835; accounts/models.py:735-737; menu/views.py:5078-5085). [scout A5-followup]
      SHIPPED 3d2a5d1 — cancel_delivery_job_for_order zeroes platform_commission on save.
- [x] **net_payout counts the delivery_fee as restaurant revenue** — DONE: net_payout now subtracts
      delivery_fee from every per-row and per-currency calculation: restaurant earns (total − delivery_fee
      − commission_amount). PDF summary now shows "Gross order revenue / Delivery pass-through / Commission
      / Net payout" for clarity. +2 tests (delivery_fee=20 and delivery_fee=0 cases). (menu/views.py;
      test_a5followup_billing.py). [scout A5-followup]
- [x] **Per-row net_payout float vs per-currency Decimal → off-by-a-cent** — rows compute net via
      round(float(...)) while per_currency re-aggregates with Decimal; sum(round(xi)) != round(sum(xi)) so the
      rows can fail to reconcile to the totals on the same PDF. Make the per-row path Decimal too.
      (menu/views.py:8008-8012 vs 8042-8054). [scout A5-followup]
      SHIPPED 3d2a5d1 — per-row net_payout now `float((o.total - o.commission_amount).quantize(Decimal("0.01")))`.

### A5-FOLLOWUP — BILLING CORRECTNESS — SHIPPED (the items below are DONE; see Done section)
A5 added the per-tenant commission rate + snapshot + tz-correct statement, but the scout found the
billing surface needs more before real money flows. #1/#2 are real money-overstatement bugs.
- [x] **Commission not reversed on cancellation (money — platform bills commission on fully-refunded
      orders)** — CustomerOrderCancelView refunds wallet/loyalty/stock but never touches
      commission_amount, and OwnerCommissionStatementView filters source+date only (no status exclusion),
      so cancelled orders still sum into total_commission. Fix: zero/exclude commission on cancel (exclude
      CANCELLED from the statement, or zero commission_amount on cancellation). (accounts/views.py:3143-3148;
      menu/views.py:7933-7956). [scout A5] **(do first)**
      DONE (verified code-read): `.exclude(status=Order.Status.CANCELLED)` at menu/views.py:8106.
- [x] **Item-void partial refund doesn't reduce commission** — VoidOrderItemView refunds the voided line
      but leaves commission_amount at the original full-order value → platform over-collects. Recompute
      commission on the new effective food subtotal at void. (menu/views.py:4313-4383). [scout A5]
      DONE (verified code-read): `_recompute_commission` + `commission_amount` save at menu/views.py:4361/4448.
- [x] **Statement sums MIXED currencies into one total** — OwnerCommissionStatementView aggregates
      Sum(total)/Sum(commission) with no GROUP BY currency, and the PDF labels everything with
      orders_data[0].currency. Bucket per ISO currency. (menu/views.py:7952-7960/7993; order currency
      accounts/views.py:3307). [scout A5]
      DONE (verified code-read): per-currency OrderedDict bucketing at menu/views.py:8144-8170.
- [ ] **Commission basis pre- vs post-discount (DECISION-GATED — owner)** — commission = pre-discount
      food_subtotal × rate, but net_payout = Sum(total) (post-discount+tip); when a promo/loyalty applies
      the restaurant is charged on revenue it didn't collect. Decide: charge on post-discount food, or keep
      gross-pre-discount with the merchant absorbing promos (document in the merchant agreement). OWNER
      decision. (accounts/views.py:3478-3485; menu/views.py:7943-7951). [scout A5]
- [ ] **Take-rate units inconsistent across paths + ride is global-only** — marketplace_commission_pct is a
      FRACTION (0–1), delivery_commission_pct is PERCENT (0–100), ride_commission_pct is a single GLOBAL
      PlatformConfig value (no per-tenant override). Converge units + add per-tenant ride override. (tenancy
      delivery_pricing.py:203; accounts/ride_service.py:157-159). [scout A5]
- [ ] **Delivery has no rate snapshot + sub-percent precision capped** — DeliveryJob stores
      platform_commission amount but not the rate (can't re-audit after a rate change), and the
      DecimalField(decimal_places=2) on the fraction can't represent 12.5%/7.5% (rounds to whole percent).
      Add delivery_commission_rate_applied + widen decimal_places if sub-percent rates are wanted.
      (accounts/models.py:733-737; menu/models.py:465-467; sales/views.py:1244). [scout A5]

## Done (moved from above)
<!-- - [x] item — commit hash -->
- [x] a11y-standalone-routes "skip-link + focusable <main> on the no-layout routes + ErrorBoundary landmark"
      (verified by me, frontend gates green: lint clean, 124 tests, i18n complete, build OK; reviewer SHIP, no
      blocking). New PlainLayout.vue (chrome-less skip-link + <main id=main-content tabindex=-1>, reuses
      common.skipToMain) wraps all standalone routes (signin/waiter-join/forgot/reset/unauthorized/activate/8×admin/
      404) via the router parent-route mechanism; 4 pages' inner <main> demoted to <div> for single-main. Scout
      caught the last landmark gap — ErrorBoundary's error fallback had no main/skip target → wrapped in <main
      id=main-content tabindex=-1> + focus-on-error. New PlainLayout.test.js + ErrorBoundary.test.js; 2 orphaned
      heading ids removed. — a11y-standalone-routes commit.
- [x] frontend-closed-deadend "block dine-in add-to-cart when closed; steer pickup/delivery to order-ahead;
      preserve scheduling" (THE owner's chosen item; verified by me, frontend gates green: verify:i18n + lint clean,
      119 tests, build OK). New businessHours.js canAddToCartNow / canPlaceImmediateOrderNow /
      classifyClosedOrderState mirror the backend order gate; CategoryPage/DishPage block dine-in add when closed
      (pickup/delivery stay addable); Cart.vue disables immediate Place Order when closed + steers to "Schedule for
      later" (dine-in: can't-order notice); validateForm blocks the immediate-409 path. **Order-ahead preserved — a
      scheduled pickup/delivery order still places when closed.** 3 i18n keys EN/FR/AR; 16 new businessHours tests.
      **The workflow DIED mid-run (5h 0-byte output) after the impl wrote the files; I reviewed the diff myself
      (scope guard held) + ran the gates (the dead run never did) before committing.** — frontend-closed-deadend commit.
- [x] meta-live-isopen "recompute is_open_now POST-cache on /api/meta/ + bust meta cache on ClosureDate writes"
      (verified by me, backend 3878/0, migrations clean, reviewer APPROVE — cache-integrity #1 risk verified: the
      recompute deepcopies, cached object byte-for-byte unchanged, no cache-hit DB, no _isopen_raw leakage). The
      last cached open-state surface: the menu/meta page now agrees with the marketplace card instead of freezing
      is_open_now for 300s. Scout caught that ClosureDate create/delete busted NO cache while the recompute freezes
      closure_today → fixed (bust meta cache on closure writes). New MetaIsOpenNowRecompute + integration + 2
      closure-bust tests. Scout → menu-list happy-hour cache (60s, same class) + listings-ignore-ClosureDate (design
      gap) triaged. — meta-live-isopen commit.
- [x] marketplace-live-fields "recompute is_open/promo_badge/flash_sale_active POST-cache" (verified by me,
      backend 3866/0, migrations clean, reviewer PASS — verified the #1 risk, no cache-object mutation: the refresh
      deepcopies, so a 2nd cache hit recomputes off intact raw inputs). The directory/marketplace listings cache the
      expensive SQL+assembly but recompute the time-sensitive verdicts on every request from cached raw inputs (no
      cache-hit DB; _raw_* stripped from the response). **The scout caught two follow-on defects the reviewer missed
      — the fresh is_open vs the FROZEN ?open=1 filter + open-first sort (a now-closed row could sit in an open-only
      list or keep a top slot) — which I fixed in the same commit: the refresh pass re-applies the filter + sort on
      the recomputed verdict (threaded open_only + open_first_sort from the view).** New RefreshLiveFieldsTests (7).
      Scout → /api/meta/ is_open_now (300s) same-class staleness triaged as next. — marketplace-live-fields commit.
- [x] frontend-open-state "one isRestaurantOpenNow(profile) verdict consuming server is_open_now" (verified by
      me, frontend gates all green: verify:i18n clean, lint clean, test 103/103, build OK; reviewer approve-with-
      1-major which the fix phase resolved). New businessHours.js isRestaurantOpenNow (is_open_now-first, graceful
      fallback) + businessHours.test.js (9 cases); Menu/MenuSelect/Cart/CustomerLeadPage display verdicts repointed;
      ordering gates deliberately left on raw is_open (scope guard — protects order-ahead). Reviewer caught a
      self-introduced contradiction on DishPage (schedule-aware notice + raw-is_open gate said "ordering disabled"
      while Add stayed enabled) → fix reverted DishPage's notice to lockstep with its gate. Scout mapped ROUND 2
      (CustomerLayout banner still raw is_open = most-visible miss; the add-to-cart→409 dead-end, unrecoverable for
      dine-in, fix = MarketplaceMenuPage's gate-on-verdict+Closed-pill pattern; the opens-at label regression) →
      triaged in BACKLOG. — frontend-open-state commit.
- [x] open-state-consolidation "one shared tenant-local schedule-window helper; fix get_is_open_now UTC bug"
      (verified by me, backend 3859/0, migrations clean, reviewer PASS/GREEN — ran a 1071-case differential
      proving schedule_open_now matches the old _schedule_open exactly, 0 mismatches). NEW tenancy/openstate.py
      (schedule_open_now tri-state + tenant_local_now, stdlib+settings only, no cycle). The 3 backend "is open
      now" derivations (menu _schedule_open, accounts _compute_is_open_now, serializer get_is_open_now) now
      delegate the window rule. get_is_open_now was on utcnow() → now tenant-local + gained the temp-disable
      guard, so the customer menu page agrees with the marketplace card for non-UTC tenants. New test_openstate.py
      + rewritten test_profile_is_open_now.py. Scout → FRONTEND OPEN-STATE cluster (businessHours.js on the
      browser clock; MenuSelect/CategoryPage/Cart/DishPage ignore server is_open_now → add-to-cart dead-end)
      triaged as the next (user-visible) batch. — open-state-consolidation commit.
- [x] list-cache-coherence "bust public list cache on profile-edit + lifecycle + delivery + template writes;
      unify is_open (tenant-local)" (verified by me, backend 3834/0, migrations clean, reviewer SHIP-with-1-
      followup which I then fixed). ProfileView.perform_update busts when validated_data hits a new
      LISTING_RELEVANT_FIELDS set; sales admin lifecycle toggle + enforce_subscriptions (once/run) bust on
      lifecycle_status flips; DirectoryView is_open unified onto _compute_is_open_now, whose schedule eval was
      moved utcnow()→tenant-local (profile tz→settings.TIME_ZONE→UTC). Reviewer/scout caught TWO bonus bugs in
      AdminTenantDeliveryView that I fixed in the same commit: (a) update_fields.append("updated_at") → 500 on
      EVERY admin delivery edit (Profile has no updated_at; masked by a save=Mock() test — added a guard), (b)
      delivery_fee/minimum not busted; PLUS the menu template-apply business_type write now busts too. New/edited
      tests across test_tenant_meta_cache, test_admin_tenant_lifecycle, test_enforce_subscriptions_listcache
      (new), test_directory_marketplace_views, test_accounts_open_and_promo, test_admin_tenant_delivery,
      test_apply_template. Scout → OPEN-STATE consolidation (3rd is_open copy get_is_open_now still on UTC +
      temp-disable inconsistency) triaged as next batch. — list-cache-coherence commit.
- [x] denorm-coherence "one tenant-local promo rule + capped-promo exclusion + flash-sale cache bust"
      (verified by me, backend 3810/0, migrations clean, reviewer SHIP IT 0 critical/major, scout → LIST-CACHE
      COHERENCE cluster). New menu/promos.py = single source of truth promo_is_active(promo, *, now_local)
      (stdlib-only, model-or-dict); both _is_promo_active_now copies are thin wrappers; the whole promo window
      now evaluates from ONE tenant-local now_local (fixes the date.today()/utcnow() mismatch — promo windows
      are tenant-local). recompute_tenant_promos excludes capped promos (Q max_uses NULL | use_count<max_uses);
      the checkout cap-strip refresh_from_db's the count + recomputes ONLY at the cap-crossing (concurrency-safe
      gate I added over the reviewer's in-memory suggestion). _bust_public_list_cache on all flash-sale writes
      (create/patch/delete/opt-in/opt-out). New PromoIsActiveSingleSourceTests + cap-filter + flash-sale-bust
      tests; existing promo-window tests repointed to the new clock. — denorm-coherence commit.
- [x] promo-badge N+1 kill (promo denorm) — the LAST per-tenant query in the public marketplace listing
      loop. (verified by me, backend 3805/0, migrations clean, reviewer 0 findings, scout CONFIRMED both
      DirectoryView + MarketplaceView loops are now fully query-free.) Profile.marketplace_promos JSONField
      (tenancy/0043) holds each tenant's is_active promo schedules (type/value/days/time_start/time_end/
      active_from/active_until, ordered -discount_value[:5] = the old selection); recompute_tenant_promos
      (menu/promos_denorm.py) refreshes it from the tenant schema + busts the public list cache, wired via
      menu.Promotion post_save/post_delete signals + a backfill_profile_promos command; the marketplace loop
      computes promo_badge IN-MEMORY at request time (_promo_badge_from_denorm) so the window stays correct
      across boundaries — no per-tenant schema_context. New test_promo_denorm.py. Scout → "marketplace denorm
      coherence" cluster above (capped-promo badge drift, consolidate the duplicated _is_promo_active_now +
      today/utcnow tz bug [real — affects checkout discount], flash-sale cache coherence, composite index).
      — promo-n1 commit.
- [x] B8-followup scale "list-cache bust on rating + min_rating index" (verified by me, backend 3774/0,
      migrations clean, reviewer 0 findings): the public marketplace/directory list cache is now bustable —
      _public_list_cache_key embeds a GLOBAL version (public_list_ver) and _bust_public_list_cache()
      (mirrors _bust_menu_cache: incr + ValueError-seed, best-effort) is called from recompute_tenant_rating
      after the public Profile update (lazy import to avoid the menu→accounts cycle), so a new rating
      refreshes the listing immediately instead of after the 90s TTL; + composite index
      profile_marketplace_rate_idx (directory_opt_in, is_menu_published, rating_avg) (tenancy/0042) backing
      the min_rating filter. New test_b8followup_scale.py. — b8followup-scale commit.
- [x] B1-followup "email List-Unsubscribe + one-click unsubscribe" (compliance gate for the B1 email
      feature; verified by me, backend 3762/0, migrations clean): send_marketing_email switched send_mail →
      EmailMessage carrying RFC 8058 List-Unsubscribe (https one-click endpoint + mailto fallback) +
      List-Unsubscribe-Post: One-Click headers + a visible unsubscribe link in the body; per-recipient token
      via django.core.signing (accounts/unsubscribe.py — NO model field). New public EmailUnsubscribeView
      (config/public_urls.py /api/unsubscribe/<token>/): AllowAny, GET confirmation + CSRF-exempt no-auth
      POST one-click → notify_promotions=False, idempotent, invalid token doesn't 500/leak, throttled
      (email_unsubscribe). Win-back + campaign senders pass customer_id so each mail gets a per-recipient
      token. **Reviewer caught a MAJOR prod bug: the DRF view 406'd on Accept: text/html in prod (only
      JSONRenderer; DEBUG's BrowsableAPIRenderer masked it in tests) → one-click POSTs from mailbox
      providers would silently fail to unsubscribe. Fixed with StaticHTMLRenderer + a no-op content-
      negotiation class + 3 regression tests pinning the PROD renderer set.** New test_b1followup_unsubscribe.py.
      Scout → remaining email-program hardening (verified-only [owner reach tradeoff], bounce/complaint
      suppression [needs ESP webhook], SPF/DKIM/DMARC [deploy DNS]) stays in the cluster above. — b1followup commit.
- [x] B8 "marketplace cross-schema N+1 kill (rating denorm)" (KEPOLI_NEXT.md Phase B; verified by me,
      backend 3734/0, migrations clean, reviewer 0 critical/major): added Profile.rating_avg +
      rating_count (tenancy/0041); menu/ratings.py recompute_tenant_rating aggregates Rating in the tenant
      schema → writes the rounded-1dp avg + count to the PUBLIC Profile (best-effort, None/0 on last-delete,
      skips public schema); wired menu.Rating post_save/post_delete signals + a backfill_profile_ratings
      command (run once on deploy — LAUNCH_CHECKLIST noted). DirectoryView is now PURE in-memory (no
      per-tenant schema_context); MarketplaceView reads the denormalized fields + pushes min_rating to a SQL
      Profile filter. New test_b8_rating_denorm.py. Scout → B8-followup cluster above (promo-badge N+1 still
      in the MarketplaceView loop, 90s list-cache not busted on rating change, no index for min_rating,
      denorm drift on owner-reply/out-of-ORM writes). — b8 commit.
- [x] OPS-6c-followup "a11y: SPA route-change focus + duplicate-main cleanup" (verified by me; frontend
      i18n/lint/94 tests/build green, backend 3719/0 sanity, reviewer 0 critical/major) — completes B12's
      skip-link work. (1) new frontend/src/router/focusGuard.js (createMainContentFocusGuard) wired via
      router.afterEach: on each NON-initial navigation, after nextTick, focuses #main-content with
      preventScroll; bails on the cold load, when a [role=dialog]/[aria-modal]/.modal holds focus, or when
      #main-content is absent (so standalone routes safely no-op); SSR-safe. +4 unit tests. (2) demoted
      duplicate page-level <main> → <div>/<section> (layout owns the single <main id=main-content>) in
      Home/Marketplace/MarketplaceMenuPage/MarketplaceOrderStatus/OwnerNotifications/Wizard/DriverPage/
      ReservationManage (Home's stale duplicate id was already gone; standalone routes kept their sole
      <main>). (3) breadcrumb crumb URLs aligned to their named routes. Residual (pre-existing, triaged
      above): standalone auth/error routes lack a skip-link/#main-content. — ops6c-followup commit.
- [x] B12 / OPS-6c "SEO + a11y + PWA depth" (KEPOLI_NEXT.md Phase B; verified by me, backend 3719/0,
      frontend i18n/lint/test/build green, migrations clean): (1) [PRIVACY] noindex personal/transactional
      pages — useSeoMeta now uses an INDEXABLE_ROUTE_NAMES ALLOWLIST (public discovery only); cart/account/
      order-status/find-my-order/checkout/reserve emit noindex,nofollow (was index,follow leaking order PII).
      (2) sitemap.xml — new backend public-host view (config/sitemap.py, static pages + ACTIVE opted-in
      tenant storefronts, resilient) + nginx /sitemap.xml proxy (reviewer caught it 404'd through nginx) +
      robots.txt Sitemap directive. (3) hreflang en/fr/ar (+x-default) on indexable pages. (4) JSON-LD
      depth — BreadcrumbList + MenuItem/Product offers + enriched business node. (5) DishCard no longer a
      role=button wrapping <button> children (valid ARIA). (6) skip-link <main tabindex=-1> on Customer+Owner
      layouts. (7) Wizard: dropped the broad aria-live, focus→step heading + terse status. (8) PWA install
      shown on mobile (CustomerLayout + OwnerLayout — I mirrored the owner one the workflow missed). (9)
      theme-color synced to tenant brand (theme.js/App.vue). (10) padded maskable manifest icons. Reviewer
      2 major (sitemap unreachable via nginx; sitemap advertised noindex URLs) — fixed; I also removed
      table-link from the indexable allowlist (per-table dup, review minor) + fixed owner mobile install.
      New test_sitemap_view.py. Scout → OPS-6c-followup a11y cluster above (route-change focus hook +
      duplicate <main>/id — coupled; breadcrumb labels). — b12 commit.
- [x] B1 "email retention channel" (KEPOLI_NEXT.md Phase B; verified by me, backend 3714/0, migrations
      clean, reviewer found 0 critical/major): win-back nudges + owner campaigns were PUSH-ONLY (reached only
      push-granted users — tiny on iOS). Now dual-channel: send_winback_nudges audience broadened from
      push-subscribers to push-OR-email (opted-in lapsed customers with a push sub OR a non-empty
      Customer.email), and the send loop delivers push (if subscribed) + email (if email on file) — the nudge
      counts as delivered if EITHER channel succeeds, the 90-day WinbackNudge dedup slot is reclaimed only if
      BOTH fail; OwnerCampaignView dispatch likewise emails its opted-in audience alongside push. New
      send_marketing_email helper (reuses the existing send_mail path; notify_promotions opt-out enforced
      both channels; record_notification per channel). 50/run cap + daily marker + per-day campaign cap +
      tenant isolation preserved. New test_b1_email_retention.py. Reviewer 2 minor (push-only audience
      preview estimate; stale docstrings) — both FIXED by me (audience_estimate now the push∪email union;
      campaign + winback docstrings updated; +the test_get_shape mock). Scout → "email-program hardening"
      cluster above (List-Unsubscribe/one-click, verified-only sending, bounce suppression, per-tenant
      opt-out) — REQUIRED before sending real marketing mail (deferred; app not live). — b1 commit.
- [x] A5-followup "billing correctness" (verified by me, backend 3698/0, migrations clean, reviewer found
      0 issues): (1) the commission statement now EXCLUDES CANCELLED orders (once on the base queryset so
      the aggregate Sum and per-order rows agree) — the platform no longer bills commission on fully-refunded
      cancelled orders. (2) item-void recomputes Order.commission_amount = commission_rate_applied × the new
      non-voided pre-discount food subtotal (marketplace-only, clamped >= 0) — partial refunds no longer
      over-collect. (3) the statement reports per-ISO-currency totals (+ PDF labels each currency correctly)
      instead of summing mixed currencies / stamping the first row's currency on everything. New
      test_a5followup_billing.py. Scout → "commission ledger / revenue-recognition redesign" cluster above
      (immutable invoices, collected-basis accrual, delivery-commission reversal symmetry, delivery-fee in
      net_payout, float/Decimal rounding) — deferred as a pre-marketplace-launch design pass (PSP-blocked;
      not live-critical; basis is an owner decision). — a5followup commit.
- [x] A5 "marketplace commission correctness" (KEPOLI_NEXT.md Phase A; verified by me, backend 3689/0,
      migrations clean): per-tenant Profile.marketplace_commission_pct (default 0.10 → behaviour unchanged;
      admin-only via sales/views.py tenant endpoint, NOT owner-editable — a restaurant can't zero its own
      commission, asserted) + Order.commission_rate_applied snapshot (tenancy/0040, menu/0059); the
      marketplace commission write uses the tenant rate (fallback 0.10 on null/malformed); the statement
      buckets by TENANT-LOCAL month (was UTC created_at__year/month) + surfaces the rate per row; PDF label
      derived from the snapshot (reviewer caught a hardcoded "10%"). Basis (pre-discount food) documented,
      not changed (owner decision). New test_a5_commission.py. Scout → A5-followup billing cluster above
      (commission reversal on cancel/void [money], multi-currency statement, basis decision, unit
      reconciliation, delivery snapshot/precision). — a5 commit.
- [x] Profile import bug (user-reported) — MarketplaceMenuView + MarketplacePlaceOrderView imported
      `Profile` from menu.models (none there → it's in tenancy.models); the ImportError was swallowed by
      the views' broad try/except into HTTP 500 server_error on EVERY marketplace menu fetch + order
      placement. Split to `from tenancy.models import Profile`. CI was green because the only tests
      reaching the import MASKED it (sys.modules fake menu.models w/ Profile; patch.object(...,create=True))
      — repointed those 3 to patch tenancy.models.Profile + added 2 regression tests asserting no
      server_error. Backend 3672/0. LESSON: broad try/except around a lazy import hides ImportError as a
      500; patch(...,create=True) silently invents a missing attr and masks such bugs. — c13c06a.
- [x] A4 "marketplace COD-on-handover" (KEPOLI_NEXT.md Phase A, pre-PSP GMV; verified by me, backend
      3677/0, FE i18n/lint/test/build green, migrations clean; reviewer found 0 issues). Ported the direct
      restaurant trusted-customer cash-on-handover to the marketplace: MarketplacePlaceOrderView gained
      _mkt_cod_order — COD only when payment_method=='cash' AND not scheduled AND _cod_eligible(profile,
      customer) (owner cod_enabled + customer has >= cod_min_paid_orders COMPLETED+PAID at THIS restaurant);
      such orders are created UNPAID (use_wallet=False, no deduction) and settled at handover (driver
      collects cash for delivery). Non-eligible / scheduled / wallet-chosen still prepay (402 when short).
      Both _PrepayUnpaid safety nets verified to not fire for COD (one use_wallet-guarded, one exempted via
      `not _mkt_cod_order`). MarketplaceMenuView now returns cod_enabled/cod_eligible so the cart knows.
      Frontend MarketplaceMenuPage.vue shows a wallet-vs-cash chooser only when cod_eligible (sends
      payment_method:'cash'); wallet-only flow unchanged otherwise. New test_a4_marketplace_cod.py (5) +
      4 i18n keys EN/FR/AR. — a4 commit. **Phase-A non-decision-gated eng items A7+A4 DONE; remaining A2
      (plan prices) + A5 (commission default) are decision-gated; A3 (PSP top-up seam dormant) buildable.**
- [x] A7 "durable Redis/Celery boot assertion" (KEPOLI_NEXT.md Phase A; verified by me, backend
      3670/0). Prod silently degraded when REDIS_URL/CELERY_BROKER_URL were unset (cache→LocMemCache,
      channel layer→InMemoryChannelLayer, tasks→inline daemon thread) → cross-worker broadcasts (live
      order/paid) + in-flight notifications lost on multi-worker prod. Fix: a Django deploy system check
      (config/checks.py, register(deploy=True)) — kepoli.E001 ERROR when DEBUG=False + REDIS_URL unset,
      kepoli.W001 WARNING when CELERY_BROKER_URL unset (inline mode is a supported opt-in fallback, so
      not a hard-fail). Registered via AccountsConfig.ready(); entrypoint.sh runs `manage.py check
      --deploy --fail-level ERROR` before starting uvicorn so a misconfigured deploy HARD-FAILS (Coolify
      keeps the old container); SKIP_DEPLOY_CHECK=1 emergency bypass. Verified: DEBUG=True silent (dev/
      tests unaffected), DEBUG=False+no-Redis → E001 + exit 1. coolify.env.example (REDIS required note +
      CELERY_BROKER_URL line) + LAUNCH_CHECKLIST §2 updated. NO settings-import raise (would break manage
      commands/tests). — a7 commit. Next Phase-A eng: A4 marketplace COD-on-handover.
- [x] OPS-5h "final security batch" (verified by me, backend 3670/0, migrations clean) — CLOSES the
      OPS-5x security program. (1) customer-login session fixation — all three finalizers
      (_rotate_customer_session) cycle the session key before the anon→customer privilege jump (phone/
      Google/email). (2) OTP SMS toll-fraud — _otp_recipient_guard adds a per-recipient cooldown +
      hourly cap (cache-keyed on canonical phone/email), independent of the IP throttle, run BEFORE
      code-gen so a cooled-down re-request can't reset the verify counter. (3) auth OTP now uses
      secrets.randbelow (Mersenne-Twister purged from the money/auth paths). (4) the ONE missed
      idempotency site — _refund_wallet_for_cancelled_order now routes through credit_wallet with a
      schema-namespaced key cancelrefund:{schema}:{order.id}, type=REFUND, tenant_id set,
      require_verified=False (replaces the direct balance write + order_number-based guard). (5)
      RequestLoggingMiddleware._safe_path redacts sensitive query values (code/phone/token/otp/…) so the
      cash-out ?code= bearer credential + ?phone= no longer land in logs/Sentry. Reviewer found 1 major
      (a test-only mock-cache TypeError in the OTP guard test — sibling missed during impl; production
      unaffected since a real cache miss returns None) — fixed. New test_ops5h_auth.py +
      test_ops5h_refund_logging.py. **FINAL CONVERGENCE SCOUT: no new exploitable money/auth/IDOR/tenant
      issue — the security surface has converged; OPS-5x program COMPLETE.** Workflow finalGates stale
      (3637) — my full re-run = 3670/0. — ops5h commit.
- [x] OPS-5g "idempotency namespacing + redemption hardening" (verified by me, backend 3637/0,
      migrations clean): (1) [HIGH] the 3 customer/staff wallet idempotency keys now schema-namespaced
      (order-pay-{schema}-{order_number}, orderpay:{schema}:{payment.id}, voiditem:{schema}:{item_id}) —
      closes the cross-tenant collision → free-order; order-status PAID guard is the durable backstop so
      the format change is safe. (2) loyalty-redeem replay now customer-scoped (both lookups) + throttle
      — IDOR/info-leak closed. (3) voucher redeem throttle (VoucherRedeemThrottle) + per-actor invalid-code
      lockout (5/15min) + CSPRNG (random.choices→secrets.choice). (4) ride wallet settle: explicit
      recorded cash-fallback (no silent flip). (5) OGView cache key re-keyed on resolved tenant id +
      bounded path (not the spoofable Host). Review found 1 minor (OG no-tenant BODY still used the
      inbound host) — I FIXED it in close-out (no-tenant canonical_host now from BRAND_DOMAIN, + a
      body-host test). New test_ops5g_idempotency.py + test_ops5g_voucher.py. **The scout EXPLICITLY
      CONFIRMED the core money/IDOR/wallet-idempotency surface has CONVERGED after 5c→5g** (verified clean:
      wallet_service locks+assertions, schema-namespaced keys, throttled redemptions, cash-out lockout,
      push-sub scoping, WS ownership, OG key, admin PII gate, SSRF allow_redirects=False, upload re-encode).
      Remaining → OPS-5h above = 5 ADJACENT items (session cycle_key, OTP toll-fraud cooldown, auth-OTP
      CSPRNG, the one missed cancel-refund idempotency site, request-log secret scrubbing) = the FINAL
      security batch. NOTE: the workflow gate agent under-reported 3609 (stale) — my full re-run = 3637/0.
      — ops5g commit.
- [x] OPS-5f "money/IDOR security" (verified by me, backend 3609/0, migrations clean, no model
      changes; reviewer found 0 issues — clean on first pass): (1) [HIGH] MarketplacePlaceOrderView
      DishOption price manipulation — options query now select_related("dish") + per-item binding check
      (opt.dish.slug==dish.slug), foreign/cross-dish/negative-delta option ids rejected with 400
      stale_options (mirrors menu/views.py); closes the wallet-prepaid total-lowering hole. (2) [HIGH]
      de-approved driver banking earnings — DriverJobStatusUpdateView re-checks
      Customer.filter(pk,driver_approved=True).exists() at the DELIVERED money-emitting transition (403
      driver_not_approved). (3) DeliveryRatingView customer branch now requires order ownership + a
      DeliveryRatingThrottle (30/hr). (4) CustomerWalletRedeemVoucher now funnels through credit_wallet
      (locks the customer row, idempotent voucher:{id}) — closes the lost-update race. (5) password-reset
      no longer builds the link from the spoofable get_host() (server-authoritative _canonical_brand_host
      via new BRAND_DOMAIN setting) + PasswordResetConfirm invalidates the user's other sessions. (6)
      OwnerWalletCharge sub-threshold instant path capped (5 charges / 100.00 per pay-token, per-actor
      OwnerWalletChargeThrottle 30/min). (7) transfer_between_customers (P2P) replay now has the
      identity-only collision assertion (was the one money fn OPS-5e missed). New test_ops5f_accounts.py
      + test_ops5f_money.py. Scout CONFIRMED clean dimensions (WS auth, driver/ride state machines, admin
      money caps, core wallet service, profile allowlist, IP throttles) → OPS-5g cluster above is the
      remaining money/IDOR tail (tenant-schema idempotency-key namespacing [HIGH], loyalty-redeem customer
      filter, voucher throttle + CSPRNG, ride escrow, OG cache key). — ops5f commit.
- [x] OPS-5e "money/IDOR security" (Phase A P0; verified by me in code, backend 3578/0, migrations
      clean, no model changes): (1) [HIGH] driver cash-out brute-force — per-actor failed-attempt
      cache lockout (CASHOUT_CONFIRM_MAX_FAILURES=5/15min, user→tenant key) shared by BOTH the confirm
      AND the lookup oracle (reviewer caught the lookup bypass), + DriverCashoutConfirmThrottle (10/min)
      on both endpoints; server-side cashout:{req.id} idempotency untouched. (2) [HIGH]
      MarketplaceOrderStatusView IDOR — financial body (items/totals/payment/wallet/loyalty/schedule)
      now gated on session-customer ownership; non-owner gets a minimal status only (items materialized
      only for the owner, inside schema_context). (3) [money] wallet idempotency — externally-supplied
      keys server-namespaced at ALL body sites (ownercharge:{schema}: / adminfund:{tenant}: /
      ownertopup:{schema}: — reviewer caught the topup site) + defense-in-depth replay assertions
      (customer_id in credit/debit_wallet, tenant_id in credit_tenant_float + transfer_to_customer);
      asserts identity ONLY not amount (allow_partial-safe), internal key formats unchanged. (4)
      CustomerOrderRate ownership gate + throttle (30/hr). (5) push-sub hijack → update_or_create scoped
      to (customer_id, endpoint). (6) TranslateView no longer echoes the provider error body. (7) OGView
      canonical/og:image derived from the tenant's authoritative domain not the spoofable Host. (8)
      is_staff dropped from can_access_admin_console + all_access capability flags. New test_ops5e_money.py
      + test_ops5e_accounts.py; updated marketplace/ratings/wallet tests for the new contracts. Reviewer
      3 major (cash-out lookup oracle, un-namespaced topup key, frozen marketplace test) — all fixed.
      NOTE: workflow finalGates misreported 2700 (partial run) — my full re-run = 3578/0. Scout → OPS-5f
      cluster above (DishOption price manip [HIGH], DeliveryRating customer IDOR, driver-approval-bypass
      earnings, P2P replay assertion, sub-threshold charge cap, voucher race, reset host poisoning). —
      ops5e commit.
- [x] OPS-5d "security" (verified by me in code; backend 3541/0, migrations clean): (1) [HIGH]
      Celery run_management_command arbitrary execution — added a hardcoded allowlist (the exact
      CELERY_BEAT_SCHEDULE command names) at the top of the task; disallowed names are logged + skipped
      (no raise → no acks_late poison loop); covers the inline-thread enqueue() fallback too. (2) [HIGH]
      Google One-Tap account takeover — _verify_google_token now rejects unless
      str(email_verified).lower()=="true" (tokeninfo returns the claim as a STRING), closing the
      unverified-email auto-link for sign-in AND account-link. (3) [money] AdminWalletBonus double-credit
      race — cache.add() mutex on the idempotency_key (mirrors campaign-cap); I moved it AFTER the
      empty-batch check (review minor) so a no-op 400 can't falsely dedupe a corrected retry. (4) CORS
      *.localhost:5173 regex now gated behind DEBUG (empty in prod). (5) cross-persona session layering —
      customer-login finalize paths (OTP/email/Google) refuse to write customer_id when request.user is
      an authenticated staff/owner. (6) CustomerReservationsView throttled (60/hr) + cancel_token removed
      from the list. (7) Django static_serve /media only under DEBUG / SERVE_MEDIA_FROM_DJANGO. (8)
      _IPThrottle (menu AND accounts — accounts was a review minor I completed, it backs the login/OTP
      brute-force buckets) now keys on trusted-proxy get_request_ip, not spoofable XFF[0]. (9) deploy:
      entrypoint --forwarded-allow-ips pinned to docker subnet, --password dropped for PLATFORM_ADMIN_PASSWORD
      env; coolify.env.example documents CORS/SERVE_MEDIA/ADMIN_URL/PLATFORM_ADMIN_PASSWORD. **PLUS the
      scout caught the OPS-5b is_staff priv-esc was STILL open in 10 helper sites (not the 3 it named) —
      I dropped is_staff from EVERY authz gate: menu/views.py _can_preview_unpublished×2, AnalyticsSummary
      _can_view, _can_edit_tenant_order, _can_view_revenue, _can_edit_menu, _is_tenant_owner, the menu-
      disabled preview, the admin customer-search gate, + accounts/views.py _is_tenant_owner. Flipped 5
      is_staff-grants-access tests to assert rejection + updated 2 accounts throttle tests for the
      trusted-proxy ident. LESSON RE-CONFIRMED: grep EVERY gate sharing an authz pattern — OPS-5b fixed
      the permission CLASSES but missed these 10 helper FUNCTIONS.** New test_ops5d_app.py (22) +
      test_ops5d_config.py. Reviewer 2 minor (both fixed). Scout → OPS-5e cluster above (driver cash-out
      IDOR, marketplace order IDOR, wallet idempotency cross-tenant, rating fraud, push hijack, +2). —
      ops5d commit.
- [x] OPS-6b "a11y/SEO/UX polish" (verified by me; backend 3506/0, frontend i18n/lint/90 tests/
      build green, no new migrations): (1) PRE-HYDRATION lang/dir — new CSP-safe external
      frontend/public/locale-boot.js (no inline script; reads the same localStorage key as
      stores/locale.js, normalizes en/fr/ar, sets <html lang>/<dir> before #app paints; tenantDefault-
      only RTL is corrected at hydration — documented). (2) og:site_name now PLATFORM_NAME (was tenant
      name — restored Kepoli social attribution; og:title stays tenant). (3) JSON-LD @type per
      business_type via BUSINESS_TYPE_SCHEMA_MAP (Restaurant/CafeOrCoffeeShop/Bakery/GroceryStore/Store/
      Pharmacy; stable element id, no duplicate tag). (4) <noscript> now tri-lingual (en/fr/ar + support
      link). (5) Wizard forward-progression guard — highestCompleted gating + Publish disabled until
      canPublish (categories>0 && dishes>0, the same rule as the warning); backward nav free. (6)
      Pharmacy parapharmacie/no-Rx disclaimer in StepPublish. (7) Cart map dialog focus-restore on close
      (APG); Menu reviews carousel keyboard-operable (tabindex + arrow keys + visible focus). (8) Cart
      named-branch error mapping — promo/loyalty/schedule branches no longer leak raw backend detail
      (incl. the applyPromoCode standalone path I closed post-review — reviewer minor). (9) Activate.vue
      single valid <main> + correct pre-activation copy. (10) Print CSS scoped to button:not(.print-keep)
      so OwnerLaunchSuccess buttons print. (11) priceZeroWarning reworded count-accurate. (12) BACKEND:
      StaffChangePasswordView throttled (staff_change_password 10/hr, per-user) + 4 tests. 6 i18n keys
      added EN+FR+AR. Review: 2 minor (locale-boot tenantDefault limitation — commented; applyPromoCode
      leak — fixed). Scout → OPS-6c cluster above (sitemap, hreflang, noindex personal pages [privacy],
      MenuItem/Breadcrumb LD, DishCard ARIA, skip-link focus, wizard live-region, PWA install/theme-color/
      maskable icon). — ops6b commit.
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
