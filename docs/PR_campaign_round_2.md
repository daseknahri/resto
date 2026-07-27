# Risk-register hardening — round 2 (campaign integration)

Merges `integration/campaign-round-2` into `main`: the second wave of the
`docs/RISK_REGISTER.md` hardening campaign. **116 commits · 228 files · +16,137 / −18,376**
(net ≈ −2,200 lines — mostly the i18n de-duplication and mega-page decomposition).
Every commit was gate-verified in isolation (backend pytest + ruff; frontend
verify:i18n / lint / build / vitest); nothing here is speculative.

> ⚠️ **Reviewer — verify the merge base first.** This is a combined integration branch;
> a prior round had a base-slip. Confirm this branch is based on the current `main` tip and
> that the diff below contains only intended round-2 work before merging.

## What's in it (by RISK item)

**Frontend**
- **FE-2 — mega-page decomposition (67 commits).** Six 2.5–3.7k-line Vue pages split into
  **~62 tested child components** (props-in / events-out), each with an isolated vitest suite.
  Both money-path pages — **Cart** and the **Marketplace checkout drawer** (now 8 sub-components) —
  and **WaiterPage** (settle + rating modals) are fully decomposed with all
  payment/order logic (`placeOrder` / `placeInAppOrder` / settle / cashout) deliberately kept in
  the parents. Behaviour-preserving throughout.
- **FE-1 — i18n single source.** Deleted the redundant `messages.js` (11.8k lines) and repointed
  both verify gates to the runtime `messages-{en,fr,ar}.js`, collapsing the dual-source footgun to
  one source per locale. Fixed live namespace-mismatch raw-key bugs surfaced by the drift.
- **FE-3 — locale first-paint.** Test coverage for the lazy `localeLoader`; residual is a
  deliberate UX tradeoff.

**Auth / identity (security-relevant)**
- **AUTHZ-1 — authorization policy layer (14 commits, 13 slices).** Migrated the owner endpoints
  from copy-pasted `_is_tenant_owner` guards to declarative `permission_classes=[IsTenantOwner]`;
  deleted the dead duplicate helper.
- **IDENTITY-1 — one auth stack (12 commits).** `CustomerSessionAuthentication` + `IsCustomer` /
  `IsOrderOwner` / `customer_or_none`; the customer/driver DRF view sweep is complete; per-customer
  throttles now key on the Customer principal; fixed a throttled-request 500→429.

**Async / money-path**
- **ASYNC-1 — durable outbox** for the inline (no-broker) task fallback + a boot-time `relay_outbox`
  (production-gated, idempotent via the ASYNC-4 dedup).
- **ASYNC-2 / ASYNC-3** — scheduled the CustomerRating retention prune; made realtime polling
  substitutive when the WS is live.
- **DATA-1** — order-number generator entropy widened to 48-bit (format-compatible; no
  migration/frontend change); the acute cross-schema risk is already covered by the composite
  `(tenant_id, order_number)` keys + reconcile.
- **STRUCT-2** — marked one-time data-backfill migrations `elidable=True` (squash-prep;
  behaviour-neutral) with a squash runbook.

Plus the register/ADR/CLAUDE.md docs kept in lockstep with each change.

## Deploy notes

- **One new migration:** `accounts/0068_outboxmessage` — creates `OutboxMessage` in the **public /
  shared** schema (picked up by `migrate_schemas --shared`). The other touched migration files are
  `elidable=True` annotations on already-applied migrations (no schema change, no drift —
  `makemigrations --check` clean).
- **`docker/entrypoint.sh`** now runs `python manage.py relay_outbox` before the server starts
  (best-effort, non-fatal).
- **No breaking API changes.** `order_number` stays `ORD-<uppercase hex>` (wider, still ≤ 20 chars,
  matches the frontend route regex); no serializer/URL contract change.
- **Env:** no new required env vars. The durable outbox only engages when `DEBUG` is off and the
  Celery broker is unreachable (the deploy check still requires a broker in prod).

## Verification

- **Backend:** full pytest suite **0 failed** (4,828 passed; the ~80 "errors" are the known
  local no-Postgres baseline — DB-requiring tests run in CI); `ruff` clean; `manage.py check` and
  `makemigrations --check` clean.
- **Frontend:** `verify:i18n` PASS (FR/AR complete, all keys used), `lint` clean (max-warnings 0),
  `build` PASS, `vitest` green (~924 tests).

## Reviewer checklist

**Merge integrity**
- [ ] Branch is based on the **current `main` tip** — no base-slip (a prior round had one); the diff below contains only intended round-2 work.
- [ ] **CI is green on the full DB-backed suite** (the ~80 local "errors" are the no-Postgres baseline and must pass in CI — confirm they run, not skip).
- [ ] The TEST-1 count-floor / skip-ceiling CI gate still passes (no silently dropped tests).

**Migrations & deploy**
- [ ] `accounts/0068_outboxmessage` is the **only** new schema migration; the other touched migration files are `elidable=True` annotations on already-applied migrations (no schema change).
- [ ] `migrate_schemas --shared` creates `OutboxMessage` in **public** only (it's a SHARED_APPS model); no per-tenant copy expected.
- [ ] `entrypoint.sh` change: `relay_outbox` runs **before** the server and is **non-fatal** (a failure must not block boot).
- [ ] No new **required** env vars; prod still fails closed without `CELERY_BROKER_URL` / `REDIS_URL` (deploy check unchanged).

**Money / order path (extra scrutiny)**
- [ ] Order-number widening is format-compatible — `ORD-<uppercase hex>`, ≤ 20 chars, still matches `router/index.js` `/order/:n([A-Z]+-[A-Z0-9]+)`; both generators (`menu.views` + the inline marketplace one) changed in lockstep.
- [ ] ASYNC-1 outbox: `enqueue` persist is **production-gated** (`not DEBUG`) and **fails open**; re-dispatch is idempotent via the ASYNC-4 dedup keys; `select_for_update(skip_locked)` makes the relay multi-container safe.
- [ ] FE-2 money-path components (Cart, Marketplace checkout, WaiterPage settle/rating) — confirm `placeOrder` / `placeInAppOrder` / settle / cashout logic stayed in the **parent**, children are presentational + emits.

**Auth / identity (security-relevant)**
- [ ] AUTHZ-1: owner endpoints now `permission_classes=[IsTenantOwner]` — spot-check that no owner route lost its `tenant_id` check in the migration; the 3 deliberate Category-C predicates are documented.
- [ ] IDENTITY-1: `CustomerSessionAuthentication` mounts don't newly 403 anonymous callers on optional-auth routes (guest cart / table-QR / marketplace track stay `AllowAny`).

**Frontend**
- [ ] `verify:i18n` passes on the merge result and no template renders a raw key (FE-1 collapsed the catalog to one source per locale — `messages.js` is gone).
- [ ] Behaviour-preserving: the ~62 extracted components are props-in/events-out with isolated vitest suites; no store/router/API contract changed.

**QA before tagging as launch-ready**
- [ ] 390 px mobile spec + cross-subdomain CSRF e2e specs pass (the blocking Playwright gates).
- [ ] A manual smoke of one full order → pay → track → rate flow on a real tenant subdomain.

## Risk & rollback

Frontend changes are behaviour-preserving component extractions + an i18n de-dup (no runtime
behaviour change beyond fixing raw-key bugs). Backend changes are additive (outbox, throttle
principal) or hardening (entropy, authz policy layer) with tests; money/order logic was kept in
its existing call sites. Rollback is a standard revert of the merge; the only new table
(`OutboxMessage`) is inert if unused.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
