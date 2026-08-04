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
