# End-to-End Smoke Test — Platform + Money Model

Run this after a deploy to confirm the whole platform works: a customer orders from the
marketplace, a driver delivers, and **every balance moves correctly** (customer wallet,
restaurant float, driver earnings). Tick each box; the **Expect** line is the pass
condition.

> Coolify does NOT auto-deploy on push — trigger backend + frontend redeploys manually.

---

## 0. Pre-deploy (one-time per release)

- [ ] **Backend redeployed** — applies migrations. Verify: `python manage.py migrate --check` is clean.
  Latest migrations this cycle: `accounts/0016–0022`, `tenancy/0027–0028`.
- [ ] **Frontend redeployed.**
- [ ] **Env set** (optional): `WALLET_DEFAULT_DIAL_CODE=212` (lets customers type local `06…` numbers). Leave `WALLET_P2P_ENABLED` **unset** (P2P stays off until KYC/legal).
- [ ] **Daily cron added**: `python manage.py enforce_subscriptions --apply` (subscription lapse → grace → suspend).
- [ ] **One-off backfill** (if upgrading an app with existing orders): `python manage.py backfill_order_index --apply` (seeds the cross-restaurant order history + re-order snapshots).
- [ ] **Plan flags audited** — in Django admin → Plans, every live/paid plan has `can_checkout` and/or `can_whatsapp_order` set. A plan with neither = browse-only (tier gating is ON).

---

## 1. Admin can manage the platform  (sign in as platform admin → `/admin-console`)

- [ ] Tenants tab lists restaurants; lifecycle (suspend/reactivate) works. **Expect:** status chip updates.
- [ ] Monitoring tab loads alerts/jobs/audit without manual expand. **Expect:** data, not empty panels.
- [ ] `/admin-customers` lists customers; open one → wallet ledger + **orders across all restaurants** show. **Expect:** detail loads.
- [ ] `/admin-flash-sales` → create a campaign. **Expect:** appears as Scheduled/Live.
- [ ] `/admin-delivery-jobs` loads (may be empty pre-test).

---

## 2. Fund a restaurant float  (admin)

- [ ] `/admin-wallets` → "Fund a restaurant float" → pick a restaurant, fund e.g. **200**.
  **Expect:** success; the restaurant's float shows 200 in the dropdown.

## 3. Owner tops up a customer  (sign in as that restaurant's owner → Wallet)

- [ ] Float card shows **200**.
- [ ] Top up a customer who has ordered there, e.g. **50** (customer must have a **verified phone**).
  **Expect:** customer balance +50, float now **150**.
- [ ] Try to top up **999** (over float). **Expect:** `402` "insufficient float", nothing moves.
- [ ] Try to top up an **unverified** customer. **Expect:** clear rejection (no verified phone → no wallet).

---

## 4. Customer orders from the marketplace  (`/order`, as a customer)

- [ ] Browse restaurants; **heart** a restaurant → Favourites filter shows only it.
- [ ] Open a restaurant with **platform delivery enabled** → add items → checkout as **delivery**.
- [ ] If not signed in, the **inline sign-in modal** appears and the order retries after auth.
- [ ] Pay with **wallet** (toggle uses the 50 credit). **Expect:** order placed; wallet debited.
- [ ] **My account → All your orders** shows this order across restaurants, with a **Re-order** button.

---

## 5. Driver delivers  (`/driver`, as a driver — a customer with driver mode on)

- [ ] Go **online** (allow location). A searching job for the order appears.
- [ ] **Accept** → advance: At restaurant → Picked up → **Delivered**.
  **Expect:** status advances; driver auto-goes-offline after delivery.
- [ ] Earnings card: **Owed** increased by the delivery fee (driver gets 100%).

## 6. Settle the driver  (admin → `/admin-drivers`)

- [ ] Driver row shows **Owed** = the delivery fee.
- [ ] Click **Pay out** → confirm amount. **Expect:** Owed drops to 0; payout recorded.
- [ ] Try paying again (Owed = 0). **Expect:** button hidden / rejected ("exceeds amount owed").

---

## 7. Money model reconciliation (the whole point)

- [ ] Restaurant float: 200 − 50 = **150**. ✅
- [ ] Customer wallet: 50 − (order paid from wallet) = remaining. ✅
- [ ] Driver: earned = delivery fee, paid = delivery fee, **owed = 0**. ✅
- [ ] Admin customer detail shows the order under "Orders (all restaurants)" and the wallet debit under the ledger. ✅

---

## 8. Gated/deferred features (confirm they're correctly OFF)

- [ ] P2P "Send credit" is **not** visible to customers (WALLET_P2P_ENABLED off). ✅
- [ ] Restaurants NOT opted into platform delivery don't spawn driver jobs. ✅

---

### If anything fails
Capture: the step, the screen, the network response (status + body), and the server
log line. Most money-flow issues surface as a clear `4xx` with a `detail`/`code`.
