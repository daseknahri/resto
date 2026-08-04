# Kepoli — start here (next session)

The single "what's the state, how do I work here, and what's left" doc for a fresh session. Read
[`../CLAUDE.md`](../CLAUDE.md) first (the on-ramp), then this. For *what already shipped*, see
[`SESSION_LOG.md`](SESSION_LOG.md); for *how it's built*, [`ARCHITECTURE.md`](ARCHITECTURE.md); for
*known debt*, [`RISK_REGISTER.md`](RISK_REGISTER.md).

> This doc supersedes the older, now-stale "what's next" files at the repo root (`KEPOLI_NEXT.md`,
> `NEXT_PHASE_PLAN.md`, `BACKLOG.md`, `Production_Enhancements_TODO.md`) — read those as history.

---

## 1. Current state (2026-08-04)

- `main` @ `616f8ed`, **green** — frontend lint/build/vitest (~963 tests) + backend pytest +
  Playwright e2e + Docker builds all pass in CI. Deployable.
- The last campaign (24 PRs, #169–#192) is fully merged and cleaned up — see
  [`SESSION_LOG.md`](SESSION_LOG.md). Deploy is still **manual via Coolify** (git push does NOT
  deploy).
- **Everything shippable without an owner decision or external prerequisite is done.** What remains
  (§4) is gated on the owner: a payment provider, the first non-MAD tenant, a few product decisions,
  and the deferred dependency majors.

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

### B. Flagged this campaign but not shipped (need a decision or are lower value)

- **Onboarding — business-hours "copy to all days"** (med, feature): hours default to 0/7 open and
  require per-day toggling; a "copy Monday to all days" helper (and/or a sensible default schedule)
  would cut real activation friction.
- **Wizard — "Save & exit to dashboard" affordance** + replace the raw `window.confirm` leave prompt
  with the app's `useConfirmModal` (med): progress already persists, so leaving should feel safe.
- **Desktop pill-nav vs. mobile dock consistency** (low-med): #185 changed only the *mobile* dock to
  Orders+Account; the desktop pill-nav in `LandingLayout.vue` still shows Landing/Order/Contact/
  Business. Reconcile if desired.
- **"Order" vs "Orders" dock-label adjacency** (cosmetic): slots 2 and 3 differ by one letter
  (mitigated with distinct icons). Could relabel slot 2 (marketplace) to "Discover"/"Browse" — but
  that also touches the desktop nav for consistency.
- **Waiter search false "No results"** (W1, med): searching a dish before its category has lazily
  loaded shows "No results" — the empty state isn't gated on a search-loading flag. Hits the core
  add-item loop; needs a small loading-flag addition.
- **Waiter clock-in guard consistency** (W2, product decision): the toolbar "+ New order" blocks with
  a "clock in first" toast, but the floor-tile / table-group "+ New order" bypasses it. Decide
  whether floor-tile new-order should require clock-in, then make them consistent.
- **Consumer in-menu qty-stepper touch targets** (C2, visual-density judgment): the `±` steppers are
  ~28px (< the 44px design-system gate) but deliberately compact; enlarging changes card density.

### C. Deferred dependency majors (4 open Dependabot PRs)

Each has a real blocker — don't merge blind:
- **`#154` tailwind 4** — a CSS-layer / config rewrite; high-risk, defer until deliberately scheduled.
- **`#151` django 6** — really a **Django 5.2 LTS** decision (4.2 is EOL; `django-tenants` compat +
  6.0 churn). Pick the LTS target first.
- **`#148` eslint 10** — tractable: `eslint-plugin-vue` caps eslint ≤9, so bump the companion plugin
  (`eslint-plugin-vue` 9→10) on the same branch, then eslint. CI-gate it.
- **`#147` stripe 15** — dormant seam; `stripe.error` removed → runtime break. Migrate when wiring the
  PSP (item A.1).

### D. Pre-existing owner items (from `CLAUDE.md`, still open)

- **Product decisions:** commission basis (pre- vs post-discount), stuck-delivery refund policy,
  rides go-live.
- **Ops / infra launch:** DNS/TLS, prod env, email, backups, first-tenant smoke.
- **Schedule the two sweep commands on Coolify:** `sweep_delivery_jobs` (~60s) and
  `reconcile_driver_earnings` (~15 min).

## 5. Repo hygiene (needs owner sign-off — not done automatically)

- **Stale leftover git worktrees** exist under `.claude/worktrees/` (`optimistic-wilson-678c57`,
  `admiring-curran-*`, `happy-goldwasser-*`) and `../resto-wt/fe2*` from much earlier sessions — they
  carry old branches and duplicate root docs. `git worktree list` shows them; prune with
  `git worktree remove` once confirmed unneeded.
- **Root doc de-clutter** — `docs/README.md` §"Point-in-time snapshots" already suggests moving the
  historical root `.md` files into `docs/history/`. File moves need explicit direction.
