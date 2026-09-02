# Kepoli — session log

A running, **append-at-the-top** changelog of significant work sessions / campaigns. Each entry
records *what shipped*, *why*, and *the resulting state of `main`*, so a future session can
reconstruct recent history without archaeology through 300 commits. This complements — does not
replace — [`ARCHITECTURE.md`](ARCHITECTURE.md) (how it's built) and
[`RISK_REGISTER.md`](RISK_REGISTER.md) (known debt). For *what to do next*, see
[`NEXT_SESSION.md`](NEXT_SESSION.md).

> Convention: newest entry first. One entry per campaign/session. Keep it factual (PR numbers,
> what changed, current state) — opinions and roadmaps live in `NEXT_SESSION.md`.

---

## 2026-09-01 — deep speed-optimization campaign (8-lens hunt → 9 fixes shipped)

**Result:** `main` @ `d8d149f`, green. A second, **deeper** performance hunt on the owner's request
("continue hunting for speed gaps… big work… always vary agents per task"). Fanned out **8 distinct
read-only deep-dive agents** (varied per task — fresh agent + rotated model per lens), each on a surface
the 2026-08-30 pass couldn't reach at depth: DB query/over-fetch, DRF serializer/payload, frontend bundle,
frontend runtime #2, caching opportunities, Python hot-spots + sweep crons, async/WebSocket/broadcast, and
multi-tenant/cross-schema cost. Each was adversarial about real-vs-marginal (several lenses came back
**clean**, cross-validating the prior optimization — WS consumers, wallet_service, order indexing, existing
caches all re-verified correct). Multiple finds **converged** across independent agents (driver-poll phone
N+1 **3×**, driver-rating aggregate **2×**, cron `select_related` **2×**), raising confidence. Verified
autonomous-safe wins shipped as **9 CI-gated PRs (#316–#324)** via delegate-and-gate (fresh agent per
file-group, disjoint files; every money/concurrency/cache diff hand-reviewed):

**Three HIGHs:**
- **#323 — driver-poll N+1s (accounts/views.py).** `_serialize_delivery_job` ran a per-job `Profile`
  phone lookup **and** a per-row lifetime-rating aggregate — on the delivery-jobs list **every online
  driver polls every 5–15s** (~21 jobs) and the admin list (×100). Both folded into one batched query
  each (`_batch_restaurant_phones` + a grouped rating map), passed via optional serializer kwargs with the
  per-call query preserved as the single-job/tracking fallback (byte-identical output). Also: marketplace
  `bulk_create` (the order-line gap #304 left on the marketplace checkout path), `_customer_owns_tenant`
  dedup, dropped a dead `select_related("zone")`, added a missing `select_related("rating")`, and deleted
  a **dead SSE `?stream=1` branch** (blocking `time.sleep` + per-tick DB for 90s/conn — verified zero FE
  callers).
- **#322 — Web Push reliability (menu/push.py, accounts/push.py).** `webpush()` had **no request
  timeout** → a slow endpoint could hang a Celery worker (concurrency 2) to the 120s limit and silently
  drop already-dedupe-stamped sends; added `timeout=5` (caught by the existing broad `except` → "error",
  fails fast). Plus a bounded `ThreadPoolExecutor` fan-out (collect-then-bulk-delete expired subs on the
  caller thread — **no ORM off the main thread**) and a cap on the previously-uncapped package-driver
  audience.
- **#324 — MarketplaceMenuView cache (accounts/views.py + bust seams).** The heaviest uncached public GET
  (nested dish tree + per-dish happy-hour price + reviews + 30-order prep-ETA aggregate + loyalty +
  flash-sale, on every storefront open) now 60s single-flight cached under `mkt_menu:v1:{slug}`, mirroring
  the tenant-subdomain twin. **The trap, handled:** `cod_eligible` (per-customer trust), `is_open`, and
  `flash_sale` are computed per-request on a `copy.deepcopy(body)` **outside** the cache — `LocMemCache`
  returns by reference, so writing them onto the shared cached object would leak one customer's COD trust
  to the next. `build_fn` caches `cod_eligible=False` as the anonymous default; the publish gate stays
  live (404s unpublished immediately). Bust wired into `_bust_menu_cache` + `_bust_tenant_meta_cache` +
  the rating-recompute path. Regression tests prove two customers get different `cod_eligible` from one
  shared body.

**The rest (mediums/lows, all behavior-preserving):** partial index for the `WalletChargeRequest`
bill-sync poll (scanned every ~15s owner poll) + `DeliveryJob.created_at` index (#317, concurrent, ×1
shared — rides the staging rehearsal); `.only()` on the platform-wide driver pool + a lean
`_owed()`-under-money-lock that drops 5 of 7 aggregates (byte-identical to `summary["owed"]`) + earnings
aggregate fold (#320); `bulk_update` for bulk-ready-items under the order lock + loyalty/z-report aggregate
folds + `.only`/`.defer` over-fetch trims (#321); `select_related("profile")` in the 3-min
`escalate_stale_pending_orders` + two sibling crons (#319, matching two crons that already do it); and four
frontend render wins (#316 cached kitchen clock + per-card memo, #318 driver-timer guard + `demoMenu`
dynamic-import).

**Deferred — owner/judgment-gated (documented, deliberately NOT forced):** SW-precache scope (HIGH —
Workbox precaches the whole app for every persona; needs a real build + offline/device test);
`OwnerOrders`→`OwnerOrderCard` extraction (needs visual QA of a live operational page); driver-rating
denormalization onto `Customer`; proof-photo upload hoisted out of the `select_for_update` (security-
adjacent); admin count/`LIKE` (`reltuples`/`pg_trgm`); OSRM-per-row on the admin list (feature trim);
non-sargable `created_at__date` (timezone); the `Accept-Language`-not-in-cache-key edge (SPA-safe); two
HTTP `Cache-Control` header items; `AdminConsole` modal `defineAsyncComponent`. Each has a file:line in
the audit agents' output.

**Verification:** every PR green on all CI jobs before merge; the N+1-batch, `_owed`-under-lock, push-
concurrency, and marketplace-cache diffs were hand-reviewed (the last line-by-line for the cross-customer
trap). Full backend suite **5051–5067 passed, 0 new failures** across the campaign (local baseline: 1
Django-pin + ~82 DB-conn errors). Also recorded a memory: the user wants a **fresh, varied agent per task**
for heavy campaigns (`vary-agents-per-task`). **Not yet deployed** — deploy is manual (Coolify); the one
new concurrent-index migration (#317) joins the staging-rehearsal set.

---

## 2026-08-30 — full-app performance pass (fresh audit → 11 fixes shipped)

**Result:** `main` @ `6f572b4`, green. A fresh **31-agent read-only speed + hosting audit**
(12 expert lenses across backend ORM/query/index/cache/async, frontend bundle/runtime, infra;
high/critical findings adversarially re-verified) produced [`PERF_HOSTING_AUDIT.md`](PERF_HOSTING_AUDIT.md)
(PR #296) — 43 findings (1 critical, 16 high, 16 medium, 10 low), superseding the fully-implemented
2026-06-07 edition. The verified, autonomous-safe items shipped as **8 CI-gated PRs (#297–#304)** via
delegate-and-gate (disjoint-file worktree agents, per-PR CI gate, money/notif/query diffs hand-reviewed):

- **#302 — async-notification migration (CRITICAL).** The last synchronous email/SMS sends now go
  through the existing `enqueue()`/Celery infra. The critical case: **bulk order-confirm fired up to 50
  sequential blocking SMTP sends inside one request** (owner-facing hang / false-500 during peak). New
  tasks `order_status_email` (re-fetches the order under `schema_context` and reuses the unchanged
  `_send_order_status_email` builder — content/recipients/opt-out byte-identical), `customer_otp_sms`
  (OTP code never logged / never in a dedupe key — bearer-credential safe), and a general
  `send_transactional_email`. **9 call sites** moved off the request thread; already-async SMS/push
  untouched.
- **#297 — GIN index on `DeliveryJob.declined_by`.** The `declined_by__contains=[driver_id]` JSONB scan
  (polled every 5–15s by every online driver) is now index-backed.
- **#298 — `AdminAuditLog` indexes** (`-created_at`, `tenant,-created_at`) on the unbounded append-only
  audit table (was zero indexes → full-scan list/count/prune).
- **#300 — reservation count-query fix.** `.count()`-only reservation/alert queries no longer carry the
  reminder-metrics annotation (JOIN + GROUP BY + 3 subqueries) — a lean base queryset re-adds only the one
  annotation an active `reminder_filter` needs, so counts stay byte-identical (~9–10× less DB work). Also
  fixed the tenant-settings-export prefetch self-defeat (baked option `id`-order into the `Prefetch`).
- **#303 — cache `AdminPlatformAnalyticsView`** (~15 uncached shared-schema aggregates) via the existing
  `get_or_build_single_flight` helper, TTL 45s. Verified the view reads **zero request inputs** (all
  `SHARED_APPS` models, one physical table each), so a single global key is provably collision-free.
- **#301 — frontend cold-load.** A build-time Vite `modulepreload` for the hashed EN i18n chunk (fetches
  in parallel with the whole static graph instead of gating `app.mount()`), and Sentry Replay now
  lazy-loads via `lazyLoadIntegration` only when replay sampling is on (recorder no longer ships on 100%
  of loads).
- **#299 — `enforce_subscriptions` cron** batched from up to 2N `Subscription` queries to 2 (set-membership
  against the exact same `valid_filter(today)` predicate).
- **#304 — `bulk_create` order lines** at both placement paths (storefront + dine-in append), shortening
  the `select_for_update` lock-hold. Safety re-verified: no `OrderItem` `save()`/signals, flat item dicts
  (options/combo are inline JSON, not child rows), instances discarded downstream; bound by `order_id` to
  keep mock-based tests green.

**Two findings correctly NOT shipped as-is** (downgraded during implementation, not blindly applied):
the password-reset session scan (#299 investigation) is **already a no-op in prod** — sessions live in
Redis (`SESSION_ENGINE=cache`), not the DB table it scans — and removing it would drop a documented DB-
fallback security backstop for zero prod gain, so it was left as-is; and one audit false-positive (a
"Node-26 build unvalidated by CI" claim) was refuted in the audit itself (the `docker` CI job builds the
real Dockerfile).

**Two owner/ops caveats to fold into deploy** (documented here, not blockers):
1. **Concurrent-index migrations (#297, #298) + the staging rehearsal.** Both use
   `AddIndexConcurrently` + `atomic=False` per [`backend/MIGRATIONS.md`](../backend/MIGRATIONS.md). Both
   tables are `SHARED_APPS` (public schema, built **once** via `migrate_schemas --shared`) — the safer
   ×1 case, **not** the tenant-provisioning/`auto_create_schema` path the doc's gate warns about. Still,
   include them in the owner's next **staging-migration rehearsal** (confirm the shared migrate step is
   transaction-free on a real Postgres) before prod deploy, alongside the existing concurrent migrations
   already on `main`.
2. **Sentry Replay CSP (#301).** `lazyLoadIntegration` pulls the recorder from the Sentry CDN. Replay is
   dormant today (sample rate 0); if an operator later **enables** it, they must allow-list
   `browser.sentry-cdn.com` under the strict `script-src 'self'` CSP. The always-shipped-recorder waste is
   fixed unconditionally regardless.

**Coverage-gap follow-up (same session, → 3 more fixes #306–#308).** The 31-agent pass was honest that
three categories weren't covered that round; a focused 3-finder read-only follow-up closed them:
- **Frontend runtime** (render/reactivity): confirmed the hard parts already exemplary (Leaflet lifecycle,
  visibility-aware bounded polling, 30s tickers, server-paginated admin tables), and found **two systemic
  wins shipped** — **#306** caches `Intl.*Format` instances in the shared formatters (they were constructing
  a new CLDR-resolving formatter on *every* call from `v-for` bindings — ~300/render on a 150-dish menu;
  util placed in `src/lib/` per convention), and **#308** stops the marketplace menu re-rendering the whole
  catalog every second during a flash sale (the 1s countdown ref lived in the parent template — moved the
  ticker into its banner child, preserving the exact `flash_sale=null` sale-end side effect via an `@ended`
  emit) + debounced the two un-debounced menu searches (~180ms).
- **Backend serializer/hot-path depth**: a near-clean bill of health (menu catalog, order/driver/ride lists,
  marketplace, WebSocket consumers, sweeps all already batched/cached); **two misses shipped as #307** — a
  `(status, delivered_at)` composite index on `DeliveryJob` (the `reconcile_driver_earnings` cron was
  scanning *every delivered job ever* + sorting in memory every ~15 min on a terminal, ever-growing bucket)
  and a one-line `HappyHourSerializer.get_category_ids` fix (`.values_list()` bypassed its own prefetch).
  The new index is the same safer `SHARED_APPS` ×1 concurrent-index case → same staging-rehearsal caveat.
- **Docker/image + dependency weight**: **re-verified clean** — every prior hosting optimization intact
  (build-tools purged from the backend image, `CONN_HEALTH_CHECKS`, uvicorn worker tuning, per-service
  memory limits, gzip/immutable-cache nginx, dynamic-import leaflet/qrcode/Sentry, correct dev/prod dep
  split). No autonomous fix; the findings are **owner/ops judgment calls**, recorded for the owner:
  dormant `boto3`/`django-storages` (~90 MB image weight; S3 off by default — slimming changes the
  S3-enable deploy contract, a roadmap call), a uvicorn `--preload`/COW **RAM lead** that needs staging
  testing (preload can break Channels/DB-at-import forks), a Redis `maxmemory`/eviction-policy gap
  (shared cache+broker+channels, so no naive LRU), and a non-perf **test-parity flag**: prod runs Python
  3.14 while local/CI run 3.12.

**Verification:** every PR green on all CI jobs (backend, frontend, docker, e2e, Trivy) before merge; the
async-notification, reservation-count, and flash-sale-refactor diffs were hand-reviewed for content/scope
parity. Backend suite **5042 passed, 0 new failures** across the campaign (the 1 local
`test_pinned_against_django_5_2` failure + ~82 DB-connection errors are the known local baseline). **Not
yet deployed** — deploy is manual (Coolify); the concurrent-index staging rehearsal + Sentry-Replay CSP
caveats apply at deploy time.

---

## 2026-08-29 — owner-decisions closed out (final 6 of 12 → all 12 shipped)

**Result:** `main` @ `3868224`, green. On the owner's "go with your recommendations," the remaining **6
owner-decision items** were implemented on the engineering recommendation, each a CI-gated PR with tests —
so **all 12 owner-decisions from the hardening sweep are now resolved**:

- **#2 — platform `driver_owed`** (PR #290): fixed to the direct liability `Sum(wallet_balance) over
  is_driver` (Option A), and `driver_paid = Sum(CASHOUT)`. (Corrected from the doc's original "add CASHOUT
  to DriverPayout", which would double-count since #227 makes every payout also a CASHOUT tx.)
- **#7 — transfer/merge audit** (PR #289): kept section-agnostic (managers legitimately consolidate across
  floor sections — no `_can_access_order` gate) but now emit a post-commit audit log of the actor + order
  ids + item count, mirroring void/comp's actor capture.
- **#11 — clock-in for payments** (PR #288): the clock-in guard now gates all four payment paths
  (`payCash`, `payWallet`, and the independent `payCashForSeat`/`payWalletForSeat` seat-split variants — the
  latter two caught in review as they bypass the first two).
- **#1 — ride typed-address dead-end** (PR #292): added a dedicated pickup Leaflet map (tap-to-pin) and an
  explicit stuck-estimate prompt naming the missing pin, replacing the permanent "Calculating…".
- **#5 — ride map a11y** (PR #292): both pin-setting maps changed from `role="img"` to `role="application"`
  with descriptive labels; non-map paths (use-my-location, saved-address chips) confirmed keyboard-reachable.
- **#3 — stuck `in_progress` recovery** (PR #291): sweep rule broadened to auto-cancel a trip whose
  APPROVED driver went absent past a generous, kind-aware window (ride 2h / package 8h; online+fresh drivers
  never touched), plus an `IsPlatformAdmin` `POST /api/admin/rides/<id>/force-resolve/` (cancel, or complete
  via the existing `settle_ride` path that skips paying a revoked driver).

Rides items #1/#3/#5 are the concrete pre-go-live blockers, now cleared (rides remain `VERTICALS_ENABLED`-
gated). **Follow-ups noted (not blocking):** an `AdminRides.vue` button for the #3 endpoint, and a keyboard/
geocoding path to set a ride drop-off pin without a saved address (#5 residual — geocoding was scoped out).

---

## 2026-08-28 — owner-decision implementation (6 of 12 resolved + a flaky-test fix)

**Result:** `main` @ `5b226e0`, green. The 12 owner-gated findings from the sweeps were packaged into a
decision doc ([`OWNER_DECISIONS.md`](OWNER_DECISIONS.md), PR #279) — each a yes/no (or A/B) call with an
engineering recommendation. The **6 that were clear correctness/safety calls** (not genuine
business/policy questions) were then shipped on the recommendation, each a CI-gated PR with tests:

- **#4 — overnight business hours** (PR #281): the editor + `tenancy/openstate.py` rejected/miscomputed a
  window whose close is earlier than open (e.g. 18:00–02:00). Now a real wraparound representation on both
  ends (`current >= open OR current < close`).
- **#6 — comp keeps loyalty points** (PR #280): documented the intentional policy (comp = goodwill, guest
  keeps points, unlike void's clawback) and corrected the docstring that falsely claimed void-parity.
- **#8 — driver revocation cascades to in-flight DELIVERY jobs** (PR #282): the revoke branch now clears
  the driver and redispatches active jobs (SEARCHING + offer reset), the delivery analog of the ride fix
  in #276.
- **#9 — durable voucher-batch idempotency** (PR #282): new `VoucherBatch` model with a unique
  `idempotency_key` claimed inside the create transaction (cache stays a fast-path; DB is the authority),
  so an evicted cache can't let a retried batch double-mint.
- **#10 — P2P transfer recipient confirmation** (PR #283): a confirm step showing amount + typed number
  before sending, and the resolved recipient surfaced in the success message.
- **#12 — FR ASCII-only enforced** (PR #284): de-accented ~405 `messages-fr.js` value lines and added an
  FR-only accented-char check to `verify:i18n` so it stays enforced (Arabic untouched).

Plus **#285** de-flaked the MFA backup-code test: two "a code fragment must not be a substring of the
pbkdf2 hash" assertions collided by chance with the fixed `$1000000$` iteration count (and random base64)
in every hash — replaced with a deterministic `check_password` proof.

**Left for the owner (6):** #1/#3/#5 (rides go-live), #2 (`driver_owed` reporting semantics), #7
(floor-section ops policy — rec is leave-as-is), #11 (clock-in labor policy).

---

## 2026-08-28 — post-sweep DEEP money/concurrency audit (7 defects the breadth sweep missed → 3 fix PRs)

**Result:** `main` @ `f30fbc6`, green. After the 2026-08-27 breadth-first sweep drained its autonomous
backlog, a focused *deeper* pass — 3 read-only finders (money/ledger end-to-end trace, concurrency +
a regression re-check of the 30 just-shipped PRs, data-integrity/tenancy), each adversarially
self-verified — found **7 real, currently-present defects the breadth-first sweep missed**, including a
**HIGH silent revenue leak** and a **regression introduced by #273**. Shipped as 3 individually
CI-gated PRs (#275–#277), each with mock-based regression tests. Lesson recorded: a depth-first pass
on the highest-stakes surface (money/concurrency) catches what a breadth-first lens does not.

**What shipped:**
- **HIGH — silent revenue loss (#277):** the void/comp "Case B" auto-settle predicate double-counted a
  wallet payment (a split-bill wallet pay writes BOTH a `method=WALLET` `OrderPayment` row AND bumps
  `order.wallet_amount_paid`), so an UNPAID order with a partial wallet payment could be flipped to PAID
  for **less than it collected** (e.g. 60-of-100, void a 10 item → `60+60≥90` → PAID, writing off 30).
  Both `StaffVoidOrderItemView` and `StaffCompOrderItemView` now use the reconciling `_order_collected()`
  helper (each wallet payment counted once).
- **MED — referral double-grant (#277):** the direct-checkout referral reward was the one loyalty sibling
  never given the concurrency guard (stale-snapshot check + unconditional credits). Now a compare-and-set
  on `referral_reward_given` (referrer credited only when the CAS claims the row).
- **LOW — cancel over-refund (#277):** `refund_and_cancel_delivery_order` read `wallet_amount_paid` from
  a pre-lock snapshot; now reads it from the locked row.
- **LOW-MED — cash-out cancel clobber (#275):** `DriverCashoutCancelView` was an unguarded check-then-act
  that could write CANCELLED over a just-committed PAID row; now a `status=PENDING`-guarded compare-and-set
  (409 on already-resolved).
- **LOW — cash-out EXPIRED regression from #273 (#275):** #273 moved the EXPIRED write to a deferred
  *unlocked* save, opening a concurrent-expiry clobber window; moved back INSIDE the lock as a guarded
  update (kept #273's raise-after-block + no-brute-force-count properties).
- **MED (latent) — revoked driver stranded their own `in_progress` trip (#276):** `_get_driver`'s
  `driver_approved=True` gate made a held trip un-completable after revocation (rider can't cancel, sweep
  never touched `in_progress`) → pinned forever, fare unsettled, rider locked out. `DriverRideStatusView`
  now lets ONLY the assigned driver complete/abandon a held trip even after revocation (accept still gated;
  money still safe via `_do_settle`'s revoked-skip); + sweep rule (e) backstop. Inert until rides go live.
- **minor sec — handover-code lockout (#276):** the ride package-code lockout reset the attempt counter
  (weaker than the delivery path, which deliberately doesn't); matched to the delivery path.

**Verified clean** (no findings): wallet debit/credit idempotency + lock re-checks, transfers, tenant-float
credit, `record_driver_payout`, `settle_ride`, drawer, voucher, and — from the concurrency + data-integrity
finders — the 30-PR campaign's own changes (loyalty lock, comp CAS, no-show gate, overcharge recompute,
order-store guard), shared-schema tenant isolation, migrations (rolling-safe), and serializer contracts.

**Note:** the deferred LOW `MAD`-currency display cluster is confirmed **owner-gated, not autonomous** — the
admin/platform pages render cross-tenant public-schema records that carry no per-record currency field, so
hardcoding `MAD` is correct today and changing it is part of the owner's mixed-currency aggregation decision.

---

## 2026-08-27 — super-app hardening sweep (118-agent audit → ~29 CI-gated fix PRs)

**Result:** `main` @ `9685363`, green. A full read-only audit (`superapp-hardening-sweep`, 118 agents:
22 finders × every lens across all four surfaces, each finding adversarially verified against the real
code) produced **94 verified findings** (backlog: [`HARDENING_SWEEP_2026-08-23.md`](HARDENING_SWEEP_2026-08-23.md),
PR #242). The **autonomous-safe** findings were then fixed in six delegate-and-gate waves — worktree-isolated
agents partitioned by disjoint files, each PR individually CI-gated + merged (money/security diffs reviewed
by hand). Only the LOW `MAD`-currency display cluster (7 files, single-MAD-correct today, overlaps the
owner-gated mixed-currency work) was deliberately deferred; the 12 owner-decision findings are left for the
owner.

**What shipped (by theme):**
- **Money / concurrency (backend):** loyalty birthday/first-order double-grant on direct checkout (#246),
  comp double-tap double-decrement (#246), no-show pay to a since-revoked driver (#246), marketplace
  promo-cap+loyalty overcharge race (#245), admin wallet-bonus double-credit on no-key retry (#245),
  negative delivery-fee/payout guard (#245), ride-payout approval re-check (#243), durable EXPIRED cash-out
  that no longer counts as a brute-force failure (#273).
- **Security / authz:** owner post-login open-redirect via `next` (#244), ProfileView write guard (#243).
- **Correctness:** marketplace dish-option composite cart key + checkout-drawer line targeting (#248, #256),
  rides-sweep re-pool dispatch-clock reset + deferred package tracking SMS (#255), Cart delivery-min no
  longer blocking pickup/dine-in (#249), order-poll in-flight guard (#269), driver code-submit
  double-submit guards (#269, #271), OwnerPromotions late-meta form hydration (#259), CustomerAccount
  birthday-save wrong-field wipe (#257), completed-order stale ETA gate (#261), service-worker per-push
  notification tags (#262).
- **UX / error-handling:** marketplace failed-delivery banner parity (#247), waiter-store retry false
  "all caught up" (#251), driver offer-modal error visibility (#252), Z-report drawer + kitchen offline
  silent failures (#258), ratings fetch-error state (#259), recipient-track poll banner (#264), auth
  OTP-length + confirm-password (#260), stale-customer-session redirect fix (#257), destructive-action
  confirmations for 86-all / tenant-reactivate / plan-flag / car-doc-reject / ride-fare (#263, #270),
  owner analytics clickable KPI + notif "all-time"/cap labels + cart subtotal reconciliation (#272),
  ride/rider push NotificationLog (#273).
- **a11y / i18n:** owner light-theme badge contrast (#250), 44px touch targets across review/driver-rating
  stars, kitchen pills, cart/waiter/ride controls (#266, #267, #268), modal close-button names, valid
  interactive nesting, form `aria-describedby`, recipient-track live region (#264, #268), RTL logical
  properties (#257, #266), untranslated "scheduled" + promo pluralization + rating format (#265).
- **Launch-prep (earlier same session):** HSTS emitted from nginx on static/SPA responses (#241).

**Remaining from the sweep:** the deferred LOW `MAD`-currency display cluster, plus 12 owner-decision
findings (product/policy calls) catalogued in the backlog doc. Not started autonomously.

---

## 2026-08-17 — §4.F hardening-decisions closure (8 of 9 owner-flagged items shipped)

**Result:** `main` @ `42f37f9`, green (all CI jobs pass). The 9 owner-decision items the 2026-08-16 gap
scan surfaced (NEXT_SESSION §4.F) were worked through one at a time; **8 shipped** as individually
CI-gated PRs (#227–#234), each with regression tests. The 9th is a genuine product decision left for the
owner.

**What shipped:**
- **Money (4):** `#227` driver-payout double-booking — `record_driver_payout` now DEBITS the driver's
  wallet, so a direct admin settlement and a restaurant cash-out extract the SAME balance (double-pay
  structurally impossible). `#228` transfer/merge of a partially-paid table — `StaffTransferItemsView` /
  `StaffMergeOrdersView` reject a source carrying collected payment (`source_has_payment` 409) instead of
  cancelling it and stranding the money. `#229` wallet self-pay over-charge — `CustomerOrderPayWalletView`
  reconciles the OrderPayment ledger via a shared `_order_collected()` under an order lock, charging only
  the true remainder. `#230` no-show + redispatch double-pay — a `NOSHOW_PAID` job (by resolution or the
  `noshow:` wallet ledger row) is refused redispatch.
- **Display / UX (3):** `#231` currency — `formatPrice` always 2 decimals (MAD no longer rounded to whole
  dirhams, so cart lines reconcile with the total). `#232` ETA anchoring — new `Order.estimated_ready_at`
  (migration 0077) stamped `now + minutes` on every ETA write; both consumer countdowns anchor to it,
  fixing an ETA set/edited long after placement. `#233` failed-delivery status — `OrderStatus.vue` shows a
  coherent "delivery issue" pill + banner instead of "Out for delivery" contradicting the driver card's
  red "Failed".
- **Correctness (1):** `#234` ride + delivery double-booking — both accept endpoints enforce a
  cross-vertical capacity check under the Customer-row lock (a driver can't hold a ride and a delivery at
  once). Inert until rides go live.

**Process.** Sequential single-item PRs (fix → regression tests → local verify → CI-gate → merge → mark
§4.F resolved). Two money PRs (driver-payout, wallet self-pay) needed extra CI rounds to flush out sibling
tests that shared a never-credit-the-wallet / no-mock assumption — the exact pattern the gap scan
predicted. A stacked-branch mistake (items 5/6/7 branched off the same `main` before #231 merged) caused a
NEXT_SESSION §4.F merge conflict; resolved by hand + `rebase --onto` to drop an already-merged commit.

**Lessons.** (1) A shared reconciliation helper beats per-endpoint money math — the wallet-ledger
"already collected" and the driver "single balance" bugs both came from two code paths disagreeing on one
definition. (2) Sequential PRs that edit the same doc section must be based on the latest merged `main`,
not branched in parallel, or the doc conflicts. (3) Adding a model query to a view breaks every no-DB test
that reaches it — budget for mocking the new query (and `transaction.atomic`) in each affected test class.

**Left for the owner:** §4.F item 8 — whether to MANDATE a photo for a code-less DELIVERED completion (the
security bypass itself is already fixed, #222). Product-policy call, not a defect.

---

## 2026-08-16 — Full-app hardening campaign (adversarial gap scan → 22 fixes)

**Result:** `main` @ `7629db9`, green (all CI jobs pass). A **45-agent adversarial gap scan** across the
whole app (money, tenancy, security, the four surfaces, content/i18n, coherence, structure) found 34 →
**32 confirmed** (2 false claims killed by per-finding verification). The **22 safe-autonomous** fixes
shipped as 4 file-partitioned, gate-verified PRs; the **9 owner-decision** items + 1 structural are
captured for the owner (NEXT_SESSION §4.F). Full record: [`HARDENING_GAPS.md`](HARDENING_GAPS.md).

**What shipped (#222–#225):**
- `#222` **accounts** — **SECURITY:** a driver could bank a payout + mark a COD order paid by PATCHing an
  arbitrary `proof_photo_url` with no delivery code; now only a server-saved, Pillow-validated FILE
  satisfies proof-of-delivery. Plus a #220-class marketplace-cancel race (lock + `newly_cancelled` guard +
  stand the driver down), the dead marketplace ETA countdown (payload now ships `created_at`), and
  analytics realized-basis (exclude CANCELLED from "active"; fee/payout sums delivered-only).
- `#223` **services** — owner-completion re-checks driver approval under the lock (OPS-5f), so a revoked
  driver isn't paid; MFA-disable is finally audit-logged (`log_admin_action(detail=…)` raised a swallowed
  `TypeError` → `metadata=` + `request=`).
- `#224` **menu** — three concurrency guards: customer-cancel race (mirrors #220), void-item race (atomic
  compare-and-set `UPDATE … WHERE is_voided=False` gated on rowcount), clock-in race (per-`(schema,user)`
  advisory lock); a **cross-tenant loyalty IDOR** guard (loyalty_points is one global balance → gate the
  owner grant on an ordered-here check) + the same gate on customer-notes; receipt coherence (comped lines,
  voided-count parity, `Profile.phone`) and swallowed-exception logging.
- `#225` **frontend** — marketplace "Order again" now carries selected options + notes and revalidates them
  against the live menu (was hard-failing checkout on must-customize dishes + silently dropping paid
  extras); `?tab=profile` deep-link, localized aria-labels, operator `payment_short` reason, `{days}`
  analytics title.

**Process.** Scan = one Workflow (10 finder lenses → dedup → per-finding adversarial verify → synthesis).
Fixes = 4 worktree-isolated agents partitioned by owner file (disjoint → no merge conflicts), each with
regression tests; the main loop kept the diff-review/CI/merge gate. **Two things were caught at the gate:**
a `NameError` in the proof-photo fix (uninitialized var on the no-photo path → would 500 every normal
delivery) and confirmation that the 8 modified menu tests were honest adaptations, not weakenings.

**Lessons.** (1) A verify-every-finding scan is worth it: it killed 2 plausible-but-wrong findings and
surfaced a real security bypass + a cross-tenant IDOR that three prior campaigns missed. (2) Delegated
worktree agents get you parallel coverage, but the diff/CI/merge gate is non-negotiable — one agent's fix
had a 500-on-every-delivery regression that only a human read caught. (3) Don't hand-edit a worktree while
its agent may still be alive (a concurrent edit produced a duplicate line, cleaned up before merge).

**Deferred:** the Arabic back-arrow glyph (low). **For the owner:** see NEXT_SESSION §4.F.

---

## 2026-08-12 — Operational-gaps closure + big-test QA sweep

**Result:** `main` @ `7e5df0f`, green (all CI jobs pass on Django 5.2.17). **4 PRs** (#217–#220). Closed the
four remaining flagged UX gaps, made four owner-delegated money/product decisions, then ran a **"big test of
every part"** — automated CI plus a two-agent read-only review across all four surfaces — which caught and
fixed one concurrency bug.

**What shipped:**
- `#217` — **the four flagged UX gaps** (NEXT_SESSION §4.B): the waiter floor-tile "+ New order" now shares
  the toolbar's **clock-in guard**; consumer qty-steppers get a 44×44 hit area (`ui-tap-expand`) meeting the
  touch-target gate without density change; the desktop nav gains **Account**; the marketplace slot is
  relabeled **"Order" → "Browse"** (all three locales).
- `#218` — **two owner-delegated money decisions.** (1) **Commission basis → POST-discount:** checkout bills
  `rate × max(0, food − promo − loyalty)` via a new shared `menu/commission.py` (`commissionable_food_base` +
  `COMMISSIONABLE_STATUSES`), used identically by checkout, the owner statement, and analytics so they can't
  drift (analytics also gained the missing `out_for_delivery` status — a latent under-count). (2)
  **Stuck-delivery auto-refund:** `sweep_delivery_jobs` now auto-refunds a **pre-pickup, provably-
  unfulfillable** job past `Profile.delivery_auto_refund_minutes` (default 30, `0` = off), reusing the shared
  idempotent refund helper and re-verifying "not picked up" under a row lock.
- `#219` — **no-show payout display:** the owner's no-show confirm now echoes the real `driver_payout` the
  backend pays, not the gross `delivery_fee`.
- `#220` — **the big-test fix.** The verification sweep caught a LOW-severity concurrency defect: the shared
  `refund_and_cancel_delivery_order` checked its cancel-guard on an **unlocked** in-memory order, so a true
  sub-second overlap (a manual refund racing the sweep, or two owner taps) could double-apply the two
  non-idempotent side effects — loyalty claw-back + inventory restock. Fixed by re-reading the order under
  `select_for_update` and branching on the locked row (the wallet credit was already keyed-safe, never
  double-credited). Plus the sweep now counts/alerts off the helper's return value, and a stale commission
  comment was corrected. Two new regression tests.

**The big test.** (1) *Automated:* full CI green on final `main` — backend DB suite + e2e + frontend
(~993 tests) + Docker + Trivy, all on Django 5.2.17 with every change layered in. (2) *Review sweep:* two
read-only agents (money/Django integration; end-to-end flows on all four surfaces) verified Django 5.2, the
commission-basis switch, the auto-refund, the no-show fix, and every surface flow as **correct with zero
regressions** — surfacing only the one concurrency bug, which #220 fixed.

**Flagged, not fixed:** the void-item commission recompute (`StaffVoidOrderItemView`) still uses the
pre-discount line-sum basis — aligning it with the new post-discount checkout needs an owner decision on
allocating an order-level discount across voided lines (NEXT_SESSION §4.D). **Deferred (owner-gated):** the
three structural phases (unified cart / offline POS / driver surface) — all money-path, reviewed and left for
deliberate staging (§4.E).

**Lessons.** (1) A final "big test" review sweep earns its cost: automated CI plus a focused adversarial read
across surfaces caught a real concurrency defect that per-PR review and green CI both missed. (2) Check-then-
act on an **unlocked** read is a race even when each side effect looks individually gated — put the guard
behind the same row lock the mutation uses.

---

## 2026-08-10 — Dependency-security unblock + Django 5.2 LTS upgrade

**Result:** `main` @ `3e25974`, green. What began as continued super-app work surfaced an escalating
CI-security situation: over a multi-day gap, newly-published advisories reddened every CI gate on `main`
and every PR, blocking all merges. Resolved by *fixability*, then by eliminating the root cause.

**What shipped:**
- `#206` — marketplace reorder now drops sold-out items (the one safe Phase-3 increment; a scoping pass —
  NEXT_SESSION §4.E — found consumer coherence is ~80% done, the rest owner-gated/structural).
- `#207` — Phase-3 consumer-coherence scoping captured.
- `#208`, `#213` — **CI-security unblock.** Handled each advisory by whether an in-range fix exists:
  **FIXED** the frontend `nanoid` HIGH (bumped to 3.3.18 via an npm override — a proper fix, not a mask);
  **DEFERRED** (documented, temporary) the dev-only js-yaml/brace-expansion advisories and the six
  **all-Low** Django CVEs with no in-range fix (EOL Django). Verified the gates clean locally.
- `#214` — recorded the EOL-Django security clock as the top priority in the handoff docs.
- `#215` — **Django 4.2.30 → 5.2.17 LTS.** Got the backend off end-of-life Django. Small/surgical (the
  stack was already 5.2-ready — django-tenants 3.10.2 / DRF 3.17.1 / Channels 4.3.2 needed no bump; only
  `make_random_password` [removed 5.1] and `django.utils.timezone.utc` [removed 5.0] usages changed) and
  removed the six CVE deferrals (5.2.17 fixes them). Validated end-to-end in CI — full DB suite on real
  Postgres + e2e + Docker, no model drift. Owner made the final merge.

**Lessons.** (1) EOL frameworks are a security *treadmill* — deferring their CVEs is a bandage; the fix
is the upgrade. (2) Split advisories by *fixability*: bump what has an in-range fix, defer only the
genuinely-unfixable (and only when Low / non-exploitable), never silently. (3) A major framework upgrade
run branch-first + CI-gated (full DB + e2e), with the owner making the final merge, lands with zero risk
to `main`.

**Flagged, not fixed:** the dormant schema-pinned `SessionStore` doesn't cover Django 5.x's async session
path — pin it before activating under ASGI (see NEXT_SESSION §4.C).

---

## 2026-08-05 — Super-app hardening campaign (money correctness + coherence + robustness)

**Result:** `main` @ `fcdf75b`, green (all CI jobs pass). **6 PRs** (#199–#204). Triggered by an
uncommitted fix found while reviewing a stale worktree, then driven by **4 parallel read-only audits**
(money-correctness, cross-side coherence, consumer-conversion, operator-money) — plus a follow-on
**calibration pass** (driver flow, onboarding→first-order, retention, cross-cutting resilience) that
confirmed the app is otherwise production-grade but surfaced a tail of 8 real flow/resilience bugs. Each
audit → a prioritized [CODE] backlog → gate-verified themed PRs (delegate-and-gate: worktree agents
implement + run the full frontend gate, the main loop reviews every money/checkout diff and merges only
on confirmed CI green).

**What shipped:**
- `#199` **money — refund tenant-scoping.** `MarketplaceOrderCancelView` refunded without `tenant_id`,
  so marketplace-cancel refunds landed as `tenant_id=None` and dropped out of the tenant's refund
  reports (Z-report filters on `tenant_id`). Recovered from a stale worktree, verified still-live on
  main, shipped with a mock regression test. The money audit then confirmed this was the ONLY instance
  of that cross-plane class (~30 money call sites enumerated).
- `#200` **money — Stripe webhook fail-closed.** The dormant PSP top-up webhook parsed RAW UNSIGNED
  JSON and credited the wallet when `PSP_STRIPE_WEBHOOK_SECRET` was empty — enabling PSP in prod
  without the secret would let a forged event mint unlimited credit. Now fails closed (503) outside
  DEBUG; the unsigned path is DEBUG-only. Reconciled `ARCHITECTURE.md` §7 (MONEY-2/3 already fixed).
- `#201` **money-UX — confirm amount/identity echo.** Operator money confirms now say *how much* and
  *which tenant*: the HIGH fix — tenant Suspend/Cancel prompt names the tenant (a mis-tap on the dense
  grid used to terminate a restaurant with a generic prompt); refund/no-show/voucher confirms echo the
  amount; bonus/top-up/credit gained an amount+identity confirm (mirroring `fundFloat`).
- `#202` **coherence — reconciling receipts + fulfillment-aware status.** Customer receipts derived
  "Subtotal" as `total − delivery_fee` and omitted the tip, so a tipped order never reconciled; now the
  subtotal inverts the backend total identity and the rendered rows (Subtotal + Delivery + Tip − Promo −
  Loyalty) sum to total *exactly* (locked by an algebraic-identity test). "Ready" is now fulfillment-aware
  (delivery → "Ready to dispatch", dine-in → "Served") across trackers/pill/global-bar/account-timeline.
  Additive backend fields (`tip_amount`, `promotion_discount`) added to the customer order-status payloads.
- `#203` **marketplace — checkout robustness.** GPS-denied delivery was a hard dead-end (no way to set
  coords without geolocation); now a paste-map-link + manual-coordinate fallback (parity with the tenant
  Cart), gated on `validCoord` (which also fixes a latent null-island `(0,0)` bug). Plus per-field
  validation with scroll-to-field, 404-vs-transient on the tracker, localized loyalty/schedule errors,
  a guest `use_wallet` gate, and a load-more toast. Shared coord-parse helpers extracted to
  `lib/deliveryPricing.js`.
- `#204` **flow + resilience — 8 bugs from the calibration pass.** *Onboarding:* the post-publish
  "Edit Menu" CTA dead-ended (it linked to the wizard, which redirects already-published tenants to the
  dashboard) → repointed to the menu builder; the **Publish** button rendered a blank noun
  (`catalog.value` is `undefined` in a `<script setup>` template) → dropped `.value`. *Flow:* a driver
  approved **mid-session** got an inert dashboard (bootstrap ran only in `onMounted`) → extracted into a
  guarded fn + `watch(approved)`. *Resilience:* a non-404 first-load failure on the post-checkout
  `OrderStatus` page left a **permanently blank screen** → added a retryable error card (same for
  `RecipientTrackPage`); sign-out and closure-date delete gained double-submit guards.

**Queued for the owner** (surfaced by the audits; each needs a decision, not code):
- No-show driver payout confirm echoes `o.delivery_fee` — confirm the backend pays exactly that.
- Two commission reports use different status filters (both exclude CANCELLED, so no refund over-billing)
  — confirm the intended PENDING/SCHEDULED/OUT_FOR_DELIVERY treatment.
- Marketplace checkout doesn't collect tips today (the receipt tip line is future-proof/dormant).
- Pre-PSP-launch: set `PSP_STRIPE_WEBHOOK_SECRET` — the webhook now refuses to run without it in prod.

**Follow-up (Phase-3 consumer-coherence scope).** A read-only scoping pass found consumer coherence is
**~80% already shipped** and the headline "unify the carts / front-ends" is **architecturally owner-gated**:
the storefront and marketplace run on **different origins**, so a unified cart needs a **server-side cart**,
not a frontend refactor. Shipped the one safe increment the scope surfaced — `#206` (marketplace reorder now
**drops sold-out items** instead of seeding a checkout-blocked cart). The structural remainder (server-side
cart, server-backed dish favorites, shared-checkout-composable) is captured in
[`NEXT_SESSION.md`](NEXT_SESSION.md) §4.E.

---

## 2026-08-05 — Documentation onboarding-completeness pass

**Result:** `main` @ `9d16935`, green. A docs-only campaign to make the doc set complete + accurate
enough that a fresh session/AI can onboard fast **without absorbing already-fixed debt as current**.
No code touched.

**What shipped:**
- `#196` — synced the two handoff docs to the merged #193–#195 (SHA/PR-count; removed the three
  now-shipped items from the `NEXT_SESSION.md` backlog).
- `#197` — **the substantive one.** Driven by two read-only audit agents (doc-set authority map +
  code→feature map), whose load-bearing claims were verified against source before writing (caught one
  agent error: `OwnerBilling.vue` is a live tab inside `OwnerProfile.vue`, not orphaned):
  - **New [`FEATURE_MAP.md`](FEATURE_MAP.md)** — the missing current-state surface inventory
    (routes/pages, models, endpoint groups per surface; capability seam; **built-vs-dormant**
    PSP/rides/retail; load-bearing config toggles). Wired into `README.md` read-order + `CLAUDE.md`.
  - **Currency fixes to `ARCHITECTURE.md`** (a 2026-07-10 snapshot that predated shipped refactors):
    i18n is single-source (FE-1 deleted `messages.js`), not dual-source; **AUTHZ-1 + IDENTITY-1 keystone
    shipped**, not "#1 liability, change planned"; **FE-2 decomposed the mega-pages**. Reconciled
    §5/§9/§12/§13/§14 against `RISK_REGISTER.md`.
  - **`README.md`:** fixed the index bug that listed the dead `platform/` Node scaffold as authoritative
    Coolify docs; updated ADR-0004/0005 verdicts; added a "Superseded — do not trust" table.
  - **`⚠️ SUPERSEDED` banners** on the 3 worst factual-misleaders (`PLATFORM_VISION.md` — a nonexistent
    JWT session + nonexistent Django apps; `platform/README.md` + `platform/DEPLOY_COOLIFY.md` — the dead
    Node scaffold).
- **Repo hygiene:** pruned **6 stale git worktrees** (non-force — branches preserved, only working copies
  removed). One (`.claude/worktrees/happy-goldwasser-dec544`) was kept because it has uncommitted files;
  see `NEXT_SESSION.md` §5.

**Lesson:** the canonical `ARCHITECTURE.md` had a `> this document wins` header but predated the
2026-07-27 round-2 merge — so on identity/authz/i18n/mega-pages it was the *stalest* canonical doc, not
the most authoritative. Dated "currency pass" stamps + a "when this and RISK_REGISTER disagree, the
newer wins" note now guard against that. **A snapshot doc claiming primacy is a trap once code moves.**

---

## 2026-08 — Daily-use, reliability, product-content & flow campaign

**Result:** `main` @ `d231144`, green (frontend lint/build/vitest + backend pytest + e2e + Docker
all pass in CI). **27 PRs merged** (#169–#195; #193 is this handoff-doc set). No PR left open except
4 deferred Dependabot majors (#147 stripe, #148 eslint, #151 django, #154 tailwind — see
`NEXT_SESSION.md`). App is code-complete for everything shippable without an owner decision or
external prerequisite.

**Context:** started from a directive to "guide the app toward a fast, easy-to-navigate, daily-use
super-app + POS." Early finding that reset the plan: **speed was already done** (the June
`PERF_HOSTING_AUDIT.md` backlog had been fully implemented by the marketplace rebuild — marketplace
response caching, `rating_avg` denormalization, indexes, `CONN_HEALTH_CHECKS`, Docker slimming,
`leaflet`/`qrcode` code-splitting, query folds, throttles), and **navigation was already
well-architected** (frequency-based IA, KeepAlive, idle prefetch, capability-gating). So the campaign
pivoted from "make it fast" (done) to daily-use quality, reliability, super-app coherence, and —
after owner decisions — conversion/activation and flow.

### What shipped, by theme

**Daily-use quality — all four operator/consumer surfaces** (audit-driven; three read-only audit
agents on waiter/owner/consumer, then four more on driver/admin/kitchen/consumer-hub):
- `#169` waiter settle-sheet i18n (order-items label + seat count).
- `#170` wave 1: **live-order-miss fix** — the owner's "N new orders" banner switched `activeStatus`
  but not `activeTab`, so tapping it from the History sub-tab silently hid the banner without
  showing the live orders; also filter-strip token localization, an empty-cart checkout dead-end
  (posting a 0-total order), and a seat-split empty state.
- `#173` **hotfix** for #170: a duplicate `const fulfillmentLabel` in `OwnerOrders.vue` (parse error)
  reached `main` because CI isn't a required check — caught by CI post-merge, fixed forward. (See the
  discipline note below and `NEXT_SESSION.md`.)
- `#171` wave 2: promo day-label i18n, category/review aria-labels, cashier-modal a11y
  (aria-modal + Esc + focus), comp/void in-flight spinners.
- `#172` wave 3: dashboard "today" bucketed by **tenant timezone** to match the orders board;
  silent post-wallet-charge refresh (no skeleton flash).
- `#174` wave 4: marketplace option-sheet Tab focus-trap + focus-restore.
- `#175` wave 5 (kitchen): mark-all-ready in-flight guard (the one unguarded mutation → double-POST),
  44px wall-tablet touch targets, delivery-chip i18n.
- `#176` wave 6 (driver): offer Accept spinner; **Escape made inert** (a stray Escape was passing —
  declining — a time-critical exclusive offer = lost income).
- `#177` wave 7 (coherence): the persistent global live-status bar repointed to the canonical
  `orderStatus.*` labels so the same order no longer reads "Ready"/"On the way" there but
  "Ready for pickup"/"Out for delivery" on the trackers.
- `#178` wave 8 (admin): localized the cross-tenant live-order status (was leaking raw enum tokens),
  hid a decorative emoji from screen readers.
- `#179` wave 9 (admin operator): **17-key status-enum localization** across tenant lifecycle / lead /
  tier-upgrade / provisioning statuses (enum values derived from backend `TextChoices`),
  error-state-on-catch in AdminWallet/AdminCustomers, sign-out in-flight guard, `pts` i18n.
- `#180` consumer coherence: account order-row timeline pills unified with the status chip vocabulary;
  SuperAppHub activity badge given an sr-only label.
- `#181` driver wave 2: advance-error surfaced at the top of the sticky active-job hero (was
  off-screen below it); a **credential-free** "code active" indicator for a live cash-out (the
  6-digit code is never rendered in the header); stable availability-switch aria-label.

**Reliability (two owner-approved fixes):**
- `#182` offline status-advance no longer shows a false "update failed" — `advanceStatus`'s offline
  branch returns a frozen truthy `QUEUED_OFFLINE` sentinel (was `undefined`, tripping the caller's
  `if (!ok)` error). Money-adjacent (shared waiter store); diff-reviewed, settle path proven
  untouched, regression test added.
- `#183` kitchen "board not updating" staleness alarm — when the browser is online but the silent
  poll starts failing (server hiccup) the board froze with no signal; a top-bar alarm fires when the
  last successful sync is >45s old, mutually exclusive with the offline banner. (`waiter.lastSyncAt`
  already had the right semantics; the store change was a one-line comment + a page-side alarm.)

**Product decisions (owner-directed via structured questions):**
- `#184` marketplace follow-a-business vocabulary standardized on **Follow/Following** (the hub's
  wording), values-only edits to the existing `marketplace.*` keys — the separate "favourite dish"
  concept and internal identifiers (`is_favorite`, the localStorage key) were left untouched.
- `#185` consumer mobile bottom-dock now surfaces **Orders + Account** (replacing Contact/Business);
  routes verified (`customer-account` is `interface:"landing"`, no `requiresAuth`, degrades to a
  sign-in hero when signed out).
- `#186` account order totals show the **actual charged currency** (`formatCurrency(o.total,
  o.currency)`), matching the tracker/receipt, instead of converting to the display currency; wallet
  balance / ride fare / loyalty stay on display currency; EUR/USD regression test added.
- `#187` admin cross-tenant order currency (backend + FE) — `AdminTenantLiveOrdersView` now serializes
  each order's `currency`; the live-orders modal and customer cross-restaurant list format per-order.

**Product-content polish (a fresh "growth/activation" lens on top of the daily-use lens):**
- `#188` owner onboarding activation: reassuring, scoped brand-step intro with `(optional)` labels;
  fixed a factual "publish from step 5" misdirection; dropped meaningless launch-success vanity tiles
  and gave the Next-actions cards real descriptions; warmed the wizard footer; **wired up the resume
  banner** (`resumedFromStep`/`startFromStepOne` keys existed but were never rendered); Publish
  reassurance + a menu-group hierarchy explainer.
- `#189` consumer conversion: de-jargoned "Fulfillment" → "Pickup or delivery?"; **free-delivery
  upsell strip** ("Add {amount} more for free delivery"); **inline guest Sign-in button** (emits to
  the existing `CustomerAuthModal`); empty-menu & empty-following "Browse" exits; guest-pickup
  "Pay in person" reassurance; just-placed ETA in the confirmation; honest "View menu" reorder label;
  checkout input placeholders; **currency-neutral price-tier dots** (was hardcoded `€€` in a MAD
  market).

**Flow improvements (owner-directed):**
- `#190` onboarding flow: **Publish CTA moved to the top** of the final step (was buried under ~10
  config sections); the **unpublished-owner dashboard** focus card now says "Finish setup → Publish"
  instead of "All caught up" (new `computeNextAction` case guarded by strict `menuPublished === false`
  so a loading state never nags); the **business-type selector moved to step 1** (StepBrand, which
  already round-trips the profile — zero persistence change) so downstream steps adapt from the
  outset.
- `#191` checkout: **allow scheduled orders while the restaurant is closed** — backend verified to
  accept a `SCHEDULED` order when closed (the `restaurant_closed` 409 only fires for ASAP orders; a
  scheduled one is validated against future hours, saved `SCHEDULED`, released later with full
  notifications). The real dead-end was add-to-cart (dishes showed a "Closed" chip so no cart could
  be built off-hours) — fixed end-to-end via the shared, tested `classifyClosedOrderState` gate. Also
  honest wallet-shortfall copy pointing at the real (in-person QR) top-up path since card top-up is
  PSP-gated.

**Cosmetic:**
- `#192` count-string pluralization (`{n} item` vs `{n} items` at n=1) across waiter/driver/marketplace
  using the app's existing `x_one`/`x_other` convention.

**Follow-ups (shipped after these handoff docs were first written):**
- `#193` this handoff-doc set: `SESSION_LOG.md` + `NEXT_SESSION.md`, wired into `docs/README.md` and
  `CLAUDE.md`'s "Current state".
- `#194` onboarding activation, wave 2: a **"copy to all days"** helper on the business-hours step
  (hours defaulted to 0/7 open, forcing per-day toggling — real activation friction) and a
  **"Save & exit to dashboard"** affordance on the wizard, with the raw `window.confirm` leave prompt
  replaced by the app's `useConfirmModal` (progress already persists, so leaving is safe).
- `#195` waiter search no longer flashes a false **"No results"**: searching a dish before its
  category has lazily loaded now gates the empty state on a synchronous search-loading flag (set
  before the 200ms debounce) with a per-run token guarding the stale-resolve race. Hits the core
  add-item loop; regression test `WaiterNewOrderSearchLoading.test.js` added.

### How the work was run (and what went wrong)

- **Delegate-and-gate:** most editing was done by fresh-context sub-agents (worktree-isolated,
  parallel where surfaces were disjoint) while the main loop kept the verify-and-merge gate —
  reviewing every money-, checkout-, and flow-touching diff, and merging only on confirmed CI green.
  This scaled well across a very long session. See memory `agent-delegate-and-gate`.
- **CI is not a required check in this repo** — `gh pr merge` will land a red/pending PR. Combined
  with the fact that **local `npm run lint`/`build`/`test` can't run in the main working tree**
  (churned `node_modules`; only `verify:i18n` runs), this bit ~half a dozen times: an intentional
  change breaking a test/mock that hard-coded old behavior (duplicate `const`, a stale label
  assertion, an unused `emit`, a missing `formatCurrency` in a test mock). **Every one was caught by
  CI and fixed before/right after merge; `main` was never left broken at rest.** The standing rule
  now: **confirm `gh pr checks <N>` is green before every merge.** See memory `ci-merge-not-gated`.
  (Note: agents that ran `npm ci` in their *fresh* worktree could run the full gate locally — that's
  the reliable way to validate a branch before the main loop sees it.)

---

<!-- Add new campaign/session entries ABOVE this line, newest first. -->
