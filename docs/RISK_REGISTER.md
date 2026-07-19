# Kepoli — Risk Register (known structural debt)

> The honest output of a ground-up, 11-dimension adversarial architecture review
> (2026-07-10). Every future session should read this **before** a scaling or onboarding
> push, so nobody rediscovers this debt the hard way. Items are ranked by severity; each has
> a concrete failure scenario, the fix, and a rough effort. When you close one, strike it
> through and note the commit.
>
> **Overall verdict:** the architecture is **not poor** — it is genuinely good craftsmanship
> for a small team, with debt concentrated in a few foundational places. The items below are
> that concentrated debt. Fix the 3 critical items before onboarding paying tenants at volume.
>
> Effort key: **S** = hours · **M** = a few days · **L** = weeks · **XL** = multi-week project.
>
> **Execution tracker:** the multi-branch campaign working through these items — waves, lanes,
> collision map, and per-item real-vs-register status — lives in
> [`CAMPAIGN_PLAN.md`](CAMPAIGN_PLAN.md) (code-verified 2026-07-11; note several items there are
> corrected to their true state, e.g. FE-3 and OPS-2 are further along than this register said).

---

## Summary (ranked)

| ID | Area | Sev | One-line | Effort |
|---|---|---|---|---|
| **AUTHZ-1** | Auth | ◑ Core done | Authorization by-convention on a shared cross-subdomain cookie. **Backstop middleware + `IsTenantOwner` policy class (+ message variants) + single `user_owns_tenant_id` owner-check** shipped; **all 58 method-entry `_is_tenant_owner` guards migrated to `permission_classes`** (13 slices); dead `accounts._is_tenant_owner` helper deleted. Residual is by design: 3 Category-C predicates (mid-logic owner checks that return a *different* response, not 403) | L |
| **OPS-1** | DR | 🔴 Critical | Single Postgres, no replica/PITR → ~24h RPO, money loss on host failure. **OWNER/infra** | M |
| **OPS-2** | DR | 🔴 Critical | Backups on-host not off-box. **Shipping mechanism built** (off-box hook + freshness probe); owner S3 creds + restore drill remain | S |
| ~~**MONEY-1**~~ | Money | ✅ Done | ~~No balance-vs-ledger reconciliation~~ — `reconcile_wallet_balances` shipped | ~~S–M~~ |
| **IDENTITY-1** | Auth | ◑ Partial | Dual identity: customer invisible to DRF. **Keystone shipped** (`CustomerSessionAuthentication` + `IsCustomer`/`IsOrderOwner`; customer is now `request.user`), proven on 3 views (incl. a live voucher `FieldError` fix); ~55-view sweep remains | L |
| **STRUCT-1** | Structure | 🟠 High | God-files (13.4k / 8.7k lines), no `OrderService`, 574-line order method. **Awaiting owner go-ahead** (money-path refactor) | L |
| **TEST-1** | Testing | ✅ Done | count-floor + DB-fail-not-skip + Playwright E2E in CI + real threaded money/isolation DB tests | M |
| **DATA-1** | Data | ◑ Partial | Loose cross-schema refs — **orphan reconcile shipped** (`reconcile_order_refs`); global-unique `order_number` remains (deferred, large ripple) | S/L |
| ~~**API-1**~~ | API | ✅ Done | ~~No API versioning~~ — **`/api/v1/` alias shipped** (legacy `/api/` unchanged & default, `reverse()`-invariant via `v1` namespace) | ~~S~~ |
| **ASYNC-2** | Async | ✅ Addressed | Named `cron.<command>` tasks (name *is* the allowlist), `cron.*`→`cron` queue route, transient-DB retry/backoff; worker consumes `-Q notifications,cron` | M |
| **ASYNC-1** | Async | ◑ Partial | Silent lossy inline task fallback — **deploy-blocking Error (kepoli.E002) + loud prod log** shipped; durable-outbox/runtime-dispatch remains | M |
| **MULTITENANCY-1** | Tenancy | 🟠 High* | Schema-per-tenant caps scale. Provisioning atomic-index landmine **fixed**; the (a)–(c) scale ceiling is a conscious **owner decision** | XL |
| ~~**MONEY-2**~~ | Money | ✅ Done | ~~Driver-payout unlocked "owed" check~~ — driver row now locked in `record_driver_payout` | ~~S~~ |
| ~~**MONEY-3**~~ | Money | ✅ Done | ~~Dormant Stripe webhook trusts metadata~~ — now credits settled `amount_total`, paid-only | ~~S~~ |
| **OPS-3** | Ops | 🟡 Med | Redis SPOF; sessions cache-only (eviction logs users out) — needs a **schema-pinned session backend** (naive `cached_db` BREAKS under django-tenants). Not yet started | M |
| **ASYNC-3** | Async | 🟡 Med | WS + full-rate polling both run → realtime cost without the load savings | M |
| **ASYNC-4** | Async | ◑ Partial | `acks_late` redelivery double-sends — **dedupe shipped**; DLQ/reject-alert remains (broker/infra work) | S/M |
| **FE-1** | Frontend | 🟡 Med | i18n dual-source: 4 coordinated edits per string → raw-key bugs | M |
| **FE-2** | Frontend | ◑ Partial | Six 2.5–3.7k-line mega-pages — **3 CustomerAccount tabs extracted** (reservations/reviews/profile; 3654→2963 lines); more tabs + other pages in progress | L |
| **FE-3** | Frontend | ◑ Partial | Locale catalogs — **code-split + lazy Sentry already shipped** (`a84cc7d`); only a small `main.js` first-paint residual remains | S–M |
| **SER-1** | API | ◑ Partial | Raw `request.data` money reads — **`QuantizedMoneyField` primitive + drawer amount** shipped (500→400). Scout found amounts already funnel through `_money()` → the rest is **defense-in-depth**, migrate opportunistically | L |
| ~~**SCHEMA-1**~~ | API | ✅ Done | ~~OpenAPI via legacy `generateschema`~~ — **drf-spectacular shipped** (collision-free operationIds, CI validates) | ~~S~~ |
| **DATA-2** | Data | ◑ Partial | `CustomerOrderRef` mirror drift — `post_delete` + **voided/comped item filter** + **content-drift reconcile** shipped; effectively complete | S |
| **DATA-3** | Data | 🟡 Med | `Dish` + 4-key JSON is not a real multi-vertical catalog. **Product decision** (build when a non-food tenant is real) | L |
| ~~**DATA-4**~~ | Data | ✅ Done | ~~Directory opt-in has no data prerequisite~~ — serializer now requires city+coords to opt in | ~~S~~ |
| ~~**DATA-5**~~ | Data | ✅ Done | ~~Four `Profile` mirrors, no periodic reconcile~~ — **`reconcile_profile_denorms` shipped** (per-tenant, reuses the 3 recompute fns) | ~~M~~ |
| **STRUCT-2** | Structure | 🟡 Med | 215 migrations, `Order` field sprawl, no squashing → slow per-schema deploys | M |
| **API-2** | API | 🟢 Low | Contract sprawl / inconsistent naming / RPC verbs in 3 god url-files (client-breaking renames — defer) | M |
| **OPS-4** | Ops | 🟢 Low | ⏭️ Re-scoped — `daphne` is a registered `INSTALLED_APP` (ASGI runserver), NOT dead weight; skipped as low-value | S |

\* MULTITENANCY-1 is "high" as a *strategic* decision to make consciously, not an urgent bug.

---

## 🔴 Critical

### AUTHZ-1 — Authorization is a copy-pasted convention on a shared cookie
**Where:** ~198 of ~262 endpoints (no permission class); `_is_tenant_owner` duplicated in
`menu/views.py` and `accounts/views.py` (divergent signatures) + predicate in 5+ places;
`SESSION_COOKIE_DOMAIN = ".<suffix>"`.
**Failure scenario:** A developer adds an owner endpoint and forgets the
`if not _is_tenant_owner(request): return 403` line (or writes a bespoke check that validates
the *role* but not `tenant_id` — exactly the Z-report bug). Because the session cookie is valid
on every tenant subdomain, an authenticated owner of tenant A changes one id in the URL and
reads tenant B's revenue, PII, and customer list. The Z-report leak and order-status IDOR we
already fixed were symptoms of this class, not isolated bugs.
**Fix:** (1) Unify identity — see IDENTITY-1 — so customers are `request.user`. (2) Replace the
inline guards with **one tested policy module**: `IsTenantMember`, `IsTenantOwner` (always
tenant-match), `IsOrderOwner`, `IsPlatformAdmin`, applied via `permission_classes` +
`has_object_permission` on detail views. Delete both `_is_tenant_owner` helpers. (3) Add a
**defense-in-depth backstop**: a `TenantScopedManager` (or middleware assertion) so any
public-schema object returned must carry `tenant_id == request.tenant.id` — a forgotten filter
becomes a fail-closed no-op instead of a leak.
**Effort:** L. Do it in slices (backstop first — it protects everything immediately).
**Progress (slice 1 — backstop, 2026-07-10):** `CrossTenantSessionGuardMiddleware`
(`config/middleware.py`, registered after `AuthenticationMiddleware`) now **downgrades to
anonymous** any tenant-owner/staff session on a *foreign* tenant's host (mismatched or null
`user.tenant_id`), so a forgotten per-view guard fails closed (401/403) instead of leaking —
the Z-report/IDOR class is dead app-wide. A downgrade rather than a 403 because the shared
cookie makes "owner of A browsing restaurant B as a guest" the normal case; superusers and
platform admins are exempt (matching `_is_tenant_owner`/`IsPlatformAdmin`); sessions are not
flushed (customer identity may share the session). Logged as `cross_tenant_session_downgraded`.
Tests: `tests/test_cross_tenant_session_guard.py` (13, no DB). A query-level backstop
(scoped manager) was evaluated and deliberately **deferred**: an inventory of all public-model
call-sites found the unscoped majority is *legitimately* cross-tenant (driver app, customer
marketplace, wallet ledger, admin, reconcile/GDPR commands), so auto-scoping would break the
app for marginal gain; revisit after IDENTITY-1 lands. The one flagged query
(`menu/views.py` CustomerRating average) is by-design platform-wide (per model docstring) and
now commented as such.
**Progress (call-site migration, slice 1 — 2026-07-17):** IDENTITY-1 is done (the customer/driver
view sweep completed), unblocking this. `IsTenantOwner` now carries a `message` (`"Owner access
required."`) so DRF renders the exact legacy 403 body when it denies an *authenticated* non-owner;
a sibling `IsTenantOwnerAccessDenied` preserves the other legacy text (`"Access denied."`). First 8
`menu/views.py` owner views migrated from an inline `if not _is_tenant_owner(request): return 403`
to declarative `permission_classes = [IsTenantOwner|…AccessDenied]` (OwnerInvoiceView,
OwnerCommissionStatementView, OwnerDataExportView, OwnerWalletFloatView, DrawerCurrentView,
OwnerIngredientLowStockView, OwnerRecipeLineDetailView, OwnerClosureDateDeleteView). Byte-for-byte
behavior-preserving: authenticated non-owner → 403 same body; anonymous → 401 (`NotAuthenticated`)
same as the old `IsAuthenticated` gate. A scout classified all ~56 sites first: **zero** were
plain-403 (every guard has a custom body, hence the `message` approach); **3 are Category-C**
predicates (`_can_access_order`, `StaffOrderListView`, `OwnerZReportView._require_owner`) that use
`_is_tenant_owner` mid-logic where non-owners get a *different valid response*, not a 403 — those
**stay** and the helpers can't be fully deleted.

