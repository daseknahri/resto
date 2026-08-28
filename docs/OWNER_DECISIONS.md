# Owner-decision backlog — the 12 hardening-sweep items that need your call

> **Progress (2026-08-28):** **6 of 12 shipped** on the engineering-recommendation where the call was a
> clear correctness/safety fix (not a genuine business/policy question): **#4** overnight hours (PR #281),
> **#6** comp-keeps-loyalty-points (PR #280), **#8** driver-revoke→delivery-cascade (PR #282), **#9**
> durable voucher idempotency (PR #282), **#10** P2P recipient confirmation (PR #283), **#12** FR
> ASCII-only enforced + CI check (PR #284). **6 still await your call** — the genuinely
> business/policy/rides-go-live ones: **#1, #3, #5** (rides go-live), **#2** (`driver_owed` reporting
> semantics), **#7** (floor-section ops policy — rec is leave-as-is), **#11** (clock-in labor policy).

The two 2026-08 hardening audits fixed everything that was safe to fix autonomously. What's left is
**12 items that hinge on a product / policy / accounting decision only you can make.** This doc turns
each into a **yes/no (or A/B) decision** with the tradeoffs and my engineering recommendation, so you can
decide fast and hand the implementation back to a session. Source findings:
[`HARDENING_SWEEP_2026-08-23.md`](HARDENING_SWEEP_2026-08-23.md); campaign record:
[`SESSION_LOG.md`](SESSION_LOG.md).

**How to use:** skim the summary table, then read only the items you're unsure about. Reply with your call
per number (e.g. "1: yes; 2: option B; 6: keep points") and the implementation is a straightforward,
CI-gated PR each. Nothing here is a live bug bleeding money *today* — the highest-severity money leak
(void/comp double-count) was already fixed (#277). These are correctness/policy gaps that matter at scale
or once a vertical goes live.

## Summary — decide these

| # | Item | Severity | The decision | My recommendation |
|---|---|---|---|---|
| 1 | Ride fare estimate never resolves for typed addresses | HIGH (rides) | How to get coordinates from a typed address | **Add pickup map + stuck-state error now; geocoding later** |
| 2 | Platform-analytics `driver_owed` overstates liability | MED (money/reporting) | What `driver_owed` should mean | **Option B — subtract CASHOUT tx too** |
| 3 | `in_progress` rides can't be force-resolved | MED (rides) | Admin force-resolve + absentee policy | **Add admin force-resolve; per-vertical timeout** (absentee case already backstopped by #276) |
| 4 | Business-hours editor rejects overnight close times | MED (product) | Support overnight hours (close < open) | **Yes — implement wraparound** |
| 5 | Ride drop-off map has no keyboard/SR path | MED (a11y) | Provide a non-map way to set a pin | **Yes — pairs with #1's geocode/search** |
| 6 | Comp doesn't claw back loyalty points (void does) | LOW (money) | Is a comp a goodwill gesture that keeps points? | **Owner call — I lean "keep points" (comp = goodwill)** |
| 7 | Transfer/Merge skip the section-ownership gate | LOW (security) | Do floor-section limits apply to transfer/merge? | **No section gate (managers cross sections) — but log actor** |
| 8 | Driver revocation doesn't cascade to delivery jobs | LOW (correctness) | Auto-redispatch vs stand-down on revoke | **Yes — cascade + redispatch** (the rides analog shipped in #276) |
| 9 | Voucher-batch idempotency is cache-only | LOW (money) | Durable idempotency for voucher batches | **Yes — add a durable batch key** |
| 10 | P2P transfer has no recipient confirmation | LOW (money/UX) | Confirm recipient before/after send | **Yes — show resolved name in a confirm step** |
| 11 | Clock-in guard only blocks new orders | LOW (policy) | Should clock-in gate all order mutations? | **Owner call — I lean "yes, gate payments too"** |
| 12 | FR locale violates its own ASCII-only rule (~280 lines) | LOW (i18n) | Enforce ASCII-only, or drop the rule? | **Enforce + add a CI check** (mechanical once decided) |

---

## Money / accounting

### 2 — Platform-analytics `driver_owed` overstates platform liability *(MED)*
`backend/accounts/views.py:7959`. `AdminPlatformAnalyticsView` computes `driver_owed = driver_earned − driver_paid`, where `driver_paid` counts only `DriverPayout` rows. But drivers are paid **primarily via the wallet** (a cash-out debits the driver's wallet), so cash-outs aren't subtracted → the dashboard **overstates** what the platform still owes drivers.
- **Decision:** what should `driver_owed` represent, and how to compute it without double-counting against `customer_wallet_liability`?
- **Options:** (A) derive driver liability from actual unspent driver wallet balances; (B) subtract `CASHOUT` `WalletTransaction`s in addition to `DriverPayout`.
- **My recommendation: Option B.** It's the minimal, correct alignment with the actual payout model and matches how the per-driver truth is computed elsewhere. (A) risks double-counting against the customer-wallet figure. Reporting-only — no money is mis-moved, just mis-displayed to you.
- **Effort once decided:** small, backend-only, with a unit test.

### 6 — Comp doesn't claw back loyalty points (void does) *(LOW)*
`backend/menu/views.py:5565`. Voiding an item proportionally claws back the loyalty points that item earned; comping does not, despite the comp docstring claiming "identical money rule."
- **Decision:** is a comp a **goodwill gesture** (customer keeps the points) or a **correction** (points clawed back like a void)?
- **My recommendation: keep the points (no clawback).** A comp is typically hospitality — you're eating the cost deliberately — so letting the guest keep the small points earned is on-brand and simplest. If you'd rather have strict parity with void, it's a clean port of the existing clawback block. Either way, document the chosen semantics in the docstring so it stops claiming parity it doesn't have.
- **Effort once decided:** trivial (either a doc/comment fix, or port the existing clawback block).

### 9 — Voucher-batch idempotency is cache-only *(LOW)*
`backend/accounts/views.py:3152`. `AdminWalletVoucherView` dedupes voucher batches only via cache (lock + result cache). If the cache entry is evicted, a retried batch with the same client key could mint a **second** batch — unlike every other admin money endpoint, which has a durable DB idempotency record.
- **Decision:** add durable idempotency for voucher batches?
- **My recommendation: yes.** Real money (voucher credit). Persist the client key on a batch row / dedicated idempotency table with a unique constraint, checked inside the create transaction — mirroring the `WalletTransaction`/`TenantFloatTransaction` pattern already used. Low risk, closes a real double-mint window.
- **Effort once decided:** small-medium (a migration + the check), backend-only, with tests.

### 10 — P2P wallet transfer has no recipient confirmation *(LOW)*
`frontend/src/pages/CustomerAccount.vue:829`. "Send" fires immediately with no step showing **who** the money is going to (recipient resolved by exact phone match), unlike cancel-order/delete-address on the same page which confirm. A mistyped digit sends to the wrong verified user, irreversibly.
- **Decision:** add a recipient confirmation?
- **My recommendation: yes.** At minimum surface the resolved recipient's first name/initial (the backend already returns it) in a confirm step before sending — cheap insurance against a fat-fingered irreversible transfer.
- **Effort once decided:** small, frontend-only (+ maybe surface the name in the transfer response if not already).

---

## Rides / courier vertical (all latent — rides not live yet)

### 1 — Ride fare estimate never resolves for typed addresses *(HIGH, rides)*
`frontend/src/pages/RidePage.vue:1161`. There is **no address→coordinates geocoding** anywhere in the frontend. Coordinates come only from "Use my location", tapping the drop-off map, or a saved-address chip — and **the pickup field has no map at all**. A user who just *types* both addresses gets a permanently-disabled CTA showing "Calculating…" forever, with no error.
- **Decision:** how do users turn a typed address into coordinates?
- **Options:** (a) add a pickup map (tap-to-pin) identical to the drop-off one; (b) integrate geocoding (e.g. Nominatim, consistent with the existing Leaflet/OSM stack) on blur/Enter; (c) at minimum detect the stuck state and show an explicit "tap the map / use your location" error.
- **My recommendation: ship (a) + (c) now, plan (b) for polish.** A pickup map + a stuck-state error removes the dead-end immediately and needs no new dependency or API budget; geocoding/autocomplete is the nicer UX but adds an external call (rate limits, attribution) worth scoping deliberately. **This is the #1 rides-go-live blocker** — the whole flow dead-ends without it.
- **Effort:** medium (pickup map mirrors existing drop-off map; the error state is small). Geocoding is a separate, larger piece.

### 5 — Ride drop-off map is the only way to set a pin, and it's inaccessible *(MED, a11y)*
`frontend/src/pages/RidePage.vue:373`. The Leaflet map is `role="img"` (tells assistive tech it's a static picture) but is actually the primary control for setting the drop-off. Screen-reader / keyboard-only users have **no way** to set a location.
- **Decision:** provide a non-map path to a pin.
- **My recommendation: yes — and fold it into #1.** The geocode/search text fallback that fixes #1(b) is *also* the accessible path here; plus change the map's `role` away from `img`. Decide #1 and #5 together — the same text-address-to-coordinates capability resolves both.
- **Effort:** shares with #1.

### 3 — `in_progress` rides can't be force-resolved *(MED, rides)*
`backend/accounts/models.py:1030`. `in_progress` only transitions to `completed`; the rider can't cancel it and there's no admin force-resolve. **Partly mitigated already:** #276 added sweep rule (e) that auto-cancels an `in_progress` trip whose driver is *null or revoked*. Still open: a trip whose (still-approved) driver simply goes offline/absent mid-trip, and the lack of an admin/support override.
- **Decision:** (a) let the sweep auto-cancel `in_progress` trips whose driver is offline/stale beyond a generous threshold (with rider+recipient notice)? (b) add an admin/support force-resolve (cancel/complete) endpoint? Passenger-ride vs package policy may differ.
- **My recommendation: add the admin force-resolve endpoint (b), and a *generous* per-vertical absentee timeout (a).** Support needs a manual lever regardless; the timeout is a safety net. Keep the timeout generous (e.g. package longer than a passenger ride) so you don't cancel a legitimately-slow-but-active trip. Rider-initiated cancel from `in_progress` stays **disallowed** (they could dodge a real in-flight fare).
- **Effort:** medium, backend (a new admin endpoint + sweep rule), with tests.

---

## Staff / ops policy

### 7 — Transfer/Merge skip the floor-section ownership gate *(LOW, security)*
`backend/menu/views.py:5953/6088`. Every other staff order-mutation checks `_can_access_order` (restricts a waiter to their assigned floor sections); Transfer and Merge check only tenant-ownership.
- **Decision:** should floor-section limits apply to transfer/merge?
- **My recommendation: do NOT add the section gate — consolidating tables across sections is a legitimate manager action** — but this is genuinely your ops call. If your floors are strict and waiters shouldn't touch other sections' tabs, add the `_can_access_order(src)`/`(dest)` checks (small, consistent with the siblings). Either way, ensure the actor is recorded on the transfer/merge for audit.
- **Effort:** trivial if you want the gate; none if not (maybe add actor logging).

### 11 — Clock-in guard only blocks starting a new order *(LOW, policy)*
`frontend/src/pages/WaiterPage.vue:2265`. A not-clocked-in waiter can't *start* an order, but `advance`, `payCash`/`payWallet`, `voidItem`/`compItem`, `fireCourse`, transfer/merge, mark-ready are gated only by permission, not shift state.
- **Decision:** should the clock-in requirement extend to all order-mutating/payment actions, or only order creation?
- **My recommendation: lean yes — gate at least the payment actions (`payCash`/`payWallet`) behind clock-in**, since shift attribution matters most for money handling; extending to all mutations is cleaner but check it doesn't block a legitimate hand-off where one waiter opens and another (clocked-in) closes. Your labor/attribution policy decides this.
- **Effort:** small, frontend (apply the existing guard to the chosen handlers).

---

## Product / correctness

### 4 — Business-hours editor rejects overnight closing times *(MED, product)*
`frontend/src/pages/OwnerProfile.vue:380` + `backend/tenancy/openstate.py:93`. `saveSchedule()` rejects any day where `close <= open` (string compare), so an open='18:00', close='02:00' bar/late-night venue **can't save valid overnight hours** — and the backend `schedule_open_now` has the same non-wraparound assumption, so even if saved it'd compute "open" wrong.
- **Decision:** support overnight hours (close-after-midnight)?
- **My recommendation: yes.** Any venue open past midnight needs this. Represent `close <= open` as "closes after midnight" and handle wraparound in *both* the frontend validation and `openstate.py`'s window comparison. It's a real schedule-semantics change, so scope it as one coherent PR (frontend + backend + tests) rather than an ad-hoc patch.
- **Effort:** medium, both ends, with tests for the wraparound cases.

### 8 — Driver revocation doesn't cascade to in-flight *delivery* jobs *(LOW, correctness)*
`backend/accounts/views.py:7517`. Revoking a driver flips their flags but leaves their in-flight `DeliveryJob`s (assigned/at_restaurant/picked_up) pointing at the now-revoked account, stranding the customer's active order. (This is the **delivery** analog of the *ride* stranding fixed in #276.)
- **Decision:** on revoke, auto-redispatch the driver's active delivery jobs, or stand them down for owner action?
- **My recommendation: cascade + redispatch.** In the revoke branch, `select_for_update` the driver's active `DeliveryJob`s, clear `driver_id`, and re-open them to dispatch (status→SEARCHING + reset offer fields, mirroring the existing redispatch reset). This keeps the customer's order moving and closes the gap end-to-end. Stand-down (leave for owner) is the more conservative alternative if you'd rather a human confirm each.
- **Effort:** small-medium, backend, with tests. (Directly parallels the #276 rides fix.)

---

## i18n

### 12 — FR locale violates its own ASCII-only convention (~280 lines) *(LOW)*
`frontend/src/i18n/messages-fr.js:159`. CLAUDE.md says FR is ASCII-only (no accents, to avoid mojibake), but ~280 of ~6000 lines still carry accented characters — the file is inconsistent with its own rule.
- **Decision:** enforce ASCII-only, or drop the rule (accents are fine now)?
- **My recommendation: enforce it and add a CI check.** The rule exists to prevent mojibake from encoding mishaps; the safest posture is to keep it and *make it real* — extend `verify-i18n` to flag accented Latin chars in `messages-fr.js`, then batch-normalize the ~280 lines. If you're confident the toolchain handles UTF-8 end-to-end (build, tests, runtime) and prefer proper French typography, the alternative is to **drop the rule from CLAUDE.md** so the doc matches reality. Either way it becomes consistent; the CI check just makes it stay that way.
- **Effort:** small-mechanical once the posture is chosen (the normalization is find-and-replace; the CI check is a few lines).

---

## Not in the 12, but on your plate (from `CLAUDE.md` / `NEXT_SESSION.md`)

These pre-date the sweep and remain owner-gated:
- **Stripe PSP** — wire card top-up / pay-by-card (biggest conversion lever; seam built, dormant). Runbook: `infra/COOLIFY_PSP_STRIPE_ACTIVATION.md`.
- **Mixed-currency analytics aggregates** + the deferred **`MAD`-currency display cluster** — both blocked on the same decision: how to present money once a **non-MAD tenant** exists (per-currency breakdown vs convert-to-base). The display cluster can't be fixed autonomously because the cross-tenant public-schema records carry no per-record currency.
- **Void-item commission basis** — align it with post-discount checkout via a discount-allocation rule.
- **§4.F item 8** — whether to *mandate* a photo for a code-less DELIVERED completion (the security bypass is already fixed, #222).
- **Rides go-live** — items 1/3/5 above are the concrete pre-go-live blockers.

---

*Generated after the 2026-08 hardening campaign. Reply per-number with your calls and each becomes a
single CI-gated PR.*
