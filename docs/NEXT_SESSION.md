# Kepoli — start here (next session)

The single "what's the state, how do I work here, and what's left" doc for a fresh session. Read
[`../CLAUDE.md`](../CLAUDE.md) first (the on-ramp), then this. For *what already shipped*, see
[`SESSION_LOG.md`](SESSION_LOG.md); for *how it's built*, [`ARCHITECTURE.md`](ARCHITECTURE.md); for
*known debt*, [`RISK_REGISTER.md`](RISK_REGISTER.md).

> This doc supersedes the older, now-stale "what's next" files at the repo root (`KEPOLI_NEXT.md`,
> `NEXT_PHASE_PLAN.md`, `BACKLOG.md`, `Production_Enhancements_TODO.md`) — read those as history.

---

## 1. Current state (2026-08-16)

- `main` @ `7629db9`, **green** — frontend lint/build/vitest + backend pytest (on **Django 5.2.17 LTS**) +
  Playwright e2e + Docker builds all pass in CI. Deployable. *(2026-08-10: backend off end-of-life Django —
  upgraded 4.2.30 → 5.2.17 LTS (#215); CI security gates clean. See §4.C.)*
- Recent campaigns are fully merged + cleaned up (#169–#225) — see [`SESSION_LOG.md`](SESSION_LOG.md). The
  latest, the **2026-08-16 full-app hardening campaign** (#222–#225), ran a **45-agent adversarial gap
  scan** (34 → 32 confirmed defects, 2 false claims killed) and shipped the **22 safe-autonomous** fixes: a
  driver proof-of-delivery **security bypass**, a cross-tenant loyalty **IDOR**, three concurrency races
  (cancel / void / clock-in), a revoked-driver payout gate, the MFA-disable audit log, and
  marketplace-reorder / receipt-coherence / i18n fixes. Full record:
  [`HARDENING_GAPS.md`](HARDENING_GAPS.md). The **9 owner-decision** items it surfaced are in **§4.F**.
  Deploy is still **manual via Coolify** (git push does NOT deploy).
- **The quick-win [CODE] backlog is drained.** Three audit/closure campaigns (daily-use, then money/
  coherence/robustness + calibration, then the operational-gaps pass) fixed the real bugs and closed the
  flagged gaps. What remains (§4) is **owner-gated or structural**: a payment provider, the first non-MAD
  tenant, a couple of product decisions, the deferred dependency majors, scheduling the two Coolify sweeps,
  and the big structural phases (POS offline reliability, unifying the two consumer front-ends, a dedicated
  driver surface).

## 2. Don't re-audit these — they're done

A fresh session's instinct is to audit and find work. These have already been audited exhaustively
this campaign; **don't burn a budget re-discovering them:**

- **Speed / hosting efficiency** — the `PERF_HOSTING_AUDIT.md` backlog is implemented (marketplace
  response caching + single-flight, `rating_avg` denormalization, `Profile`/`Order` indexes,
  `CONN_HEALTH_CHECKS`, Docker `build-essential` purge, `CustomerOrderRef` admin path,
  `leaflet`/`qrcode` code-splitting, query folds, throttles). Only two explicit "revisit at
  100+ tenants" items remain (WebSocket order-status vs polling; HTTP cache headers) — not quick
  wins.
- **Navigation / IA** — mature (frequency-based owner nav + mobile dock, `KeepAlive :max=8`, idle
  chunk-prefetch, capability-gating, live badges). The consumer dock was fixed this campaign (#185).
- **Daily-use quality, cross-surface coherence, product-content/conversion, onboarding activation,
  count pluralization** — all swept this campaign across every surface. See `SESSION_LOG.md`.

## 3. How to work here (the playbook that succeeded)

**Verification — this is the #1 operational trap:**
- The frontend `node_modules` in the **main working tree is churned** — `npm run lint`/`build`/`test`
  do NOT run there (only `npm run verify:i18n`, which is plain Node and covers **only** locale parity
  + key-usage, not lint/build/vitest).
- **CI is NOT a required check** — `gh pr merge` will land a red or pending PR. So **YOU are the
  gate: confirm `gh pr checks <N>` shows the `frontend` (and `e2e`) job `pass` before every merge.**
  Never merge on pending/fail. (Memory: `ci-merge-not-gated`.)
- To validate a branch *before* merging, the reliable path is `npm ci` inside `frontend/` in a
  **fresh git worktree** (works from the committed lockfile; the churn/arborist bug only hits lock
  *regeneration*, not a clean `ci` install) — then `lint` + `build` + `test` all run. Agents that did
  this shipped zero-fallout branches.
- Backend: mock-based `SimpleTestCase` tests DO run locally —
  `cd backend; $env:DJANGO_DEBUG="True"; C:\Python312\python.exe -m pytest tests -q -p no:cacheprovider`.
  ~56 DB-requiring tests error locally (no local Postgres) — that's the known baseline, not
  regressions. CI has a DB and runs them for real.

**Delegate-and-gate (for anything bigger than a one-file fix):**
- Spawn fresh-context sub-agents to do the editing (worktree-isolated; parallel only across
  **disjoint** files — same-file work must be sequential). Give each a precise brief: exact
  file:line, the i18n rules, "check `__tests__` and update assertions your change breaks", "commit +
  push a branch, NO PR/merge, report back", and — for money/checkout/nav — "prove the blast radius
  and report; don't ship a flow that fails later." Keep the PR / CI / **diff-review** / merge gate
  yourself. (Memory: `agent-delegate-and-gate`.) Recurring failure mode to watch: an intentional
  change breaks a test/mock that hard-coded the old behavior — expected; fix the test to the new
  intent.
- After merge, clean up the agent's worktree: `git worktree remove --force <path>` +
  `git worktree prune` (the `gh pr merge --delete-branch` local-branch step warns while the worktree
  still holds the branch — harmless).

**Non-negotiables** (also in `CLAUDE.md`): never push to `main` directly (blocked); FR i18n is
ASCII-only, AR matches its neighbors' encoding style; wallet idempotency keys are schema-namespaced
and the driver cash-out 6-digit code is a **live bearer credential — never log or over-expose it**;
`accounts`-schema models (Customer, wallet, DeliveryJob) must be manually tenant-scoped. End commit
messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## 4. Remaining backlog (prioritized)

### A. Highest leverage — needs an external prerequisite (owner)

1. **Wire card payment / wallet top-up (PSP / Stripe).** This is the single biggest conversion lever:
   signed-in checkout is wallet-only, so a first-time customer with an empty wallet is hard-blocked.
   The top-up/checkout/payout **seam is built but dormant** behind `platform.psp_topup_enabled`
   (off in prod). Interim honest copy is already shipped (#191 points users at the in-person QR
   top-up). When the owner has a Stripe account: wire top-up + pay-by-card at checkout against the
   existing seam. Runbook: `infra/COOLIFY_PSP_STRIPE_ACTIVATION.md`. (Also unblocks Dependabot
   `#147 stripe 15` — `stripe.error` was removed, so migrate at activation time.)
2. **Mixed-currency analytics aggregates** — the platform analytics dashboard sums money across
   tenants under a single `MAD` label; correct today (single-MAD prod), wrong once a **non-MAD
   tenant** onboards. Deferred by owner decision; when a non-MAD tenant exists, decide the approach
   (per-currency breakdown [backend groups by ISO currency] vs. convert-to-base via `CurrencyRate`)
   and build it. Per-order currency display in the admin console is already done (#187); this is the
   *aggregate* case only.

### B. Flagged earlier campaigns — ✅ ALL CLOSED (2026-08-12, #217)

The four UX gaps flagged (but deferred) by the prior campaigns were all closed in the operational-gaps
pass. Kept here as a record; nothing outstanding:

- ✅ **Desktop pill-nav vs. mobile dock consistency** — `LandingLayout.vue` desktop nav now carries
  **Account** (Landing/Browse/Account/Business), matching the mobile dock's Orders+Account direction.
- ✅ **"Order" vs "Orders" dock-label adjacency** — the marketplace slot was relabeled **"Order" →
  "Browse"** (`landingLayout.navOrder`, all three locales), removing the one-letter adjacency.
- ✅ **Waiter clock-in guard consistency (W2)** — the floor-tile / table-group "+ New order"
  (`openNewOrderForTable`) now applies the **same clock-in guard** as the toolbar (a not-clocked-in
  waiter gets the "clock in first" toast; a clocked-in one is unaffected).
- ✅ **Consumer in-menu qty-stepper touch targets (C2)** — the `±` steppers get a 44×44 invisible hit
  area (`ui-tap-expand`) that meets the design-system gate **without** changing visual card density.

### C. Deferred dependency majors + the EOL-Django clock (✅ RESOLVED)

**✅ RESOLVED (2026-08-10): Django upgraded 4.2.30 → 5.2.17 LTS (#215).** The app is **off end-of-life
Django** and onto supported 5.2 LTS. The six deferred Low CVEs are now genuinely *fixed* (5.2.17 ships
them), so the six `--ignore-vuln` deferrals were removed from `ci.yml` + `.trivyignore` and the security
gates run clean again. The upgrade was small/surgical — django-tenants 3.10.2 + DRF/Channels needed no
bump; only `make_random_password` (removed 5.1) and `django.utils.timezone.utc` (removed 5.0) usages had
to change — and was validated end-to-end in CI (full DB suite + e2e + Docker on 5.2.17, no model drift).
*(The separate npm `nanoid` HIGH was fixed to 3.3.18 in #213. Dependabot `#212`, which targeted 6.1, is
now superseded — close it.)* **One follow-up, flagged not fixed:** the *dormant* schema-pinned
`accounts/session_backends.SessionStore` only pins Django's **sync** session methods — pin the 5.x
**async** path (`asave`/`aexists`/…) before ever activating that store under ASGI (documented in
`backend/tests/test_ops3_session_backend.py`).

Each remaining Dependabot major has a real blocker — don't merge blind:
- **`#154` tailwind 4** — a CSS-layer / config rewrite; high-risk, defer until deliberately scheduled.
- **`#148` eslint 10** — tractable: `eslint-plugin-vue` caps eslint ≤9, so bump the companion plugin
  (`eslint-plugin-vue` 9→10) on the same branch, then eslint. CI-gate it.
- **`#147` stripe 15** — dormant seam; `stripe.error` removed → runtime break. Migrate when wiring the
  PSP (item A.1).

### D. Pre-existing owner items (from `CLAUDE.md`)

- **Product decisions — two resolved 2026-08-12 (#218), the rest open:**
  - ✅ **Commission basis → POST-discount** (#218, revenue-affecting): marketplace checkout now bills
    `rate × max(0, food − promo − loyalty)` via the shared `menu/commission.py` `commissionable_food_base`
    (owner statement + analytics use the same constant, so the three can't drift). *Follow-up (owner
    decision pending):* the **void-item commission recompute** (`StaffVoidOrderItemView`) still uses the
    **pre-discount** line-sum basis, so a discounted order later partly voided can slightly over-state
    commission. Aligning it needs a rule for **allocating an order-level discount across the voided lines**
    — decide the allocation, then apply (documented at the recompute site in `menu/views.py`).
  - ✅ **Stuck-delivery refund → bounded auto-refund** (#218): the `sweep_delivery_jobs` sweep now
    auto-refunds a **pre-pickup, provably-unfulfillable** delivery job past
    `Profile.delivery_auto_refund_minutes` (default **30 min**; `0` disables). It never touches a
    picked-up job (re-verified under a row lock) and reuses the shared idempotent refund helper (hardened
    against concurrent double-apply in #220). **Needs the sweep scheduled on Coolify to actually fire** —
    see below.
  - ⬜ **Rides go-live** — still open.
- **Ops / infra launch:** DNS/TLS, prod env, email, backups, first-tenant smoke.
- **Schedule the two sweep commands on Coolify:** `sweep_delivery_jobs` (~60s — now also drives the
  stuck-delivery **auto-refund**, so scheduling it is what turns that feature on) and
  `reconcile_driver_earnings` (~15 min).

### E. Structural super-app phases (scoped 2026-08-05; owner-gated — need a go-ahead, not autonomous)

The big vision levers. The audit campaigns hardened the existing surfaces; these change *structure* and
touch the working money/checkout path, so they need owner approval + careful staging (not overnight work).

> **Reviewed again 2026-08-12 and deliberately deferred.** Asked to "decide for me" on these, the call
> was **not** to start them autonomously: all three (unified server-side cart, offline-first POS, dedicated
> driver surface) sit **on the money/checkout path** and need deliberate staging + owner sign-off, not
> unattended work. The one safe, self-contained increment the scoping surfaced was already shipped (#206).

**Phase 3 — consumer coherence** (scoped in detail; `PRODUCT_VISION` §"Surface 2" is now partly **stale** —
coherence is **~80% already shipped**). Remaining, ranked:
- **Unify the two carts / front-ends (the headline item) — architecturally blocked.** The storefront
  (`Menu`/`Cart`/`OrderStatus`, on a **tenant subdomain**) and the marketplace/hub (`Marketplace`/
  `MarketplaceMenuPage`/`SuperAppHub`/`CustomerAccount`, on the **platform host**) run on **different
  origins**, so their localStorage carts **cannot** share client state. A truly unified cart needs a
  **server-side cart** (new model + endpoints **on the checkout path**) — not a frontend refactor.
- **Server-back dish favorites** — today localStorage-only per-slug (business *follow* is already
  server-backed via `CustomerTenantFollow`). Needs a `CustomerDishFavorite` model + migration + a
  follow-style view + FE wiring. Additive, but backend + migration.
- **Extract the duplicated stale-happy-hour re-price + validation guards** (`Cart.vue` ≈
  `MarketplaceMenuPage.vue`) into a shared checkout composable — sensible DRY, but it runs **inside the
  place-order path**, so stage it deliberately with full verification.
- *Already coherent (no action):* status vocab + reconciling receipts (#202), marketplace checkout parity
  (#203), server-hydrated **tenant-scoped** storefront history, shared saved-addresses. Forcing
  cross-tenant history onto the storefront would be **wrong** product behavior.
- *Shipped from this scope:* `#206` — marketplace reorder now **drops sold-out items** (was seeding them
  into a checkout-blocked cart) — the one safe, self-contained increment the scope surfaced.

**Phase 2 — POS terminal reliability** (offline-first order entry + payment, ticket concurrency,
multi-drawer/PIN, ESC/POS printing) and **Phase 5 — dedicated driver surface** (carve out a `/driver`
bundle, WebSocket offers/status, native push, offline action queue) are the other two structural levers —
both large and money-adjacent. See `PRODUCT_VISION` §"Surface 1/3" for the decomposition.

### F. Hardening-campaign decisions (owner) — surfaced 2026-08-16 by the gap scan

The full-app hardening scan (#222–#225) shipped all 22 safe fixes but surfaced **9 money/product-policy
items** that are the owner's call (not acted on autonomously), plus 1 structural. Full per-item evidence in
[`HARDENING_GAPS.md`](HARDENING_GAPS.md). Ranked:

1. **Driver-payout double-booking** (high, money) — the admin `owed` ledger and the wallet+cash-out rail
   settle the *same* delivered-job money independently, so a manual admin settlement can double-pay a
   driver. *Rec:* make the wallet+cash-out rail the single source of truth; `owed` excludes payouts already
   credited to the wallet.
2. **Transfer/merge a partially-paid table** strands the collected `OrderPayment` (money loss /
   double-charge). *Rec:* carry the OrderPayment rows onto the target order on transfer/merge.
3. **No-show → redispatch pays two drivers** for one delivery fee. *Rec:* only pay the no-show driver if the
   job isn't redispatched (or deduct it).
4. **Wallet self-pay ignores the cash/card `OrderPayment` ledger** — a customer paying the remainder of a
   partly-cash-settled tab is over-charged. *Rec:* outstanding = total − wallet_paid − OrderPayment sum.
5. **Currency rounding** — browsing/cart round MAD to whole dirhams while prices/receipts carry 2 decimals.
   *Rec:* round to 2 decimals everywhere.
6. **ETA anchoring** — the countdown is anchored to placement time, but owners mean "ready in X min *from
   now*". *Rec:* add a server-set `ready_at` anchor when the ETA is set/edited.
7. **Failed-delivery status divergence** — the customer page shows "Out for delivery" while the same page's
   tracker shows a red "Failed" pill. *Rec:* show a coherent "delivery failed — being resolved" state.
8. **Code-less DELIVERED completion** *policy* residual — the client-URL bypass is already fixed (#222);
   whether to additionally *require* a real photo for code-less completion is a policy call.
9. **Structural — a driver can hold an active ride AND an active delivery** at once (cross-vertical
   double-booking); tied to the owner-gated rides go-live (§4.D / §4.E).

**Deferred (not a decision):** the Arabic back-arrow glyph (low) — the FR arrows were cleaned in #225 but
`messages-ar.js` was untouched; a one-line follow-up.

## 5. Repo hygiene (needs owner sign-off — not done automatically)

- **Stale leftover git worktrees** — mostly pruned (2026-08-05): `optimistic-wilson-678c57`,
  `admiring-curran-*`, and `../resto-wt/fe2{j,k,l,m}` were removed via non-force `git worktree remove`
  (their `refactor/fe-2*` branches are **preserved** — only the working copies went). **One remains:**
  `.claude/worktrees/happy-goldwasser-dec544`, kept because its tree has **uncommitted files** (non-force
  remove refused it). Review that work, then `git worktree remove --force` it if disposable.
- **Root doc de-clutter** — `docs/README.md` §"Point-in-time snapshots" suggests moving the historical
  root `.md` files into `docs/history/`. The actively-*misleading* ones are now neutralized **in place**
  (a `⚠️ SUPERSEDED` banner on `PLATFORM_VISION.md` + `platform/*`, and the README "Superseded — do not
  trust" table, 2026-08-05), so this is now cosmetic de-clutter, not a correctness issue. File moves need
  explicit direction.