**Slice 2 (2026-07-17):** the 4 remaining cash-drawer views (`DrawerOpenView`,
`DrawerTransactionView`, `DrawerCloseView`, `DrawerHistoryView`) migrated to
`permission_classes = [IsTenantOwner]`, completing the cash-drawer feature's owner-gating
(`DrawerCurrentView` landed in slice 1). Chosen as a coherent, low-risk batch because their
tests all live in `test_cash_drawer.py` and call the view **methods directly** — so the happy-path
tests (which `@patch("menu.views._is_tenant_owner")` and bypass dispatch) keep passing unchanged,
and only the 4 owner-denial tests needed the `.as_view()` + force-authenticated-non-owner rewrite
(shared `_assert_owner_required` helper). **Deliberately NOT batched:** the `.as_view()`-heavy test
files (e.g. `test_customer_notes_views.py` — 18 dispatch-level tests that patch `_is_tenant_owner`)
would each need every happy-path test rewritten to a real owner principal, so those views get their
own slices.

**Slice 3 (2026-07-17):** the 3 owner analytics views — `OwnerBestSellersView`,
`OwnerRevenueChartView` (→ `IsTenantOwnerAccessDenied`), `OwnerRepeatAnalyticsView`
(→ `IsTenantOwner`). Their `test_analytics_and_chart_views.py` tests migrated **transparently**
(they set a real non-owner principal and the inline guard already delegated to
`user_owns_tenant_id`, so `IsTenantOwner` yields identical results). Two nuances confirmed here,
worth recording:
- **Anonymous → 403, not 401** (corrects the slice-1/2 commit phrasing). With only
  `SessionAuthentication` in the stack, a permission failure raises `NotAuthenticated`, but DRF's
  `handle_exception` **downgrades it to 403** because `SessionAuthentication.authenticate_header`
  returns `None` (no `WWW-Authenticate`). So both the old `[IsAuthenticated]` gate and the new
  `[IsTenantOwner]` gate return **403** for anonymous — behavior preserved, mechanism now understood.
- **`MagicMock(spec=User)` non-owner fixtures must pin `is_superuser=False` / `is_platform_admin=
  False`.** `user_owns_tenant_id` short-circuits `True` on a truthy value there, and a `spec=User`
  mock returns a truthy `Mock` for any unset attribute — so a "staff" fixture that only sets
  `role=STAFF` reads as a **superuser** and is *allowed*. `test_repeat_analytics._staff()` only
  "worked" before via a now-dead `_is_tenant_owner=False` patch; fixed the fixture + dropped the
  patch. This is a landmine for every future denial test in this migration.

**Slice 4 (2026-07-17):** the ingredient/recipe owner views — `OwnerIngredientListCreateView`,
`OwnerIngredientDetailView`, `OwnerIngredientAdjustView`, `OwnerDishRecipeView` (all →
`IsTenantOwnerAccessDenied`), completing the ingredient group (`OwnerIngredientLowStockView` +
`OwnerRecipeLineDetailView` landed in slice 1). First **multi-method** classes in the migration:
every method was owner-gated with a per-method guard, so class-level `permission_classes` collapses
2–3 guards into one declaration without over-gating. `OwnerIngredientDetailView`'s `_get(pk)` helper
does only the 404 lookup (the 403 was per-method, now on the class) so it stays. Migrated
**transparently** — `test_ingredients.py` already force-authenticates real owner/staff fixtures that
correctly pin `is_superuser=False`/`is_platform_admin=False` (the slice-3 landmine is absent here).
Also removed the now-unused `_IsAuthenticated` alias import.

**Slice 5 (2026-07-17):** the customer owner views — `OwnerCustomerNotesView`,
`OwnerCustomerLoyaltyGrantView`, `OwnerCustomerListView` (all → `IsTenantOwnerAccessDenied`).
`test_owner_customer_list.py` migrated transparently (no `_is_tenant_owner` patch, landmine-safe
fixtures). `test_customer_notes_views.py` hit the slice-3 landmine head-on: its two
`test_non_owner_gets_403` tests used a **real `_owner()`** principal + relied on a
`_is_tenant_owner=False` patch to force the denial — once that patch goes dead, the owner would
*pass*. Fixed by adding a landmine-safe `_staff()` fixture (pinned `is_superuser`/`is_platform_admin`
False) and pointing the denial tests at it; the happy-path `_is_tenant_owner=True` patches are now
harmless no-ops (left in place). This is the confirmed template for the remaining `.as_view()`-heavy
files.

**Slice 6 (2026-07-17):** the wallet owner views — `OwnerWalletTopupView`,
`OwnerWalletHistoryView` (→ `IsTenantOwnerAccessDenied`). Transparent (no `_is_tenant_owner` patch,
landmine-safe fixtures in `test_owner_wallet_views.py`).

**Slice 7 (2026-07-17):** four multi-method owner classes — `OwnerPromotionListCreateView`,
`OwnerPushSubscribeView`, `OwnerLoyaltyView` (→ `IsTenantOwnerAccessDenied`),
`OwnerClosureDateListCreateView` (→ `IsTenantOwner`). All per-method-guarded on every method, so
class-level collapses the pair. **Key heuristic confirmed: a test file with ZERO
`_is_tenant_owner` patches migrates transparently** — the inline guard already delegated to
`user_owns_tenant_id` (the exact function `IsTenantOwner` uses), so any denial test green today stays
green. The slice-3 landmine only lives in files that *patch* `_is_tenant_owner` (the patch masks
whether the fixture independently yields the right result). 96 tests across 5 files, no changes.

**Slice 8 (2026-07-17):** `OwnerSectionListCreateView` / `OwnerSectionDetailView` (→
`IsTenantOwnerAccessDenied`) — the first patch-using file (`test_table_sections.py`, 13 patches).
Its shared `_req()` used a **bare `MagicMock`** user (truthy `is_superuser` → the slice-3 landmine),
which the happy paths only survived via the `_is_tenant_owner=True` patch bypass, and the one
`test_non_owner_denied` faked denial via `_is_tenant_owner=False`. Upgraded `_req()` to a real
landmine-safe `_owner()` (+ a `_staff()` for the denial test). **New wrinkle:** one happy-path test
`patch.dict`-mocks `sys.modules["accounts.models"]` (to stub the tenant-member whitelist query), so a
function-local `from accounts.models import User` in the fixture got the *mocked* User and its `role`
stopped equalling the real `TENANT_OWNER` enum → owner denied. Fixed by importing `User` at the test
module level (bound to the real class before any test runs), so the fixture keeps the real role even
inside the `patch.dict` block. The waiter-ack tests in the same file patch `_is_tenant_owner` for a
*different* (un-migrated) view and are untouched.

