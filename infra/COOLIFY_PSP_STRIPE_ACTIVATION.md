# Stripe PSP wallet top-up — activation runbook

> **Status: the code seam is built, tested, and dormant.** This runbook activates it. The seam lets
> a customer top up their wallet by card via **Stripe Checkout**; it credits the wallet on the
> verified `checkout.session.completed` webhook. It ships **disabled** — `PSP_TOPUP_ENABLED` unset
> means the intent endpoint returns `{"enabled": false}` and nothing touches Stripe.
>
> **Owner-only prerequisite:** a Stripe account. Creating the account, obtaining API keys, and
> configuring the webhook are yours — an agent cannot create accounts or hold credentials.

## What's already built (so you know what you're turning on)

| Piece | Location |
|---|---|
| Feature flag + keys | `backend/config/settings.py` — `PSP_TOPUP_ENABLED`, `PSP_STRIPE_SECRET_KEY`, `PSP_STRIPE_WEBHOOK_SECRET`, `PSP_SITE_URL` |
| Start checkout | `CustomerTopUpIntentView` — `POST /api/customer/topup/intent/` |
| Receive payment | `CustomerTopUpWebhookView` — `POST /api/customer/topup/webhook/` |
| Capability probe | customer profile response exposes `psp_topup_enabled` (frontend shows/hides the top-up button) |
| Tests | `backend/tests/test_psp_topup.py` (disabled-path + webhook signature paths) |
| Dependency | `stripe>=10.0.0,<13.0.0` (already installed, unused while dormant) |

Money-safety already handled in code (do **not** weaken these):
- **Idempotent** — credits on `idempotency_key="stripe:<event_id>"`, so Stripe's at-least-once
  redelivery can't double-credit.
- **MONEY-3 hardened** — credits only a session whose `payment_status` is `paid`, and credits the
  **settled `amount_total`** Stripe reports (not the client-requested metadata amount), so a
  partial/adjusted/tampered session can't over-credit.
- **Amount bounds** — the intent endpoint accepts 10–2000 only.

## Currency note (read before activating)

The Checkout Session is created in **MAD** (`"currency": "mad"`, `unit_amount = amount × 100`),
hardcoded in `CustomerTopUpIntentView`. If you operate in another currency, that's a **code change**,
not an env change — flag it before go-live.

## Activation steps

### 1. Create keys in Stripe (start in **test mode**)
- Stripe Dashboard → Developers → API keys → copy the **Secret key** (`sk_test_…`, later `sk_live_…`).

### 2. Create the webhook endpoint in Stripe
- Dashboard → Developers → Webhooks → **Add endpoint**.
- URL: `https://<your-public-menu-domain>/api/customer/topup/webhook/`
  (the customer-facing origin, e.g. `https://menu.yourdomain.com/...`).
- Events to send: **`checkout.session.completed`** (that's the only event the handler acts on).
- Save, then copy the endpoint's **Signing secret** (`whsec_…`).

### 3. Set env in Coolify (see `coolify.env.production.sample`)
```
PSP_TOPUP_ENABLED=1
PSP_STRIPE_SECRET_KEY=sk_test_…      # sk_live_… when you go live
PSP_STRIPE_WEBHOOK_SECRET=whsec_…    # REQUIRED — see warning below
PSP_SITE_URL=https://menu.yourdomain.com   # optional; falls back to PUBLIC_MENU_BASE_URL
```
> **⚠️ Always set `PSP_STRIPE_WEBHOOK_SECRET` in production.** Without it, the webhook still runs but
> **skips signature verification** — any caller could POST a fake `checkout.session.completed` and
> mint wallet credit. The secret is what makes the endpoint trustworthy. (The no-secret path exists
> only for local/staging where the signing secret is unknown.)

Redeploy so the new env takes effect.

### 4. Test-mode smoke (before touching live keys)
1. Confirm the flag is live: the customer profile response now shows `"psp_topup_enabled": true`,
   and the top-up button appears in the account page.
2. Start a top-up in the app → you're redirected to Stripe Checkout.
3. Pay with Stripe's test card **`4242 4242 4242 4242`**, any future expiry, any CVC.
4. Stripe fires `checkout.session.completed` → verify:
   - the wallet balance increased by the **paid** amount, exactly once;
   - a `WalletTransaction` exists with reference `stripe:<session_id>`;
   - `python manage.py reconcile_wallet_balances` shows no drift.
5. **Idempotency check:** in Stripe → Webhooks, **resend** the same event → the balance must **not**
   change again (the `stripe:<event_id>` key dedupes it).
6. **Signature check:** temporarily POST a bogus body to the webhook URL → expect `400`, no credit.

### 5. Go live
- Swap `sk_test_…`/`whsec_…` for the **live-mode** key + a live webhook endpoint's secret.
- Re-run steps 4.1–4.4 with a real small top-up (e.g. 10 MAD), then refund it in the Stripe dashboard.

## Rollback / kill switch
Set `PSP_TOPUP_ENABLED=0` (or unset it) and redeploy. The intent endpoint immediately returns
`{"enabled": false}`, the webhook returns `{"ok": false, "detail": "PSP disabled."}`, and the
frontend hides the button. No data migration, no code change.

## What stays yours
Creating the Stripe account, generating/rotating keys, configuring the webhook endpoint, and holding
the secrets. This runbook is the exact sequence; the credentials and the live smoke are yours.
