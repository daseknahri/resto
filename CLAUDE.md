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

## Current state (2026-08-04)
`main` is green and deployable (all CI jobs pass). The 2026-08 daily-use / reliability / product-content / flow campaign shipped **24 PRs (#169–#192)** — daily-use quality across all four operator + consumer surfaces, two reliability fixes, four owner-directed product/flow decisions, and a conversion/activation pass. **Speed and navigation were already done** (the `PERF_HOSTING_AUDIT.md` backlog is implemented; the IA is mature) — do **not** re-audit them. Everything shippable without an owner decision or external prerequisite is done.

> **New session? Read [`docs/NEXT_SESSION.md`](docs/NEXT_SESSION.md) first** — current state, the verify/merge discipline (**CI is NOT a required check here → confirm `gh pr checks` green before merging**; the main-tree `node_modules` can't run lint/build/test — only `verify:i18n`), the delegate-and-gate campaign playbook, and the prioritized remaining backlog. [`docs/SESSION_LOG.md`](docs/SESSION_LOG.md) is the changelog of what shipped.

**Remaining work needs the owner** (details in `docs/NEXT_SESSION.md`): a **Stripe PSP** account (top-up/checkout/payout seam built but dormant — the biggest conversion lever), the first **non-MAD tenant** (mixed-currency analytics aggregates), a few product decisions (commission basis, stuck-delivery refund, rides go-live, plus a handful of flagged UX items), the 4 deferred Dependabot majors, ops/infra launch (DNS/TLS, prod env, email, backups), and **scheduling the two sweep commands** on Coolify: `sweep_delivery_jobs` (~60s) and `reconcile_driver_earnings` (~15 min).

## Conventions
- Match surrounding code style. Work on a branch off `main` (do **not** push to `main` directly — it's blocked). Commit gate-verified batches; end commit messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Fixing a security/logic bug? Update the tests that encoded the old behavior AND add a regression test.

## Deep docs (read when relevant)
- **Canonical set (start here): [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · [`docs/RISK_REGISTER.md`](docs/RISK_REGISTER.md) · [ADRs](docs/adr/) · [`docs/README.md`](docs/README.md) (index).**
- Architecture / routing (deep-dive): `Tenant_Routing_and_API_Architecture.md`
- This session's audit + fixes: `DAILY_USE_AUDIT.md`
- Launch / QA / ops: `Pre_Deployment_QA_Checklist.md`, `First_Tenant_Production_QA.md`, `Launch_Closure_Plan.md`, `VPS_Deployment_Readiness_Report.md`, `infra/DEPLOYMENT_RUNBOOK.md`, `infra/README.md`
- Product roadmap / tiers: `SaaS_Roadmap.md`, `restaurant-saas-tiers.md`
- i18n content model: `I18N_Content_Model_Strategy.md` · Order flow: `Order_Flow_E2E_QA.md`