**Slice 9 (2026-07-17):** `OwnerCampaignView` (→ `IsTenantOwner`). Despite the `_is_tenant_owner`
patches, it migrated **transparently** — both test files (`test_owner_campaigns.py`,
`test_b1_email_retention.py`) already force-authenticate a landmine-safe `_owner_user()` and set
`req.tenant`, and there are no denial tests — so the `=True` patches are now harmless no-ops. (Not
every patch-using file needs the landmine fix; only ones whose denial tests fake denial via the
patch, or whose fixtures aren't independently owner-valid.) 36 tests, no changes.

**Slice 10 (2026-07-17):** `OwnerPromotionDetailView` (first shared-lookup-helper case) +
`OwnerWaitlistView`. In `OwnerPromotionDetailView` the 403 lived inside `_get_promo` (called by
get/patch/delete); moved it to `permission_classes = [IsTenantOwnerAccessDenied]` and slimmed
`_get_promo` to the 404 lookup only (dropped its now-unused `request` arg + updated 3 callers). Order
preserved: a non-owner still 403s before the method (permission runs first), and the 404 only reaches
a real owner — same as the old helper checking owner-then-existence. `OwnerWaitlistView` needed a
**third message variant** — added `IsTenantOwnerForbidden` (`message="Forbidden."`) alongside the
`IsTenantOwner`/`...AccessDenied` pair; its `test_permissions` message-contract test added. Both
files (`test_owner_promotions.py`, `test_waitlist_and_push.py`) are 0-patch → transparent.

**Slice 11 (2026-07-17):** the `accounts/views.py` non-staff 2-arg sites — `OwnerFlashSaleListView`,
`OwnerFlashSaleOptInView` (post+delete), `OwnerDeliveryZoneView`, `OwnerDeliveryRadiusUpdateView`
(all → `IsTenantOwner`). The accounts `_is_tenant_owner(request, tenant)` helper is
`user_owns_tenant_id(request.user, request.tenant.id)` — identical to `IsTenantOwner` since the
`tenant` passed is always `request.tenant`. The `tenant = getattr(request, "tenant", None)` line +
its `if tenant is None: 400` guard stay (the bodies use `tenant`); only the owner 403 moved.
Transparent (both `test_flash_sales.py` / `test_admin_delivery_views.py` are 0-patch, landmine-safe
fixtures). `accounts._is_tenant_owner` is now used only by the 3 staff sites.

**Slice 12 (2026-07-17):** the staff endpoints — `OwnerStaffListCreateView` (get+post),
`OwnerStaffDeleteView` (`_get_staff` shared helper) → `IsTenantOwnerStaffForbidden`. Their 403 body
uniquely carries a `code` (`{"detail": "Owner access required.", "code": "forbidden"}`, asserted by
a test), which a string `message` can't reproduce. Solved by giving the permission class a **dict**
`message`: DRF's `permission_denied` raises `PermissionDenied(detail=message)` and the exception
handler uses a dict `detail` as the response body verbatim — confirmed (`test_owner_staff_views`
green, `resp.data["code"]=="forbidden"`). `_get_staff`'s 403 moved to the class; its 404 lookup
stays. All 8 `accounts/views.py` call sites are now migrated — the accounts `_is_tenant_owner` helper
is **dead** (no view calls it) but retained for now (3 test files still patch/unit-test it;
deleting it is a separate cleanup).

**Slice 13 — call-site migration COMPLETE (2026-07-17):** `OwnerAnalyticsExportView` (the ordering
gotcha) migrated via a **`get_permissions()`** override — it returns `AllowAny` on the public
schema / no-tenant path (so the view's own `400 "Not available on public schema."` still answers
first) and `IsTenantOwner` otherwise (403 for a non-owner). This preserves the 400-before-403
ordering a class-level attribute would have broken. `test_analytics_and_chart_views` green (400 for
no-tenant + public, 403 for outsider, CSV for owner), no test change.

**Call-site migration is done.** Every method-entry `_is_tenant_owner` guard across `menu/views.py`
and `accounts/views.py` (58 sites) is now a declarative permission (`IsTenantOwner` +
`...AccessDenied` / `...Forbidden` / `...StaffForbidden` message variants for exact-body
preservation, and `get_permissions()` for the one ordering exception). What remains is **by design**:
the **3 Category-C predicates** (`_can_access_order`/`CustomerOrdersByPhoneView` line ~4206,
`StaffOrderListView` line ~4341, `OwnerZReportView._require_owner`) that use `_is_tenant_owner`
mid-logic where a non-owner gets a *different valid response*, not a 403 — so the `menu`
`_is_tenant_owner` helper stays (serves those). The **accounts** `_is_tenant_owner` helper (dead
after the migration — no view called it) has now been **deleted** (2026-07-19): its owner-check
semantics live in `sales.permissions.user_owns_tenant_id`, fully covered by
`tests/test_permissions.py::UserOwnsTenantIdTests`; the 9 delegate unit-tests were removed and two
now-dead `patch("accounts.views._is_tenant_owner", …)` no-ops (in `test_ops5b_admin_security.py` /
`test_ops5_billing.py`, both of which call `view.post()` directly and so never hit the permission
layer) were dropped. This closes AUTHZ-1's core deliverable: authorization is a tested policy layer,
not a copy-pasted convention.
**Source:** API/auth review (rated the authz *architecture* **poor**), security-isolation review.

### OPS-1 — Single Postgres, no replica, no PITR
**Where:** `docker-compose.coolify.yml` (one `postgres` service); no WAL archiving/replica.
**Failure scenario:** The VPS disk fails at 14:00. The last dump ran at 02:00. Every wallet
top-up, order, and payout from the last 12 hours is gone — unrecoverable. Your own runbook
already admits "customers may need manual wallet adjustments." For a money app this is
business-ending, not "degraded."
**Fix:** Enable continuous WAL archiving / PITR (e.g. `pgBackRest` or a managed Postgres with
PITR), and/or a streaming replica. Target RPO ≤ 5 min for the money tables.
**Effort:** M.
**Source:** ops/scale review (CRITICAL).

### OPS-2 — Backups live on the same host they protect
**Where:** backup scripts write to local disk on the VPS.
**Failure scenario:** The VPS is lost (provider incident, ransomware, accidental teardown).
The database *and* every backup vanish together. A backup you can't reach when the host is
gone is not a backup.
**Fix:** Ship every backup **off-box** immediately after creation (S3-compatible object store
with versioning + lifecycle + a restore drill). This single change also materially mitigates
OPS-1's blast radius.
**Status (code-verified 2026-07-11):** the shipping *mechanism* is already built and wired —
`infra/coolify/install_backup_cron.sh --remote-copy-cmd` runs an owner-supplied rclone/rsync/scp
after each daily `pg_dump`, alerts on copy failure, and `backup_freshness_probe.sh` catches a
silently-dead cron (see `infra/COOLIFY_DB_BACKUP_RUNBOOK.md`). What remains is **OWNER-only** and
un-automatable by an agent: create an S3-compatible bucket + credentials, install/configure rclone
on the prod VPS, re-run the installer with `--remote-copy-cmd`, and perform a restore drill. Reframe
as "mechanism built, disabled by default, awaiting owner enablement," not "not started."
**Effort:** S. **This is the cheapest critical fix — do it first.**
**Source:** ops/scale review (CRITICAL).

---

## 🟠 High

### MONEY-1 — No `balance == sum(ledger)` invariant  ✅ ADDRESSED (2026-07-10)
**Where:** `Customer.wallet_balance` / `Tenant.float_balance` (denormalized) vs
`WalletTransaction` / `TenantFloatTransaction` (journals). No reconciliation job.
**Failure scenario:** A process crashes between writing the journal row and updating the
denormalized balance (or any code path updates one without the other). The balance silently
drifts from the ledger. Nothing detects it; it compounds; the first symptom is a customer
dispute you can't explain.
**Resolution:** `accounts/management/commands/reconcile_wallet_balances.py` reconciles both
ledgers by asserting `balance == balance_after of the latest ledger row` — a **sign-agnostic**
anchor (`amount` is a positive magnitude and `adjustment` can go either way, so summing signed
amounts is ambiguous; the recorded `balance_after` is not). Categories: OK / **DRIFT** (fixable)
/ **ORPHAN** (non-zero balance, no ledger — never auto-fixed) / **CHAIN** (`--deep`: a row whose
balance step ≠ its amount). Default mode is read-only detect + alert (on the `payments` channel);
`--fix` repairs only the unambiguous DRIFT case under the wallet service's `select_for_update`
lock, re-checking under the lock. Scheduled on Beat every 6h **detect-only** (Beat never
auto-mutates money; a human runs `--fix` after triage). Verified: every active ledger writer
(service + loyalty redeem + admin bulk bonus) sets `balance_after` to the persisted balance, so
the check does not false-positive. Tests: `tests/test_reconcile_wallet_balances.py` (7, green on
Postgres).
**Source:** money review, data-model review.

### IDENTITY-1 — Two disjoint identity systems; the customer is invisible to DRF  ◑ KEYSTONE SHIPPED (2026-07-11)
**Where:** staff → `request.user` (SessionAuth); customer → `request.session["customer_id"]`
(~49 raw reads in `accounts/views.py`), never in `request.user`.
**Failure scenario:** You *cannot* write an `IsOrderOwner` permission class for customer
resources because the permission layer can't see the customer — so ownership is forced into
every handler body and into response-shaping. This is the structural reason AUTHZ-1 exists and
why the order-status IDOR was possible.
**Fix:** A `CustomerSessionAuthentication` DRF auth class that hydrates `request.user` from
`session["customer_id"]` (or a custom auth backend). Then customers, staff, owners, drivers,
and admins all flow through one auth stack — the prerequisite for AUTHZ-1's policy layer.
**Effort:** L (touches ~60 customer views), but it's the keystone.

**Shipped (keystone + bounded slice):**
- `accounts/authentication.py::CustomerSessionAuthentication` — hydrates the signed-in
  `Customer` onto `request.user` from `session["customer_id"]`. Deliberately a plain
  `BaseAuthentication` (NOT a subclass of DRF `SessionAuthentication`): customer POSTs run today
  with an empty auth stack and thus **no CSRF enforcement**, so subclassing would newly 403 every
  customer POST on CSRF. `authenticate_header` is set so unauthenticated requests render as **401**
  (matching the old hand-rolled "Not authenticated"), not 403. Fails closed (returns `None`) on
  absent/stale session PK.
- `Customer.is_authenticated` / `.is_anonymous` properties (`accounts/models.py`) — makes the
  model usable AS a principal; the two identity systems stay disjoint (a Customer is never a User).
- `accounts/permissions.py::IsCustomer`, `IsOrderOwner` — the single home for the
  `customer_id`-ownership predicate that ~5 IDOR-prone views each re-implemented. `IsOrderOwner`
  is usable both as a DRF object permission and as a plain predicate (so views keep their specific
  coded/​graceful-degradation responses).
- **Converted 3 views:** `CustomerWalletRedeemVoucherView` (also fixes a **live bug** — it did
  `Customer.objects.get(user=request.user)`, but `Customer` has no `user` field → `FieldError` for
  any real caller; the old tests masked it by injecting `request.customer`), and
  `MarketplaceOrderCancelView` (inline `int==int` → shared `IsOrderOwner`, exact 403 preserved).
- Tests: `tests/test_identity_customer_auth.py` (16, no DB) + rewritten voucher/cancel view tests
  to the real auth path (force-authenticated `Customer` principal).

**Landmine found (guides the deferred sweep):** now that `Customer.is_authenticated` is `True`,
any multi-role view that hydrates the customer onto `request.user` **and** has a
`request.user.is_authenticated` *staff* gate (e.g. `DeliveryRatingView`'s `role=="restaurant"`
branch) would let a customer principal pass the staff gate. Such branches must additionally check
the principal is a `User` (not a `Customer`) before the sweep flips their `authentication_classes`.

**Update (2026-07-14):** `RideTipView` (`accounts/ride_views.py`) — the last single-role
customer view living outside the two hot files (`menu/views.py`, `accounts/views.py`) — is now
migrated (dead `_get_rider` helper removed). The remaining sweep is entirely inside those two
hot files (partially done across two prior rounds) plus the permanently-skipped landmine views
(6 driver views in `ride_views.py`, `DeliveryRatingView`, staff/owner multi-role branches).

**Update (2026-07-16):** first hot-file slice — 5 single-role, non-money `accounts/views.py`
wallet/push views (`CustomerWalletPayTokenView`, `CustomerWalletChargeRequestsView`,
`CustomerWalletChargeDeclineView`, `CustomerPushSubscribeView`, `CustomerWalletView`) migrated.
A full survey of the ~40 remaining raw `session["customer_id"]` reads across both hot files
classified the rest: 11 driver-role views (`accounts/views.py` `Driver*`) need a not-yet-built
`IsDriver` permission first (a plain `IsCustomer` would under-authorize — any customer, not just
drivers, would pass); `PlaceOrderView`/`MarketplacePlaceOrderView` are money-mutating **and** must
keep serving anonymous/guest orders, so they need `CustomerSessionAuthentication` added while
keeping `permission_classes=[AllowAny]` and duck-typing `request.user`, not a plain flip; 3 views
(`CustomerOrdersView`, `CustomerMarketplaceOrdersView`, `CustomerReservationsView`) currently
degrade to an empty list for anonymous callers rather than 401 — flipping to `IsCustomer` would
be a real behavior change, deferred pending a frontend check; the rest are the already-known
landmine/money views (`DeliveryRatingView`, `CustomerOrderCancelView`, wallet transfer/approve).

**Update (2026-07-16, driver slice):** all **12 driver views** in `accounts/views.py`
(`DriverRegisterView`, `DriverStatusView`, `DriverPositionUpdateView`, `DriverJobListView`,
`DriverJobAcceptView`, `DriverJobDeclineView`, `DriverJobStatusUpdateView`, `DriverEarningsView`,
`DriverCashoutView`, `DriverCashoutCancelView`, `DriverCashoutHistoryView`, `DriverDeliveriesView`)
now authenticate via `CustomerSessionAuthentication` + `IsCustomer`.

**Design decision — no `IsDriver` permission class (deliberate).** The earlier survey assumed the
driver slice was blocked on building `IsDriver`. On reading the code that is the *wrong* shape: the
driver gates are **not uniform** and each carries its own response contract — `is_driver` → **404**
`"Driver account not found."`, while `DriverJobAcceptView` needs `is_driver + driver_approved +
is_driver_online` → **403** `"Driver must be approved and online to accept jobs."`, and
`DriverStatusView.get` is deliberately ungated (it reports `driver_status:"none"` to a customer who
never applied). A permission class returns DRF's generic 403 and would silently break all three
contracts for the driver app. So `IsCustomer` gates the *principal* and each view keeps its own
gate reading `request.user` — which still achieves IDENTITY-1's goal (no raw session read; the
driver is `request.user`) and **removes one DB query per driver request**. A real `IsDriver` policy
class belongs to AUTHZ-1 and needs a response-contract decision + a frontend audit first.

