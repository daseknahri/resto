---
name: saas-finalization
description: >
  Playbook for finalizing the Kepoli restaurant/delivery super-app into a real, customer-friendly,
  end-to-end product. Use when the task is holistic UX/product finalization across the four sides
  (customer, restaurant owner/staff, driver, platform admin) and their cross-side relations — auditing
  real-life friendliness, then shipping improvements in gate-verified, multi-branch PRs. Invoke for
  "finalize the app", "improve UX end to end", "make it customer-friendly for real use", or continuing
  the UX-finalization campaign.
---

# SaaS finalization playbook (Kepoli)

Goal: turn a code-complete, hardened app into one that feels like **one coherent product real people
enjoy using** — a customer who finishes the order and comes back, staff who work fast without mistakes,
a driver who glances and taps, an operator who trusts the numbers.

## The four sides + their key flows
- **Customer** — storefront (per-tenant, host-resolved) + marketplace (platform, slug-resolved): discover →
  browse/menu → customize dish → cart → checkout (delivery/pickup, address, fee/min, tip, promo,
  wallet/cash) → track order → rate/reorder; account (auth, wallet, loyalty, saved addresses, following).
- **Owner/staff** — POS/waiter floor (new/append/transfer/merge/course/void/comp/settle), kitchen board,
  menu mgmt, promotions, reservations, drawer (open/txn/close/Z-report), analytics, onboarding, settings.
- **Driver** — mobile, one-handed: job list → accept → navigate → pickup → deliver (+ code) → earnings →
  cash-out. (The cash-out 6-digit code is a live bearer credential — never surface/log it carelessly.)
- **Platform admin** — tenants, funding a tenant float, delivery zones, delivery-job list, analytics,
  flash sales, wallet bonus/voucher.

## Cross-side relations (the "connecting people" spine)
The **order lifecycle** spans all sides: customer places → owner/kitchen accepts/prepares → driver
dispatched/picks up/delivers → customer tracks live → ratings + wallet/loyalty settle. Finalization means
a status set on one side reflects clearly and **consistently** (same wording, same steps) on the others,
with timely cross-side feedback (accepted / ready / driver-assigned / delivered / paid / rated), and the
money story (wallet, cash-on-handover, commission, driver earnings, refunds) stays coherent from each view.

## What "customer-friendly for real life" means (audit dimensions)
1. **No dead-ends** — always a clear next action / way back.
2. **Every async has 3 states** — loading, empty, error — plus success feedback. A blank screen or raw
   error on a flaky phone loses the user.
3. **Human copy** — errors are a sentence + a next step, never a raw code/status. Confirmations for
   destructive/irreversible actions (void, comp, close drawer, delete, fund, refund).
4. **Trust at money moments** — echo the amount, say what's being paid, wallet vs cash clarity.
5. **Feedback on every action** — did it save? did the order go through? disable-on-submit; the backend
   now has idempotency on append/payment/drawer — surface that safety in the UI.
6. **Consistency** — same terminology/status across sides; reuse shared components/composables.
7. **Accessibility + i18n + RTL** — labeled controls, focus-visible, semantic buttons; no raw i18n keys;
   FR (ASCII-only convention) + AR parity; RTL-safe.
8. **Real-life edge cases** — slow/lost connection, retries, concurrency, empty accounts, first-run.

## Workflow (multi-branch, gate-verified, continuous)
1. **Audit** — fan out read-only agents (one per side + one cross-side) → each returns a PRIORITIZED
   backlog, every item tagged **[CODE]** (verifiable without a render: copy, states, flow, feedback,
   consistency, a11y, i18n, logic) or **[VISUAL]/[PRODUCT]** (needs deploy QA or an owner decision).
2. **Synthesize** — merge into one ranked backlog by (real-user impact × frequency); group into coherent,
   independently-shippable themes (usually one theme = one PR).
3. **Execute [CODE] items autonomously**, one theme per branch off `main`:
   - Implement matching surrounding style; reuse `ui-*` design primitives (see
     `frontend/src/styles/UI_SYSTEM.md`) and shared composables; converge duplicated logic.
   - For visual/layout polish that stays behavior-preserving, delegate the page to the
     **`ui-ux-pro-max`** agent (it must not change behavior/props/emits/API/router/store).
   - Add/adjust tests. Update i18n in **all** locale files under the correct namespace.
4. **Gate-verify before every commit** (GREEN = 0 failed; ~80 backend DB errors are the known baseline):
   ```
   cd backend;  $env:DJANGO_DEBUG="True"; C:\Python312\python.exe -m pytest tests -q -p no:cacheprovider
   cd frontend; npm run verify:i18n; npm run lint; npm run build; npm run test
   ```
   Run only the frontend gates for FE-only changes, only pytest for BE-only.
5. **Ship** — branch off `main` (never commit to `main`), commit (end message with the Co-Authored-By
   line), push, open a PR, `gh run watch` the CI, verify per-job conclusions, `gh pr merge --merge
   --delete-branch` server-side, sync `main`. Pipeline: rebase the next branch onto updated `main`
   (disjoint files auto-merge); merge server-side so an in-flight branch's working tree stays intact.
6. **Queue [VISUAL]/[PRODUCT]** items for the owner with a crisp one-line decision each; keep a running
   list. Never ship a change whose correctness you can't verify (no live render here).
7. **Loop** — after a theme merges, take the next; re-audit when a surface is substantially reworked;
   keep going until the backlog is drained or hitting diminishing returns, then hand off the queue.

## Environment notes (this repo)
- Backend: system Python `C:\Python312\python.exe`, run via PowerShell; no local Postgres (DB tests
  error locally = baseline, not regressions). Prefer mock `SimpleTestCase`. A test that goes through a
  new `transaction.atomic()` must patch `menu.views.transaction` (SimpleTestCase forbids real DB).
- Bash tool's PATH is unreliable here (no gh/grep/cat) — use PowerShell for gh/git; git push prints to
  stderr so PowerShell shows NativeCommandError but the push SUCCEEDS (verify with `git status -sb`).
- Deploy is manual (owner triggers Coolify); `git push` does NOT deploy. So [VISUAL] items only get real
  QA after the owner deploys — batch them and say so.
- Canonical docs: `docs/PRODUCT_VISION_AND_REBUILD_PLAN.md`, `docs/ARCHITECTURE.md`, `CLAUDE.md`,
  `frontend/src/styles/UI_SYSTEM.md`.
