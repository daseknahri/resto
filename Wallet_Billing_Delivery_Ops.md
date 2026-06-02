# Wallet, Billing & Delivery — Operations Runbook

Operational reference for the wallet/payments, subscription-billing, tier-gating, and
delivery/driver work. Read this before redeploying so no step is missed — several
changes are **inert or wrong until you complete a manual step** (cron, env, plan flags).

---

## 1. Database migrations (apply on backend redeploy)

Coolify does **not** auto-deploy on push — trigger the backend redeploy manually, which
runs migrations. New since this work:

| App | Migrations | What they add |
|-----|-----------|---------------|
| `accounts` | `0016`–`0019` | Wallet ledger hardening (`idempotency_key`, `balance_after`, `currency`), `TenantFloatTransaction`, P2P + adjustment transaction types |
| `tenancy` | `0027`, `0028` | `Tenant.float_balance`, `Profile.platform_delivery_enabled` |

Verify after deploy: `python manage.py migrate --check` (or `showmigrations`).

---

## 2. Environment variables

| Var | Default | Purpose |
|-----|---------|---------|
| `WALLET_P2P_ENABLED` | `False` | Customer↔customer wallet gifting. **Leave OFF** until you have a money-transmitter license + KYC/AML (see §6). |
| `WALLET_DEFAULT_DIAL_CODE` | `""` (empty) | Digits only, e.g. `212`. Lets customers type local numbers (`06…`) for P2P recipients; empty = senders must type full `+212…`. |

No env is required for the float system, billing, tier gating, or delivery — they work
from the DB/admin.

---

## 3. Scheduled jobs (cron)

Add a **daily** cron in Coolify (or the host scheduler):

```
python manage.py enforce_subscriptions --apply
```

Without this, subscription lapses are **never enforced** — no grace banner, no
suspension. Run once without `--apply` first to preview. Transitions: lapsed →
`payment_overdue_since` set (owner grace banner) → after `Tenant.GRACE_PERIOD_DAYS` (7)
→ suspended; a renewed subscription clears the flag automatically.

---

## 4. One-off / as-needed commands

```
python manage.py sweep_unverified_wallets            # dry-run report
python manage.py sweep_unverified_wallets --apply     # zero balances held by unverified phones
```
Enforces "no verified phone → no wallet" on pre-existing balances. Writes an auditable
`ADJUSTMENT` transaction per wallet. Safe by default (dry-run).

---

## 5. Tier gating — set plan flags BEFORE relying on it

Per-plan ordering entitlements are now truthful (not forced open). A plan with
`can_checkout = False` **and** `can_whatsapp_order = False` is **browse-only** (ordering
UI hidden). After deploy:

1. Django admin → **Plans** (or platform console plan editor): set `can_checkout` /
   `can_whatsapp_order` correctly per tier.
2. Confirm every live/paid restaurant's plan has at least one ordering channel enabled.

`max_dishes`, `max_staff_accounts`, `max_languages` (0 = unlimited) are enforced on
create. Staff-limit returns `staff_limit_reached`; dish-limit `dish_limit_reached`.

---

## 6. Money model summary & gates

- **Float (live):** platform funds a restaurant's `float_balance`; the owner spends it
  down by topping up customers (prepaid, hard cap). Cash reconciled offline. Only
  **active** tenants can fund/distribute; only **phone-verified** customers can receive.
  - Admin: `POST /api/admin/wallet/fund-tenant/` + "Fund a restaurant float" UI.
  - Owner: `POST /api/owner/wallet/topup/` + float card on the wallet page.
- **P2P gifting (built, OFF):** `POST /api/customer/wallet/transfer/`, gated by
  `WALLET_P2P_ENABLED`, rate-limited 20/hour/customer, recipient must be phone-verified
  (E.164-normalized). **Do not enable without legal sign-off + KYC/AML.**
- **Delivery (opt-in per restaurant):** turn on "Use platform driver network" in a
  restaurant's delivery settings → each delivery order spawns a searching `DeliveryJob`
  (driver payout = 100% of the delivery fee). Drivers sign up + work at `/driver`.

---

## 7. Post-deploy smoke (manual)

1. Admin funds a test restaurant's float → owner sees the float card amount.
2. Owner tops up a verified customer who ordered there → balance moves, float drops;
   overspend → `402`; unverified customer → clear rejection.
3. Enable platform delivery on a restaurant → place a delivery order → a job appears in
   the `/driver` app for an online driver → accept → advance to delivered.
4. Set a plan to no ordering channels → that restaurant's menu is browse-only.