Two things deliberately left as real DB queries (they are NOT identity reads and must not be
"optimized" onto the principal): (1) `DriverJobStatusUpdateView`'s approval **re-check** at the
DELIVERED transition (`Customer.objects.filter(pk=..., driver_approved=True).exists()`) — the
principal was hydrated at auth time and approval may have been revoked since, and this gate guards
the earnings credit (RISK OPS-5f); (2) `DriverJobAcceptView`'s `select_for_update` driver-row mutex.

**Follow-up noted:** `accounts/throttles.py::_CustomerThrottle` still keys on
`request.session["customer_id"]` rather than `request.user`. Behavior is unchanged today (login
still populates the session), but it is now a latent inconsistency: if a later slice drops the
session dependency (e.g. customer-CSRF/token hardening), every customer/driver throttle would
silently fall back to per-IP bucketing. Migrate it when that slice lands.

**Update (2026-07-16, optional-auth slice — first `menu/views.py` conversions):**
`OrderEligibilityView`, `CustomerOrderStatusView` and `CustomerOrderRateView` migrated. These are
**optional-auth**, not single-role: each must keep serving anonymous callers (a guest cart, a
table-QR diner, the coded `not_order_owner` 403), so they pair
`authentication_classes = [CustomerSessionAuthentication]` with **`permission_classes = [AllowAny]`**
and branch on the principal rather than gating on it. `IsCustomer` would 401 anonymous callers and
break all three contracts. This establishes the pattern the remaining optional-auth money views
(`PlaceOrderView`/`MarketplacePlaceOrderView`) need.

Shipped with it:
- **`accounts/permissions.customer_or_none(request)`** — the optional-auth primitive (returns the
  `Customer` principal or `None`; never a staff `User`), so views stop re-reading the raw session.
- **`CustomerSessionAuthentication` is now session-safe.** It did an unguarded
  `request.session.get(...)`; `CustomerOrderStatusView` had previously read the session behind its
  own `try/except` and degraded to anonymous, so mounting the auth class on it would have turned
  that tolerated case into a **500 raised from inside the auth stack**. Absent/unusable session
  state now fails closed to anonymous. (Latent for every already-converted view too.)
- **Six duplicated ownership comparisons collapsed into one `IsOrderOwner` call.**
  `CustomerOrderStatusView` re-implemented the `customer_id` check **five more times** below its
  gate — in two subtly different forms (`int()==int()` and `str()==str()`) — each guarding a
  separate leak (restaurant feedback, wallet balance, delivery/driver block, `can_cancel`,
  `delivery_code`). All now read the single `_owns` predicate. This duplication is exactly the
  IDOR class AUTHZ-1/IDENTITY-1 exist to kill; `ruff` caught it (the removed variable was still
  referenced), not the tests. `CustomerOrderRateView` also stopped re-fetching the linked customer
  — the ownership gate already proves `request.user` is the owner — and its docstring no longer
  claims "No authentication required" (false since OPS-5e added the gate).

**Update (2026-07-16, money slice):** the money-mutating customer views are migrated —
`CustomerWalletChargeApproveView`, `CustomerWalletTransferView`, `CustomerTopUpIntentView`
(`accounts/views.py`), `CustomerOrderCancelView`, `CustomerOrderPayWalletView` (`menu/views.py`).
The slice split three ways, and **the ordering of each view's own checks decided the treatment**:
- `IsCustomer` only where the handler already 401'd *unconditionally, first*
  (`CustomerWalletChargeApproveView`).
