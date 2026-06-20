# Restaurant App — Completion & Daily-Ease Plan

> **Goal (owner directive):** complete the full super-app structure in sequence —
> **restaurant → delivery → courier** — and make the UX **extremely easy for daily
> use** so people use it every day. This doc covers the **restaurant** phase.
>
> **Method:** built from three per-persona daily-UX assessments (owner / waiter /
> customer). The app is feature-rich and already a daily driver; the gap is
> *friction* in the high-frequency loops, plus a few genuinely-missing daily
> features. Each batch ships independently with the usual gates (lint, build,
> tests, verify:i18n) and one commit.

---

## Sequencing rationale
The daily users are, in order of headcount and habit-formation: **customers** (order
daily → revenue + retention), **waiters** (every shift, on a phone, mid-rush),
**owners** (live-ops all day). So: **Customer loop → Waiter loop → Owner loop**,
each tackling its P0 daily-friction first.

---

## Batch R-CUST — Customer ordering loop ("order every day in seconds")
The repeat-order loop is the habit engine. P0s here lose orders today.

| # | Item | Why (frequency/impact) | Sev | Files |
|---|------|------------------------|-----|-------|
| 1 | **Pre-fill name + phone at checkout** (storefront Cart + marketplace drawer); hide when known | Every delivery/pickup order retypes the same contact = #1 mobile abandonment | P0 | `Cart.vue`, `MarketplaceMenuPage.vue:611+` |
| 2 | **Reorder restores fulfillment + address**, and surface "Order again" at the TOP of the menu | Daily repeat loop; today reorder drops address/fulfillment and is buried below the whole menu | P0/P1 | `Menu.vue:413+,766+`, `OrderStatus.vue:790+`, `cart.js` |
| 3 | **Inline wallet top-up sheet** on shortfall (pre-filled with the shortfall) instead of a full page-exit; COD fallback inline | Insufficient-balance customers abandon when bounced to the account page | P0 | `Cart.vue:656+` |
| 4 | **Delivery-time estimate before ordering** (tenant "typical prep/delivery time" field shown on cart) | First-time + daily users need "15 or 45 min?" before committing | P0/P1 | profile field + `Cart.vue` |
| 5 | **Persist fulfillment choice + auto-select last/default address** | Returning delivery customer re-selects Delivery + address every session | P1 | `cart.js`, `Cart.vue:262+` |
| 6 | **"Earn ~Y pts on this order"** projection at checkout | Cheap retention nudge | P2 | `Cart.vue` loyalty block |

## Batch R-WAIT — Waiter floor loop ("one-handed, mid-rush")
| # | Item | Why | Sev | Files |
|---|------|-----|-----|-------|
| 1 | **Waiter-calls panel in the waiter app** (bell-calls are currently OWNER-only — invisible to floor staff) | Biggest waiter gap: a customer's bell never reaches the waiter's own device | P0 | `WaiterLayout.vue` + existing `useWaiterCalls` |
| 2 | **Item-ready toggle + "All ready"** in the waiter card (store action + endpoints already exist, no UI) | Waiter picks up at the pass and can't tick items ready | P1 | `WaiterPage.vue`, `waiter.js:370+` |
| 3 | **Action footer: primary + overflow** (one big primary action; Transfer/Merge/Rate/Bill into •••) | 4–7 equal-weight buttons wrap on a phone; no clear "tap this first" | P0 | `WaiterPage.vue:520+` |
| 4 | **Void: bigger tap target + optional quick-pick reason** (12px button + forced typing today) | Accidental voids + slow typing mid-rush | P0 | `WaiterPage.vue:471+,1432+` |
| 5 | **Quick-split ÷2/÷3/÷4 buttons** on the settle partial-amount input | Mental arithmetic on a numeric keypad mid-settle | P1 | `WaiterPage.vue:1064+` |
| 6 | **Waiter real-time via the owner WebSocket group** (15s poll today) | Kitchen "ready" lags up to 15s on the waiter screen | P1 | `WaiterPage.vue:2075+`, `useOwnerRealtime` |
| 7 | **"Needs action" default tab** (pending+ready) instead of "All" | Waiter lands on the noisiest view; urgent tabs are buried | P1 | `WaiterPage.vue:41+` |

## Batch R-OWN — Owner live-ops loop ("run the whole day fast")
| # | Item | Why | Sev | Files |
|---|------|-----|-----|-------|
| 1 | **Primary action button to the TOP of the order card** (+ optional compact queue mode) | Owner scrolls a tall card to reach Confirm/Ready on every order in a rush | P0 | `OwnerOrders.vue:442+` |
| 2 | **Kitchen + Z-report promoted to primary nav** (mobile dock + desktop), out of the settings gear | Kitchen is the most time-critical view; Z-report is a nightly ritual — both buried 2–3 taps deep | P0/P1 | `OwnerLayout.vue` |
| 3 | **Consolidated "Service Status" card** (open + delivery + menu in one row + plain-English summary) | Owner can set open but forget delivery; no at-a-glance combined state | P0 | `OwnerHome.vue:42+` |
| 4 | **86-board from Home quick-actions** (kitchen has a great one; dashboard hides it in a collapsed panel) | 86-ing a dish is 4 steps from the dashboard | P0 | `OwnerHome.vue:309+`, `OwnerDashboardDishPanel.vue` |
| 5 | **Inline price edit on menu rows** (tap price → input → Enter) | Most common menu change is a 6–8 step modal trip today | P1 | `StepDishes.vue`, `OwnerMenuBuilder.vue` |
| 6 | **"Confirm All" visible regardless of active filters** | The bulk-confirm button vanishes when any filter is set (very common) | P1 | `OwnerOrders.vue:209+` |

---

## After restaurant
- **Delivery app** (driver daily loop) — same assessment→friction-fix method.
- **Courier order** (send-package daily loop) — same.
- Cross-cutting: keep the "extremely easy, daily-driver" bar in every batch.

*Deferred / bigger (revisit): owner labor/shifts UI, business-hours auto-open
schedule, low-stock thresholds, customer favourites, guest pickup/delivery,
floor-plan view, ESC/POS thermal printing.*
