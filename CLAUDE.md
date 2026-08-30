# Kepoli — working guide for Claude Code sessions

Kepoli is a multi-tenant restaurant / delivery **super-app**: Django + django-tenants + DRF
backend, Vue 3 + Vite + Pinia SPA frontend (i18n is **hand-rolled** — `composables/useI18n.js`,
**not** vue-i18n). This file is the fast on-ramp for a new session — **how to work here without
rediscovering the traps.** Deep docs are linked at the bottom; don't duplicate them.

> **New here? Read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the mental model, then
> [`docs/RISK_REGISTER.md`](docs/RISK_REGISTER.md) for the known debt.** Those + the
> [ADRs](docs/adr/) are the canonical docs; the 30+ root `.md` files are point-in-time snapshots
> (see [`docs/README.md`](docs/README.md) for which are still authoritative).

## Layout
- `backend/` — Django project (apps: `accounts` = public/shared schema incl. wallet & drivers, `menu` = per-tenant orders/menu, `tenancy` = tenants). Tests in `backend/tests/`.
- `frontend/` — Vue SPA. Pages in `src/pages/`, stores in `src/stores/`, i18n in `src/i18n/`, design system in `src/styles/`.
- `infra/`, `platform/` — Coolify deploy, DNS/TLS, backups, runbooks.

## Run & verify — READ THIS FIRST

### Backend (no local Postgres!)
- Use system Python (there is **no** local venv): `C:\Python312\python.exe`. Run via the **PowerShell** tool, not Bash.
- Tests need debug on or they hard-fail on SECRET_KEY:
  ```
  cd backend; $env:DJANGO_DEBUG="True"; C:\Python312\python.exe -m pytest tests -q -p no:cacheprovider
  ```
- **GREEN = `0 failed`.** There are ~56 `errors` (not failures) — DB-requiring tests that can't connect to Postgres locally. They are the known baseline, **not** regressions. Never chase them.
- Most tests are **mock-based `SimpleTestCase`** and DO run locally. When adding tests, prefer mocks so they run without a DB. `py_compile` is a quick syntax pre-check for big edits.

### Frontend (can't render locally — gate-verify only)
```
cd frontend
npm run verify:i18n   # locale parity + usage (see gotcha below) — runs TWO scripts
npm run lint          # eslint, --max-warnings=0
npm run build         # vite build (catches template/compile errors the linter misses)
npm run test          # vitest (~343 tests)
```
No prod data locally, so you cannot preview the UI — these 4 gates are the verification.

## Gotchas (these WILL bite you)
- **i18n is single-source-per-locale** (FE-1 collapsed the old dual source; `messages.js` was deleted). A new key is added to **one file per locale**: `messages-en.js` (English — the runtime EN **and** the parity source both gates check against), `messages-fr.js` (French), and `messages-ar.js` (Arabic; runtime AR = clone-of-en + these sparse overrides). Both gates now read these **same runtime files**, so a key that passes the gates is the key the runtime ships — no more "passes one gate, raw key at runtime" drift. Put the key under the **same namespace the template uses** (a `mktMenu.*` key must live under `mktMenu`, not `menu`/`cartPage` — that mismatch was the exact latent bug FE-1 fixed). FR text in `messages-fr.js` is **ASCII-only by convention** (no accents — avoids mojibake). `npm run verify:i18n` runs both checks (FR/AR completeness + key-usage); both must pass.
- **Tenancy scoping.** Each restaurant is a Postgres **schema**. `menu`/order models auto-scope by the request's schema. But `accounts` models (`Customer`, `WalletTransaction`, `DeliveryJob`, `DriverCashoutRequest`, cash-out) are in the **public/shared** schema — they must be **manually** scoped by `tenant_id` / ownership, or you leak across tenants. The session cookie is valid on **every** tenant subdomain, so owner/admin endpoints must check `user.tenant_id == request.tenant.id` (use the `_is_tenant_owner(request)` helper), not just the role.
- **Money invariants.** The driver cash-out 6-digit code is a **live bearer credential — never log it.** Wallet idempotency keys derived from tenant-local ids must be **schema-namespaced**. Wallet mutations re-check idempotency **under the `select_for_update` row lock** (see `accounts/wallet_service.py`) so concurrent same-key requests replay instead of double-applying / 500-ing.
- **Deploy is manual.** `git push` does NOT deploy. The user triggers Coolify in its dashboard. Prod needs a real `DJANGO_SECRET_KEY` and `DEBUG=False` (see `infra/`).
- CRLF warnings from git on Windows are harmless.