- **`AllowAny` + `customer_or_none`** where a **feature-flag gate must answer before auth**:
  `CustomerWalletTransferView` (`WALLET_P2P_ENABLED` → 403 "not enabled") and
  `CustomerTopUpIntentView` (`PSP_TOPUP_ENABLED` → `{"enabled": False}`, its docstring's "safe to
  call always" contract). A permission class runs in `initial()`, *ahead of* `post()`, so
  `IsCustomer` would turn those into 401s. `test_customer_wallet_transfer.py::
  test_disabled_returns_403_before_anything_else` ("Even with a valid-looking session, the flag
  gate wins") pins that ordering deliberately — the test caught the intent, not review.
- **`AllowAny` + `IsOrderOwner`** for the two order views, whose non-owner 403 **is the sign-in
  prompt** ("Sign in to cancel this order") an anonymous caller is meant to receive, and which
  check order-existence (404) first. Both had re-implemented the ownership comparison inline.

**Known cost, accepted:** mounting `CustomerSessionAuthentication` makes DRF hydrate the principal
in `initial()`, so views that previously used only the raw session *id* (transfer, charge-approve)
now do one extra `Customer` lookup — including on the flag-disabled path, which used to be DB-free
(that test file's "runs before any DB access" premise is now only true because the tests
force-authenticate). This is the keystone's uniform cost, already paid by every converted view, and
it buys the declarative gate. Response ordering is unchanged.

**Bug found and fixed separately** (see the `fix(api): throttled customer requests 500 instead of
429` commit): `config/exceptions.exception_handler` — the **global** DRF handler — logged
`user.username` on `Throttled`. `Customer.is_authenticated` is True but `Customer` has no
`username`, so the handler raised `AttributeError` and a throttled customer/driver request returned
**500 instead of 429**. Live on `main` since the keystone via `CustomerWalletRedeemVoucherView`
(+ `VoucherRedeemThrottle`). This is the same family as the multi-role landmine above — **code that
assumes an authenticated principal is a staff `User`** — and it will keep biting; audit any
`request.user.<User-only-attr>` on a path a customer can now reach.

**Update (2026-07-17, marketplace-reads slice):** the two marketplace optional-auth reads —
`MarketplaceMenuView` (COD eligibility → `customer_or_none`) and `MarketplaceOrderStatusView`
(inline `_owns` → `IsOrderOwner`) — migrated. Exact mirrors of `OrderEligibilityView` /
`CustomerOrderStatusView` from the earlier optional-auth slice: `CustomerSessionAuthentication` +
`AllowAny`, personalise/gate on the principal rather than gating access. `MarketplaceOrderStatusView`
runs its ownership check *inside* a `schema_context(tenant.schema_name)`, which is safe because the
principal is hydrated in `initial()` (public schema, before the view switches schema) and
`customer_or_none` / `IsOrderOwner` do no query at call time. `MarketplaceOrderCancelView` right
after was already converted in an earlier round.

**Update (2026-07-17, place-order slice — the crown-jewel money path):**
`PlaceOrderView` (`menu/views.py`) and `MarketplacePlaceOrderView` (`accounts/views.py`) migrated.
The two turned out to be **different shapes**, which is the whole lesson of this slice:

- **`MarketplacePlaceOrderView` is pure optional-auth** — it runs on the public marketplace host,
  has **no** `request.user`/preview branch, only a session-`customer_id` link. Straight
  `CustomerSessionAuthentication` + `AllowAny` + `customer_or_none`, like the earlier optional-auth
  views.
- **`PlaceOrderView` is genuinely MULTI-ROLE** — it reads `request.user` in *two* places: a
  staff-preview gate (`can_preview`: `is_superuser`/`is_platform_admin`/`tenant_id`) AND
  `resolve_prepay_and_wallet`'s staff-exemption (`user.role`). Its auth stack is now
  **`[SessionAuthentication, CustomerSessionAuthentication]`** — SessionAuthentication first so a
  staff session still lands a `User` (and keeps its CSRF enforcement, which the customer path never
  had), CustomerSessionAuthentication second so a customer session lands a `Customer`. A session
  carries EITHER a staff user OR a `customer_id` (never both, per `_staff_session_conflict`), so
  exactly one principal resolves.

**The landmine was real and confirmed:** `Customer` has no `is_superuser` field, so the bare
`user.is_superuser` in `can_preview` would raise `AttributeError → 500` for a customer principal now
that `Customer.is_authenticated` is True. Hardened by gating on `_is_staff_user` (authenticated AND
`customer_or_none(request) is None` — i.e. a staff `User`) *before* reading any User-only attribute.
`resolve_prepay_and_wallet` was already safe (`getattr(user, "role", None)` → None for a Customer →
`is_staff=False`, same as the old AnonymousUser), so its behavior is unchanged. Regression test
`test_customer_principal_is_not_a_previewer` pins both halves (no 500; a customer does not get the
preview bypass). The test churn was significant — five money/order test files
(`test_place_order_view`, `test_a4_marketplace_cod`, `test_a5_commission`,
`test_r15b_r16_money_hardening`) had to move from "hand-set `request.session` + patch
`Customer.objects.get`" to force-authenticating a **real** `Customer` principal (a MagicMock no
longer passes `customer_or_none`'s class-name check).

**Update (2026-07-17, anon-degrading list views):** `CustomerOrdersView`,
`CustomerMarketplaceOrdersView`, `CustomerReservationsView` migrated. The register framed these as
blocked on a frontend check because *flipping to `IsCustomer`* (401 for anonymous) is a real
behavior change — but that framing conflated two things. The IDENTITY-1 goal (kill the raw
`session["customer_id"]` read, put the customer on `request.user`) is achieved by the **optional-auth
pattern** (`CustomerSessionAuthentication` + `AllowAny` + `customer_or_none`) with the `[]`-for-
anonymous degradation preserved **byte-for-byte** — no 401, no frontend change. Done that way. The
`IsCustomer` flip (make them 401) stays a **separate, optional** product hardening that would need
the frontend check; it is NOT required for IDENTITY-1 and is deferred.

**Update (2026-07-17, helpers + the DeliveryRatingView landmine):**
- **`_resolve_customer_from_request` DELETED** — it was dead code (no view has called it since
  `CustomerLinkReferralView` stopped in an earlier round; only a direct unit test remained). Removed
  the function + its `ResolveCustomerFromRequestTests`; that was the last raw session read in a
  helper.
- **`_tracking_request_owns_order`** now reads `customer_or_none(request)` instead of the raw
  session id; `OrderTrackingView` gained `CustomerSessionAuthentication` (stays AllowAny — a
  non-owner still gets basic tracking, the owner-only driver phone/live position stays gated). Added
  a direct unit test (the helper was previously only ever `patch`ed, never exercised).
- **`DeliveryRatingView`** — the multi-role landmine — converted. `role="customer"` and
  `role="driver"` now read the principal via `customer_or_none`; `role="restaurant"` is **hardened**:
  it required a staff owner via a bare `user.is_authenticated`, which a `Customer` principal now
  passes (`Customer.is_authenticated` is True). Guard added: `customer_or_none(request) is not None`
  → reject (a Customer can't write the owner→driver rating). Kept `[CustomerSessionAuthentication]`
  only (NOT `+ SessionAuthentication`): the `restaurant` branch was already unreachable in production
  through this `AllowAny` path (no authenticator loaded the staff user — tests reach it only via
  `force_authenticate`), so this is behavior-preserving AND closes the landmine. Regression test
  `test_restaurant_role_rejects_customer_principal` pins it.

**Remaining (deliberately out of scope):** the throttle-helper session reads
(`VoucherRedeemThrottle` fallback `get_cache_key`, `_voucher_redeem_fail_cache_key`) — these key the
rate-limit bucket per session and are fine as raw reads; `CustomerSessionView` (the "am I logged in"
probe — must stay AllowAny + `{customer: null}`); and `CustomerPhoneVerifyView`'s OTP session-link
branch (it *writes* the session during registration/link, not a customer-principal read). Then the
optional **customer-CSRF hardening** as a deliberate, separate step. **The customer/driver view sweep
is complete** — every request-handling view that read `session["customer_id"]` now goes through
`CustomerSessionAuthentication`; what's left are throttle key-builders, the session probe, and the
login/OTP writers.
**Source:** API/auth review.

### STRUCT-1 — God-files and no `OrderService`
**Where:** `menu/views.py` = **13,380 lines / 110 classes** across 8 domains;
`accounts/views.py` = 8,742; `PlaceOrderView.post` = a **574-line method** doing
stock+loyalty+promo+wallet inline with locally-defined exception classes; **618 function-local
imports** exist only to dodge circular deps between the two fat files.
**Failure scenario:** The crown-jewel order path is raw inside an HTTP handler (contrast the
clean `wallet_service`). Every change risks a regression in an unrelated concern; onboarding a
new engineer means reading a 13k-line file; the circular-import web makes refactoring scary.
**Fix:** Extract `OrderService` (place/modify/cancel/refund) as a tested domain service, then
split the god-files by bounded context (orders / catalog / dine-in / analytics / admin). The
618 local imports mostly dissolve once the files are split.
**Effort:** L. Start with `OrderService` — highest value, and it de-risks the money path.
**Source:** backend-structure review.

### TEST-1 — Test suite gives false confidence  ✅ ADDRESSED (2026-07-10)
**Where:** mock-heavy `SimpleTestCase`s that patch `WalletTransaction.objects`,
`transaction.atomic`, `select_for_update`; DB tests self-skip when Postgres is absent;
Playwright E2E specs exist but aren't wired into CI; no test-count floor.
**Failure scenario:** The tests that "cover" money and isolation actually patch the very
machinery they claim to protect — they verify Python control flow, not the invariant. One CI
infra hiccup and DB tests silently skip, CI goes green with zero DB tests run, and a real
concurrency/isolation regression ships.
**Fix:** (1) Make DB tests **fail, not skip**, when the DB is absent in CI. (2) Wire the
Playwright E2E (incl. the cross-subdomain-CSRF spec) into CI. (3) Add a **test-count floor**
so a collection error can't silently drop tests. (4) Convert the highest-value money/isolation
mocks into real DB integration tests.
**Resolution (item 3, 2026-07-10):** the CI "Backend tests" step now asserts a floor on
`passed` (≥ 4000) and a ceiling on `skipped` (≤ 100) parsed from the pytest summary — a collection
error or a mass DB-self-skip (the exact false-green this warns about) now fails CI instead of
passing with a silently shrunken suite. Parsing validated locally against real/edge summaries.
**Resolution (item 1, 2026-07-10):** CI now sets `PYTEST_REQUIRE_DB=1`; `tests/conftest.py`
aborts the whole session (`pytest_sessionstart`) if Postgres is unreachable, and the per-file
availability guards re-raise instead of skipping. **Bonus root-cause find:** the old in-file probe
(`django.db.connection.ensure_connection()` at import) *always* raised under pytest-django's
access blocker — so the 24 MFA DB tests (`test_mfa_totp.py` B1–B7) had **never actually run in
CI** (they were the mysterious "24 skipped" baseline). The probe now connects via the raw
psycopg2 driver (`tests/_dbprobe.py`), so those tests execute in CI for the first time — and
that first run exposed that all 24 were **written but never validated**: they drove the full
`APIClient` stack against the default host `testserver`, which is neither a tenant domain nor a
`PUBLIC_SCHEMA_HOST`, so every request 404'd at the tenant middleware before reaching a view.
Fixed by pointing the client at the public host `localhost` (the MFA/login endpoints live in the
shared urlconf and never read `request.tenant`); the 24 now exercise the real enrollment / login-
gate / verify / disable flows.
**Resolution (item 2, 2026-07-10):** a new `e2e` CI job (`.github/workflows/ci.yml`, gated on the
backend+frontend jobs) stands up the real stack — Postgres, `migrate_schemas`, `seed_plans
--with-demo` (creates the `demo` tenant + admin + owner), `runserver` on :8000, Vite dev on :5173,
`demo.localhost` mapped to loopback — and runs the Playwright specs. **Split gate:**
`cross-subdomain-auth-csrf` (the security/isolation + CSRF regression this item names) **and**
`mobile-breakpoint-regression` (390px no-horizontal-overflow QA invariant) are **blocking**;
`critical-saas-flow` (the fragile full onboarding journey) runs **informational**
(`continue-on-error`). The e2e job's first green run also surfaced real pre-existing debt the specs
were built to catch — both now **fixed**: an `AddIndexConcurrently`-vs-provisioning 500 (see
MULTITENANCY-1) and a **390px horizontal overflow on `/owner/onboarding`** (contained by a
`Wizard.vue` `overflow-x-clip` guard after the overflow proved data-dependent and
non-reproducible locally; the mobile spec was then promoted to blocking).
Traces/screenshots/server logs upload as artifacts on every run.
**Resolution (item 4, 2026-07-10):** the load-bearing money/isolation invariant the mocks could
never verify — that the `select_for_update` row lock and the under-lock idempotency re-check
actually serialize *concurrent* writers — is now covered by real multi-threaded DB tests
(`tests/test_money_concurrency.py`): concurrent same-key credit (must apply once, no unique-key
500), concurrent debits (no overspend / negative balance), concurrent credits (no lost update),
and concurrent driver payouts (no double-pay past `owed`, RISK MONEY-2). Each worker runs on its
own connection, released together by a barrier so they genuinely contend; assertions are
deterministic on correct code and only fail when the lock is broken. Both `test_wallet_service.py`
and `test_driver_payout_service.py` had explicitly flagged this as un-coverable single-threaded —
that gap is now closed. **Residual (low value):** a tail of older tests still mock `transaction.atomic`
/ `select_for_update` (e.g. `test_a4_marketplace_cod.py`, `test_bulk_order_status.py`); they now
duplicate control-flow coverage the real DB tests provide, so de-mocking them is cleanup, not risk.
**Effort:** M (remaining). **Source:** testing/CI review.

### DATA-1 — Cross-schema refs have no orphan protection  ◑ PARTIALLY ADDRESSED (2026-07-11)
**Where:** `(tenant_id, order_number)` on `DeliveryJob`, `WalletTransaction`, `CustomerOrderRef`,
`CustomerRating`; **no `Order` `post_delete` handler anywhere**; `order_number` is only
tenant-unique.
**Failure scenario:** An `Order` is hard-deleted or its tenant schema is dropped. A
`DeliveryJob` still carries `driver_payout` and feeds `reconcile_driver_earnings` → a driver is
paid for a delivery whose order no longer exists, with no FK to catch it. Separately, any code
that ever queries these public tables by `order_number` **without** `tenant_id` cross-contaminates
restaurants.
**Resolution (orphan reconciliation, 2026-07-11):** `reconcile_order_refs` scans each tenant's
public refs (`DeliveryJob`/`CustomerOrderRef`/`CustomerRating`) against the `order_number`s that
actually exist in that tenant's schema (`schema_context`, mirroring `backfill_order_index`) and
reports orphans. **Detect-only by default** (Beat runs it daily with no `--fix`, mirroring
`reconcile_wallet_balances`): a money-carrying **`DeliveryJob` orphan** (has a `driver_payout` —
the exact "driver paid for a vanished order" hazard) is escalated to the `payments` channel for
human triage and is **NEVER auto-deleted**; a `CustomerRating` orphan is reported only. `--fix`
deletes ONLY the pure-mirror `CustomerOrderRef` orphans (safe; already removed on `Order`
post_delete — this catches signal misses like a bulk delete / schema drop). `WalletTransaction` is
out of scope (fuzzy free-text `reference`; a money ledger must never be reconciled by deletion).
Tests: `tests/test_reconcile_order_refs.py` (4, no DB). Verified there is **no production Order
hard-delete path today** (GDPR erase blanks-but-retains; no admin/teardown deletes), so this is
defense-in-depth for out-of-band deletes.
**Remaining (structural):** (1) make `order_number` **globally unique** (`{tenant_id}-{seq}` or
UUID) so public refs need one column and can't cross-contaminate — a large ripple (URLs,
serializers, frontend), deliberately deferred; (2) an `Order` **soft-delete convention** (no
`deleted` field exists). The existing per-ref `tenant_id` scoping (audited: DeliveryJob /
CustomerRating / CustomerOrderRef lookups already constrain `tenant_id`) plus this reconcile job
cover the acute risk without the structural rewrite.
**Effort:** S (reconcile, done) / L (global-unique order_number, remaining).
**Source:** data-model review.

### API-1 — No API versioning
**Where:** zero versioning (URL/header/namespace) across all routes; no `VERSIONING` setting.
**Failure scenario:** A PWA/mobile-web client caches an old bundle (service workers persist for
hours/days). You ship a breaking response-shape change; in-flight clients break with no
negotiation path. The moment there's a store-distributed native app (the rides/delivery
ambition implies one), old versions are pinned in users' hands and you **cannot** force-upgrade.
**Fix:** Introduce `/api/v1/` (`URLPathVersioning`) **now**, while there's one client and it's
trivial. Retrofitting after a client is pinned is near-impossible.
**Effort:** S now / XL if deferred.
**Source:** API/auth review.

### ASYNC-2 — One generic cron task on a shared 2-worker queue  ✅ ADDRESSED (2026-07-19)
**Where:** `run_management_command` (single task, 25-entry allowlist) wired to ~24 beat entries;
`--concurrency 2`; the sweep task had no retry decorator. (A dedicated `cron` queue *route* had
already shipped, but pointed at the single generic task; the worker still ran `-Q notifications,default`.)
**Failure scenario:** A slow `sweep_delivery_jobs` (the dispatch heartbeat) occupies one of the
two worker slots; because every cron and every push notification share the single default queue,
customers' "order ready" SMS are starved behind it. And the sweeps carry no retry, so a
transient DB blip during a tick just drops that tick. Separately, the generic task accepted a
**caller-supplied command name off the (unauthenticated) broker**, guarded only by a hand-maintained
allowlist that could drift from the beat schedule.
**Resolution:** The generic `run_management_command` + `_MANAGEMENT_COMMAND_ALLOWLIST` are deleted.
Each of the 24 beat entries now dispatches a dedicated `@shared_task(name="cron.<command>", …)`
that bakes in its own command name (and `apply=True` for `enforce_subscriptions`) — **the task name
IS the allowlist**, so no broker message field selects what runs. The route is now `cron.*` → `cron`
queue (whole namespace, not one task); notifications stay on the default `notifications` queue. All
24 cron tasks carry `_CRON_RETRY` = `autoretry_for=(OperationalError, InterfaceError)` + bounded
jittered backoff (`retry_backoff_max=60`, `max_retries=3`) — a transient Postgres blip retries, a
genuine bug still fails fast (no 3× re-run). **Schedules unchanged.** Deploy: the Coolify worker
now runs `-Q notifications,cron` (was `-Q notifications,default`, a dead queue) so cron tasks are
actually consumed once a broker is set; `config/celery.py` documents running a second `-Q cron`
worker for full slot-isolation. Tests: `tests/test_celery_tasks.py` (named-task dispatch, retry
config, routing, "every scheduled cron task is registered", "generic runner + allowlist are gone")
+ `tests/test_ops5d_app.py::TestCronCommandTasks`.
**Effort:** M.
**Source:** async/realtime review.

### ASYNC-1 — Inline fallback loses work on restart
**Where:** `accounts/tasks.py` `enqueue()` — when `CELERY_BROKER_URL` is unset (a likely default),
tasks run on an in-process `ThreadPoolExecutor`; `.run()` bypasses `autoretry_for`; the pending
queue is unbounded and evaporates on process exit.
**Failure scenario:** Every deploy does a rolling uvicorn restart. Any inline task still queued
(a `charge_request` money-nudge, an `sms_order_ready`) is dropped with no record and no retry.
The docstring claims "durable, survives restarts" — true only in the broker branch, which may
not be running.
**Fix:** Make the broker **required in production** (fail-closed if unset), or give the inline
path a durable outbox. At minimum, document that inline mode is dev-only and assert a broker in
prod boot.
**Effort:** M.
**Source:** async/realtime review.

### MULTITENANCY-1 — Schema-per-tenant caps the ambition (decide consciously)
**Where:** `TENANT_APPS = [..., menu]`; django-tenants; the money layer pulled into `public`.
**Failure scenario (at scale):** (a) Every deploy runs each of 76 `menu` migrations **per
schema** — at hundreds of tenants a migration window is an operational hazard; (b) can't use
PgBouncer transaction-pooling (`SET search_path` is session state) → connection ceiling; (c)
O(N-schema) analytics; (d) a ~~**latent landmine**~~ **REALIZED then fixed (2026-07-11)**:
provisioning wrapped schema creation in `transaction.atomic()`, but the shipped index migrations
(`menu/0060`, `0062`, `0066` — `AddIndexConcurrently`) **cannot run in a transaction**, so **every
new tenant signup 500'd**. It was dormant only because no tenant had been provisioned since those
migrations shipped; the new **e2e CI job surfaced it** (first thing in CI to create a tenant). Fixed
in `sales/services.provision_lead` and `seed_plans --with-demo`: create the tenant ROW inside the
txn with `auto_create_schema=False`, then `create_schema()` **after commit** (outside any txn); a
schema-build failure rolls the tenant back (deletes it so the slug frees) and marks the
`ProvisioningJob` FAILED. Tests: `tests/test_provision_schema_deferral.py` (deferral + rollback) +
updated `test_seed_plans_command.py`; the success path is exercised end-to-end by the e2e job. The
broader items (a)–(c) remain the conscious scaling decision below.
**Fix / decision:** This is a *conscious decision*, not an urgent patch. If your true ceiling is
**low-hundreds of premium tenants**, schema-per-tenant is fine — keep it. If you genuinely target
**thousands**, plan a migration to **shared-schema + Postgres Row-Level Security** — which your
money layer already proves works. Do not rewrite now; **decide the ceiling** and record it in
[ADR-0001](adr/0001-schema-per-tenant.md).
**Effort:** XL (only if you choose to migrate).
**Source:** multitenancy review, data-model review.

---

## 🟡 Medium

### MONEY-2 — Driver-payout "owed" check is unlocked  ✅ ADDRESSED (2026-07-10)
**Where:** `accounts/driver_service.py` `record_driver_payout`, which aggregated "owed"
(`earned − sum(payouts)`) without a row lock.
**Failure scenario:** Two concurrent payout requests both read the same "owed" total before
either writes → double payout.
**Resolution:** `record_driver_payout` now acquires `Customer.objects.select_for_update()` on the
driver row before (re)computing owed and creating the `DriverPayout`, so concurrent settlements
serialize — the second recomputes owed *including* the first's committed payout. Idempotency is
also re-checked under the lock (a concurrent same-key request replays instead of racing a second
insert that would 500 on the unique key). An adversarial review added two further hardenings to
match the wallet-service discipline: a **cross-driver idempotency-key collision guard** (a
caller-supplied key resolving to another driver's payout is refused, not silently handed back),
and a **fail-closed** check if the driver row is absent (so the mutex can't be a silent no-op).
Mirrors the wallet-service discipline; single-row lock, so no new deadlock ordering. Tests:
`tests/test_driver_payout_service.py` (6, green on Postgres).
**Source:** money review.

### MONEY-3 — Dormant Stripe webhook trusts metadata  ✅ ADDRESSED (2026-07-10)
**Where:** `accounts/views.py` `CustomerTopUpWebhookView`, which credited `metadata.amount`
(the *requested* amount echoed back), not the settled amount.
**Failure scenario (when PSP goes live):** a partial/adjusted (or, without a signing secret,
tampered) session credits the wrong amount.
**Resolution:** the webhook now credits the **settled `amount_total`** Stripe reports (minor units
→ MAD), only for sessions with `payment_status == "paid"`, falling back to metadata only when
`amount_total` is absent (older events). Signature verification (when `PSP_STRIPE_WEBHOOK_SECRET`
is set) and event-id idempotency (`stripe:<event_id>`) were already in place; the docstring still
flags that the secret is **required in production**. Still dormant (`PSP_TOPUP_ENABLED=False`) —
this hardens it before go-live. Tests: `tests/test_psp_topup.py` (+3, incl. amount_total-wins and
unpaid-no-credit; 10 total, no DB needed).
**Source:** money review.

### OPS-3 — One Redis backs four subsystems
**Where:** `REDIS_URL` = cache + sessions + Channels layer + optional broker; 256 MB cap.
**Failure scenario:** A WS fan-out spike or the 256 MB ceiling triggers eviction → cached
idempotency mutexes/throttle counters vanish **and** sessions get evicted, logging users out
mid-shift.
**Fix:** Move sessions off the cache, then split the broker onto its own instance at first contention.
**⚠️ GOTCHA (verified 2026-07-10):** the naive `SESSION_ENGINE = cached_db` swap **breaks prod** here —
django-tenants switches the connection to the *tenant* schema during middleware unwind, and
`django_session` lives only in `public`, so a `cached_db` write 500s on every authenticated request
(the team documented this at `config/settings.py` ~L409). The real fix is a **schema-pinned session
backend** (force `schema_context("public")` around session DB writes) or **signed-cookie sessions**
(size/invalidation tradeoffs) — a deliberate custom component, not a one-line setting.
**Effort:** M. **Source:** async/realtime review.

### ASYNC-3 — Realtime and polling both run at full rate  ✅ ADDRESSED (2026-07-17)
**Where:** `OrderStatus.vue` polls every 15s even when the WS is live; `OwnerOrders.vue` polls
15s and doesn't instantiate the (already-built) `useOwnerRealtime` at all.
**Failure scenario:** You pay for `channels_redis` + WS fan-out **and** keep full-rate polling —
backend request volume is ~unchanged from poll-only, plus the WS cost. Realtime is additive, not
substitutive.
**Resolution:** both pages now poll via a **self-rescheduling `setTimeout`** (not a fixed
`setInterval`) that reads the WS `connectionState` each cycle: `'live'` → a **60s safety-net**,
otherwise the original fast 15s primary rate — so the cadence adapts if the socket flips mid-session.
`OrderStatus.vue` reuses the `connectionState` its existing `useOrderRealtime` already exposes.
`OwnerOrders.vue` now instantiates `useOwnerRealtime` (mirroring `OwnerKitchen`'s own `/ws/owner/`
subscription): `order.*` events push a `doPoll()` — the same refresh the timer runs — and its poll
gates on that channel's `connectionState`. Behavior is unchanged for users whose socket never
connects (still 15s + the background-tab skip). Net: 4× fewer HTTP polls when live, for one extra
(cheap) WS subscription — the intended substitutive tradeoff. All four frontend gates green
(verify:i18n, lint, build, vitest 519).
**Effort:** M. **Source:** async/realtime review.

### ASYNC-4 — `acks_late` without dedupe → duplicate sends  ◑ PARTIALLY ADDRESSED (2026-07-11)
**Where:** `CELERY_TASK_ACKS_LATE = True` (global) + `CELERY_TASK_TIME_LIMIT = 120`, no
`task_reject_on_worker_lost`, no DLQ; the notification tasks had no dedupe key.
**Failure scenario:** A worker is killed mid-`sms_order_ready` (by the 120s time-limit or OOM) →
the task is redelivered and re-run → the customer gets a duplicate SMS (real cost + trust hit),
exactly under the load when redelivery happens.
**Resolution (dedupe, 2026-07-11):** the trust/cost-sensitive tasks (`sms_order_ready`,
`recipient_track_sms`, `whatsapp_new_order`, `customer_order_milestone`) now **claim a one-time
send key** (`accounts/tasks._claim_send`, an atomic `cache.add`/SETNX) BEFORE dispatching — a
redelivered / autoretried duplicate finds the key already claimed and skips, so the customer never
sees a double SMS/WhatsApp/status-push. The claim is **released on exception** so a genuine
transient-failure retry (`SmsProviderError` → `autoretry_for`) still re-sends; it **fails open** so
a cache blip never silently drops a notification; and keys embed the global `tenant_id` so a
tenant-local `order_number` can't collide across schemas. TTL 1h ≫ the retry+redelivery window.
Tests: `tests/test_notification_dedupe.py` (9, no DB) — dedupe, distinct-notification isolation,
retry-preservation, fail-open.
**Remaining:** a true **DLQ / rejected→alert path** for tasks that exhaust retries (the failure
audit already lands in `NotificationLog` with `status=failed`, but there is no active alert). That
is broker/infra work (dead-letter exchange), not a code S-fix; `task_reject_on_worker_lost` was
left off deliberately — it is global and would also requeue non-idempotent cron/management tasks.
**Effort:** S (dedupe, done) / M (DLQ, remaining). **Source:** async/realtime review.

### FE-1 — i18n dual-source footgun
**Where:** `messages.js` (inline en+fr, read by runtime + gates) **and** `messages-ar.js` **and**
`messages-en.js` must all be edited for one new key.
**Failure scenario:** A dev edits only `messages-{en,fr}.js`, passes `verify-i18n.mjs`, fails
`verify-i18n-usage.mjs` (or ships raw keys at runtime). Already happened this project.
**Fix:** Collapse to a **single source of truth** — delete `messages.js` as the runtime source,
generate the parity files, or move to a keyed catalog with one file per locale. See
[ADR-0005](adr/0005-i18n-dual-source.md).
**Effort:** M. **Source:** frontend review.

### FE-2 — Mega-page components
**Where:** `WaiterPage.vue` 3,722, `CustomerAccount.vue` 3,654, + four more 2,500–3,700 lines.
**Failure scenario:** Single-writer bottleneck; merge conflicts; hard to test; slow to reason about.
**Fix:** Split each into feature child-components + composables.
**Effort:** L. **Source:** frontend review.

### FE-3 — Locale catalogs block first paint  ◑ MOSTLY SHIPPED (verified 2026-07-11)
**Where:** ~500KB of locale data loaded up front; Sentry not lazy.
**Failure scenario:** An Arabic visitor waits on ~500KB of JS before first meaningful paint.
**Fix:** Split catalogs by namespace/route and lazy-load; lazy-init Sentry.
**Status (code-verified):** the two named problems were already fixed by commit `a84cc7d`
("perf(R24): code-split i18n locale catalogs out of the initial bundle"). `src/i18n/localeLoader.js`
now dynamically imports each locale (`messages-{en,fr,ar}.js`) as its own Vite chunk (~69–82KB gz
each, down from one always-loaded ~800KB file), and `src/lib/sentry.js` fires a non-awaited dynamic
`import('@sentry/vue')` before mount (its own async chunk). **Residual update (2026-07-17):**
`localeLoader.js` now has a test — `src/i18n/__tests__/localeLoader.test.js` (8 cases, mocks the 3
dynamically-imported catalog chunks): EN/FR load, the AR = EN-base + AR-overrides merge with
corrupted-value filtering, unknown-locale no-op, concurrent-load dedup (chunk fetched once),
`getMessages` EN fallback, and the retry-eviction of a failed in-flight load. The only remaining
residual is the deliberate one: `main.js` still `await`s the active locale before `app.mount()` (an
AR first paint blocks on ~82KB gz) — and namespace/route splitting (the original Fix) trades a
flash-of-raw-keys risk, so both are left for a deliberate later slice.
**Effort:** S–M. **Source:** frontend review.

### SER-1 — Writes bypass serializers  ◑ PRIMITIVE SHIPPED (2026-07-12)
**Where:** 242 raw `request.data.get(...)` reads vs 41 serializer-mediated writes.
**Failure scenario:** Validation/type-coercion is hand-rolled per handler; a money endpoint
reads a price/amount from `request.data` without a serializer guard → price-manipulation class
(cf. the DishOption price-manip bug already fixed).
**Fix:** Route writes — especially money/price endpoints — through serializers with explicit
fields + `read_only_fields`.
**Scout finding (5-agent money-endpoint sweep, 2026-07-12):** SER-1 is largely
**defense-in-depth, not a live exploit** — nearly all wallet/order amounts already funnel through
`wallet_service._money()` (Decimal coercion + positivity → 400) plus downstream caps (order-
outstanding 409, promo clamp, admin caps). The candidate money endpoints (tip_amount, promo
discount, split-payment) are **not** cleanly hardenable behavior-preservingly: their current code
silently *coerces* (never rejects), so a naive serializer would 400 currently-succeeding requests.
**Shipped:** `config/drf_fields.QuantizedMoneyField` — the reusable migration primitive that
pre-quantizes to 2dp (matching the legacy silent round) before DRF enforces type/`max_digits`/
`min_value`, so a handler migrates onto a serializer with **zero change to accepted inputs**.
Applied to `DrawerTransactionView` (the one genuine gap: an oversized amount used to overflow the
`NUMERIC(10,2)` column → uncaught **500**; now a clean **400**). Independently verified
behavior-preserving by a 3-lens adversarial pass (legacy-vs-new across ~50 inputs). Tests:
`test_ser1_money_field.py` (contract matrix) + drawer regression tests.
**Remaining:** migrate the other hand-rolled money reads onto `QuantizedMoneyField`
**opportunistically** (low urgency — defense-in-depth), each behavior-preserving with a regression
test. Not a high-priority sweep.
**Effort:** L (incremental). **Source:** API/auth review.

### SCHEMA-1 — OpenAPI has duplicate operationIds
**Where:** CI exports via legacy `generateschema`; ~239 view classes, zero `operationId` overrides.
**Failure scenario:** Colliding operationIds make the schema unusable for typed client-generation
(openapi-generator/orval drop or dedupe colliding ops) — the one mechanism that could let clients
evolve safely against the API is itself broken.
**Fix:** Switch to **drf-spectacular** (`@extend_schema`, unique operationIds); enables a generated
typed client (which also mitigates API-1's client-drift risk).
**Effort:** S–M. **Source:** API/auth review.

### DATA-2 — `CustomerOrderRef` mirror can silently drift  ◑ PARTIALLY ADDRESSED (2026-07-10)
**Where:** `menu/signals.py` `mirror_order_to_public_index` fired on `menu.Order` `post_save` only;
OrderItem mutations don't always re-save the parent.
**Failure scenario:** A customer's cross-restaurant "My Orders" shows phantom orders (deleted
orders that lingered), stale statuses, or a stale re-order cart.
**Resolution (this batch):** added a `post_delete` receiver `remove_order_from_public_index` that
drops the mirror row (scoped by `tenant_id` + `order_number`) when an order is deleted — killing
the phantom-order class. The existing sync already logs failures via `logger.exception` (not a
silent `except: pass`). Tests: `tests/test_order_mirror_delete.py` (3, incl. a receiver-registration
guard against a wrong sender string).
**Remaining (smaller residuals):** re-mirror on OrderItem void/comp/append mutation (status/items
snapshot can still drift while the order lives), and a periodic mirror-reconcile as belt-and-suspenders.
**Effort:** S. **Source:** data-model review.

### DATA-3 — `Dish` + 4-key JSON is not a multi-vertical catalog
**Where:** `Dish.attributes` restricted to `{sku, barcode, brand, unit}`; retail/pharmacy have no
home for variants, tax class, expiry, dosage, controlled-substance flags, batch/lot.
**Failure scenario:** The first serious pharmacy/retail tenant needs regulated fields → you either
overload `attributes` into an unqueryable free-for-all or do the deferred `Dish→Item` rename
across 76 migrations + every serializer/view/frontend ref.
**Fix:** When a paying non-food tenant is real, design a neutral `Product` with a typed
`product_kind` + per-vertical satellite tables (`FoodAttrs`/`RetailAttrs`/`PharmacyAttrs`). Until
then, keep verticals at `coming_soon` (see the product recommendation in ARCHITECTURE §11).
**Effort:** L. **Source:** data-model review.

### DATA-4 — Directory opt-in has no data prerequisite  ✅ ADDRESSED (2026-07-10)
**Where:** `cuisine_type`, `city`, `lat`, `lng` are `blank/null=True` with no rule tying them to
`directory_opt_in=True`.
**Failure scenario:** A restaurant opts into the public directory with empty city/coords →
distance-sort silently breaks; every consumer must null-guard (the frontend already had to).
**Resolution:** `ProfileSerializer.validate` now rejects `directory_opt_in=True` unless the
effective **city** and **valid coordinates** are present (coords checked *after* the existing
(0,0)/out-of-range normalization). Enforced only when `directory_opt_in` is in the update payload
(mirrors the disable-note rule), so turning it on requires the data but editing an unrelated field
on an already-listed profile isn't blocked. Tests: `tests/test_directory_optin_validation.py` (7,
no DB). Left `cuisine_type` optional so non-food verticals aren't over-constrained.
**Source:** data-model review.

### DATA-5 — Four `Profile` mirrors kept by scattered signals
**Where:** `rating_avg`, `rating_count`, `marketplace_promos`, `closure_dates` — each synced by a
different signal file + a different backfill command, all cross-schema, all best-effort.
**Failure scenario:** A bulk update / data migration / direct SQL misses a signal → the public
marketplace shows wrong ratings/promos with no constraint to catch it.
**Fix:** Consolidate the denorm into one well-tested sync path; add a periodic reconcile. (Justified
optimization — this is about making it robust, not removing it.)
**Effort:** M. **Source:** data-model review.

### STRUCT-2 — Migration sprawl, `Order` field-by-field growth
**Where:** 215 migrations (menu at 0076); `Order` ~60 fields accreted one flag at a time; no squashing.
**Failure scenario:** Every deploy runs a longer per-schema migration chain (compounds with
MULTITENANCY-1); wide `Order` rows hurt every scan.
**Fix:** Squash migrations at a release boundary; consider decomposing `Order` by bounded context
as part of STRUCT-1.
**Effort:** M. **Source:** data-model review.

---

## 🟢 Low

### API-2 — Contract sprawl
Inconsistent naming (`api/admin/customers/` vs `api/admin-tenants/`), RPC-style verb routes, all
hand-listed in three god url-files. Maintainable now (authors hold it in their heads); won't
survive team growth. **Fix:** naming convention + per-domain url modules as part of STRUCT-1.
**Effort:** M. **Source:** API/auth review.

### OPS-4 — `daphne` — re-scoped (NOT dead weight)  ⏭️ (2026-07-10)
The async review called `daphne` dead weight, but on inspection it is **wired into `INSTALLED_APPS`**
(`config/settings.py` ~L163 inserts it when channels is present) — it provides the ASGI `runserver`
dev command. Prod serves via uvicorn, so `daphne` isn't the *server*, but removing the package also
means removing the `INSTALLED_APPS` insertion and changes local `runserver` to the WSGI dev server
(no WS in dev runserver). That's a deliberate dev-tooling change, **not** the free image-slim win the
review implied — **skipped** as low-value/low-priority. If you do remove it: drop the requirement
*and* the settings insertion, and confirm nobody relies on `manage.py runserver` for local WS.
**Effort:** S. **Source:** async/realtime review (claim corrected here).

---

## Recommended sequencing (the smart path)

1. **This week (S/M, stops the bleeding):** OPS-2 (off-box backups) → OPS-1 (PITR) →
   MONEY-1 (reconciliation job) → MONEY-2 (lock payout) → TEST-1 (DB tests fail-not-skip + wire E2E).
2. **Next few weeks (the keystone refactors):** AUTHZ-1 backstop first, then IDENTITY-1 →
   the `IsTenantOwner`/`IsOrderOwner` policy layer → STRUCT-1 (`OrderService`) → FE-1 (kill dual-source).
3. **Before the PSP goes live:** MONEY-3, and re-audit every money endpoint through the new policy layer.
4. **Before a native app ships:** API-1 (versioning) + SCHEMA-1 (drf-spectacular).
5. **Strategic, decide don't drift:** MULTITENANCY-1 (pick your tenant ceiling) and the
   depth-first-on-restaurant product call (ARCHITECTURE §11).