## Design system
`frontend/src/styles/UI_SYSTEM.md` is the contract (primitives `ui-panel`, `ui-input`, `ui-btn-primary/outline`, `ui-table-wrap`, `ui-chip`…). QA gate: no horizontal overflow at 390px, explicit loading/empty/error states, one primary CTA per section, ≥44px touch targets, focus-visible, RTL-safe.

## Current state (2026-08-30)
`main` is green and deployable (all CI jobs pass, on **Django 5.2.17 LTS**). Most recent: the 2026-08-30 **full-app performance pass** — a fresh 31-agent read-only speed+hosting audit ([`PERF_HOSTING_AUDIT.md`](PERF_HOSTING_AUDIT.md), PR #296; 43 findings, high/critical adversarially verified) whose verified autonomous-safe items shipped as **11 CI-gated PRs (#297–#304, #306–#308)**: the **critical async-notification migration** (bulk order-confirm no longer blocks the request on up to 50 sequential SMTP sends; #302), two missing indexes (`DeliveryJob.declined_by` GIN + `AdminAuditLog`; #297/#298), a 9–10× reservation count-query fold (#300), `AdminPlatformAnalyticsView` caching (#303), frontend cold-load (EN-chunk modulepreload + Sentry Replay lazy-load; #301), `enforce_subscriptions` batching (#299), order-line `bulk_create` (#304); plus — from a coverage-gap follow-up round that closed the three categories the big pass hadn't covered — cached `Intl.*Format` formatters (#306), a marketplace flash-sale per-second-re-render fix + debounced menu search (#308), and a `DeliveryJob (status,delivered_at)` index + HappyHour serializer prefetch fix (#307). **Two owner/ops caveats at deploy** (see [`docs/SESSION_LOG.md`](docs/SESSION_LOG.md)): the two concurrent-index migrations should ride the owner's next staging-migration rehearsal (they're the safer `SHARED_APPS` ×1 case, not the tenant-provisioning path), and enabling Sentry Replay later needs a CSP allow-list for `browser.sentry-cdn.com`. Prior: the 2026-08-27 **super-app hardening sweep** — a 118-agent read-only audit (22 finders × every lens across all four surfaces, each finding adversarially verified) surfaced **94 verified findings** ([`docs/HARDENING_SWEEP_2026-08-23.md`](docs/HARDENING_SWEEP_2026-08-23.md), PR #242); the autonomous-safe ones shipped as **~29 CI-gated PRs (#241, #243–#273)** across six delegate-and-gate waves (money/concurrency, security/authz, correctness, UX/error-handling, a11y/i18n). A follow-up 2026-08-28 **deep money/concurrency audit** (3 read-only finders on the highest-stakes surface) then found **7 more defects the breadth-first sweep missed** — incl. a **HIGH silent revenue leak** (void/comp Case-B double-counted wallet payments) and a regression from #273 — shipped as #275–#277. The LOW `MAD`-currency display cluster is confirmed **owner-gated, not autonomous** (cross-tenant public-schema records carry no per-record currency; it's part of the mixed-currency aggregation decision). The **12 owner-decision findings** remain the owner's product/policy calls. Full record: [`docs/SESSION_LOG.md`](docs/SESSION_LOG.md). Earlier campaigns since #168: the 2026-08 daily-use pass (**#169–#192**), the 2026-08-05 super-app hardening + calibration (**#199–#204**), the 2026-08-12 **operational-gaps closure + big-test sweep** (**#217–#220**), the 2026-08-16 **full-app hardening campaign** (**#222–#225**) — a 45-agent adversarial gap scan (32 confirmed defects) whose **22 safe-autonomous** fixes shipped (a driver proof-of-delivery **security bypass**, a cross-tenant loyalty **IDOR**, three concurrency races, a revoked-driver payout gate; see [`docs/HARDENING_GAPS.md`](docs/HARDENING_GAPS.md)) — and the 2026-08-17 **§4.F hardening-decisions closure** (**#227–#234**): **8 of the 9** owner-flagged items shipped as CI-gated PRs, each with regression tests — 4 money (driver-payout double-booking, transfer/merge stranded payment, wallet self-pay over-charge, no-show+redispatch double-pay) + ETA server-anchor, currency 2-decimals, failed-delivery status coherence, and ride+delivery cross-vertical double-booking. **Only §4.F item 8 remains** and it's a product-policy call for the owner (whether to MANDATE a photo for a code-less DELIVERED completion — the security bypass itself is already fixed, #222). **Navigation/IA is mature** — do **not** re-audit it. **Speed was freshly re-audited 2026-08-30** (the ~65-PR churn since the prior audit warranted it), *including* a follow-up round that closed the three categories the first pass hadn't covered — frontend runtime, backend serializer/hot-path, and Docker/deps; the verified wins shipped (#297–#304, #306–#308). Docker/image + dependency weight were re-verified **clean** (all prior optimizations intact). What remains is genuinely **not low-hanging fruit**: **Phase-4 structural** (a `DeliveryJobDecline` table/counter once the `declined_by` GIN index isn't enough), and **owner/ops hosting judgment calls** — dormant `boto3` (~90 MB image weight; slimming it changes the S3-enable deploy contract, a roadmap call), a uvicorn `--preload`/COW RAM lead that needs staging testing, a Redis `maxmemory`/eviction-policy gap, and a non-perf **test-parity flag** (prod runs Python 3.14 vs local/CI 3.12). Everything shippable without an owner decision or external prerequisite is done.

> **New session? Read [`docs/NEXT_SESSION.md`](docs/NEXT_SESSION.md) first** — current state, the verify/merge discipline (**CI is NOT a required check here → confirm `gh pr checks` green before merging**; the main-tree `node_modules` can't run lint/build/test — only `verify:i18n`), the delegate-and-gate campaign playbook, and the prioritized remaining backlog. [`docs/SESSION_LOG.md`](docs/SESSION_LOG.md) is the changelog of what shipped.

**Remaining work needs the owner** (details in `docs/NEXT_SESSION.md`): a **Stripe PSP** account (top-up/checkout/payout seam built but dormant — the biggest conversion lever), the first **non-MAD tenant** (mixed-currency analytics aggregates), a couple of product decisions (**rides go-live**; and the flagged **void-item commission** basis — align it with post-discount checkout via a discount-allocation rule), the 4 deferred Dependabot majors, ops/infra launch (DNS/TLS, prod env, email, backups), and **scheduling the two sweep commands** on Coolify: `sweep_delivery_jobs` (~60s — now also drives the stuck-delivery auto-refund) and `reconcile_driver_earnings` (~15 min).

## Conventions
- Match surrounding code style. Work on a branch off `main` (do **not** push to `main` directly — it's blocked). Commit gate-verified batches; end commit messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Fixing a security/logic bug? Update the tests that encoded the old behavior AND add a regression test.

## Deep docs (read when relevant)
- **Canonical set (start here): [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · [`docs/FEATURE_MAP.md`](docs/FEATURE_MAP.md) (what's built, per surface) · [`docs/RISK_REGISTER.md`](docs/RISK_REGISTER.md) · [ADRs](docs/adr/) · [`docs/README.md`](docs/README.md) (index).**
- Architecture / routing (deep-dive): `Tenant_Routing_and_API_Architecture.md`
- This session's audit + fixes: `DAILY_USE_AUDIT.md`
- Launch / QA / ops: `Pre_Deployment_QA_Checklist.md`, `First_Tenant_Production_QA.md`, `Launch_Closure_Plan.md`, `VPS_Deployment_Readiness_Report.md`, `infra/DEPLOYMENT_RUNBOOK.md`, `infra/README.md`
- Product roadmap / tiers: `SaaS_Roadmap.md`, `restaurant-saas-tiers.md`
- i18n content model: `I18N_Content_Model_Strategy.md` · Order flow: `Order_Flow_E2E_QA.md`
