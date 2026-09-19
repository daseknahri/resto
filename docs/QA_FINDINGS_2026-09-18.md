# E2E QA findings — 2026-09-18 (live prod)

Read-only end-to-end pass against the **live** deployment (`menu.ibnbatoutaweb.com` + the
`doro.menu.ibnbatoutaweb.com` tenant storefront). No orders placed, no auth, no mutations —
prod is real. Compiled for this week's work.

## Summary
Two production issues, one **critical**. Everything I *could* reach on the frontend rendered
cleanly; the blockers are backend/infra, and they prevent testing the whole transactional path.

| # | Sev | Area | One line |
|---|-----|------|----------|
| **F1** | 🔴 **CRITICAL** | backend | **The entire `/api/*` surface returns 500 on every request, all hosts** — the backend API is effectively down. |
| **F2** | 🟠 HIGH | infra/TLS | Tenant-storefront subdomains have no valid TLS (expired + wrong-CN) — every restaurant storefront is HTTPS-unreachable. |

Because of F1 + F2, the real customer journey (browse a menu → cart → checkout → order status)
and all authenticated surfaces (owner/waiter/driver/admin) could **not** be exercised this pass.

> **⛔ NEEDED FROM OWNER to run the full E2E:** a **staging URL with valid TLS + a live API**, and
> **test credentials** for each role (customer, owner, waiter, driver, platform admin). Prod can't be
> used for the transactional/authenticated flows — it's real data, and right now the API is down (F1)
> and tenant TLS is broken (F2). Once staging + creds exist, the customer transactional path and every
> authenticated surface can be tested safely.

---

## F1 — 🔴 CRITICAL — the backend API is down (every `/api/*` request 500s)

**What I saw**
- Loading `https://menu.ibnbatoutaweb.com` fires `GET /api/customer/session/?lang=en` which returns
  **500**, repeated **~6× per page load** (the frontend's retry wrapper amplifies each logical call).
- Probing further: **every** `/api/*` endpoint returns 500 — `/api/marketplace/`, `/api/super-categories/`,
  `/api/meta/`, `/api/health/`, `/api/` — on **both** the platform host **and** the `doro` tenant host
  (tested with `curl -k` to bypass F2). Only non-API routes work, and only because they're **static SPA
  files** served before Django (the marketing shell renders, masking the outage).
- The 500 is a **bare Django `Server Error (500)` HTML page**, not a DRF JSON error, and it's **fast
  (~0.2 s)** — an immediate application-level exception, not a slow DB timeout.

**Where it's failing (evidence-based)**
- `/api/health/` (`backend/config/api.py:248` `health_view`) is explicitly built to survive a DB outage
  and return `503 {status:"down"}`. It instead returns a **bare 500** → the request dies in **middleware,
  before any view runs**.
- The first middleware is the custom `config.middleware.TenantAwareMainMiddleware`, which (django-tenants
  style) resolves the tenant by querying the public-schema tenants table **on every request**. A fast,
  universal, middleware-level 500 across all hosts is the signature of **that DB query failing** →
  **the database is unreachable / erroring** (Postgres down, connection refused, auth, or a schema/migration
  state problem).

**Impact**
- No API-backed feature works anywhere: sessions, marketplace listings, menus, cart, orders, owner/admin
  dashboards — all 500. The app only *looks* alive because the static marketing shell renders.
- Every visitor triggers 6 server 500s → Sentry/log flooding.

**This week**
1. **Immediate:** pull the traceback from Sentry (`sentry-sdk` is wired) or Coolify logs for any `/api/`
   request, and check the **database container / `DATABASE_URL` / Postgres health** in Coolify. This is a
   right-now outage, not a "later" item.
2. Secondary (resilience): the health endpoint is meant to report DB-down as `503` but can't, because it
   sits **behind** the tenant middleware that needs the DB. Consider a DB-independent liveness route (or
   ordering the health check ahead of tenant resolution) so `/api/health/` can actually report "db down"
   instead of a generic 500.
3. Consider whether the frontend's retry wrapper should **not** retry a 500 on the session bootstrap
   (6 failing calls per load is pure noise once the endpoint is known-down).

---

## F2 — 🟠 HIGH — tenant-storefront subdomains have no valid TLS

**What I saw**
- `curl -I https://doro.menu.ibnbatoutaweb.com/menu` → `SEC_E_CERT_EXPIRED`; the in-app browser refused to
  navigate (cert interstitial).
- `openssl`: the subdomain is served the **apex cert** `CN=menu.ibnbatoutaweb.com`, valid **May 10 →
  Aug 8 2026 → expired ~6 weeks ago**. The apex host itself has a *renewed* cert (Aug 24 → Nov 22 2026)
  that **did not propagate to subdomains**. There is **no wildcard `*.menu.ibnbatoutaweb.com` cert**, so
  even unexpired the apex cert wouldn't cover a subdomain (CN/SAN mismatch).

**Impact**
- Every tenant storefront (`<slug>.menu.ibnbatoutaweb.com` — the actual customer-ordering surface) is
  unreachable over HTTPS. The platform hub's "View live demo" → `https://doro.menu.ibnbatoutaweb.com/menu`
  is a dead link. A launch-blocker for the per-subdomain multi-tenant model.

**This week**
- Provision a **wildcard cert `*.menu.ibnbatoutaweb.com`** (Coolify/Let's Encrypt DNS-01), or issue +
  auto-renew a per-subdomain cert as part of tenant provisioning. Ties to the pending "DNS/TLS ops launch"
  item — but it's actively broken now, so it graduates from "launch task" to "fix".

---

## What passed (no findings) — the reachable frontend is healthy
Tested on the platform host (the only host with valid TLS), desktop + mobile (375×812):
- **Responsive:** landing/hub, sign-in, and 404 all render with **zero horizontal overflow** at 375px;
  mobile bottom dock present and correct.
- **RTL / Arabic:** switching to Arabic applies `dir="rtl"` + `lang="ar"`, translates content
  (`Kepoli — مدينتك في تطبيق واحد`), and does **not** break layout (no overflow).
- **i18n completeness (AR):** scanned the rendered hub — **zero raw i18n keys** and zero English leakage
  (only Latin text is the `contact@kepoli.app` email). The hand-rolled i18n + `verify:i18n` gate holds.
- **Sign-in page:** renders, proper form (`autocomplete="username"` / `current-password`), links to
  activate / forgot-password.
- **404 page:** renders the NotFound view (localized, "View menu" / "Back", shows the bad path).

These are the exact surfaces the recent mount-smoke campaign guarded — they render correctly in prod.

## Not tested this pass (blocked / needs setup)
- **Customer transactional path** (menu → cart → checkout → order status/tracking): blocked by **F2**
  (tenant-storefront TLS) *and* **F1** (API down). Re-run once both are fixed, or against a staging host
  with valid TLS + a live API.
- **Authenticated surfaces** (owner, waiter, driver, admin): need test credentials and are unsafe to
  create/exercise on prod. Best done on **staging**.
- **RTL directional-glyph review** (the `messages-ar.js` literal `←/→` arrows on owner/status pages): those
  pages need auth + a working API, so still open — verify visually once F1/F2 clear.

## Note on deployment shape
`menu.ibnbatoutaweb.com` is currently a **demo/pre-launch** deployment (heavy "DEMO / View live demo /
List your business" marketing, the `doro` demo tenant, no real catalog on the hub). The findings above are
real regardless, but F1 in particular may reflect an **idle/broken deployment state** — confirm whether the
DB/container simply needs a restart vs. a deeper config issue.

---

## Update — post-fix E2E round (same day)

**F1 is RESOLVED.** Root-caused live in Coolify and fixed: the API was down because Postgres hit
`max_connections=50` — caused by **8 orphaned `admin` containers from ~4-month-old deploys** still holding
connections. Removed them (`docker rm -f`) + restarted Postgres → all endpoints back to 200
(`/api/health/` green). Full write-up + durable fixes in
[`INCIDENT_2026-09-18_db_connection_exhaustion.md`](INCIDENT_2026-09-18_db_connection_exhaustion.md).

With the API back, the **marketplace consumer path** (previously blocked by F1) was tested on the platform
host and **works**: `/order` lists businesses with full filters; `/order/<slug>` loads the menu (categories,
items, allergen filters, reviews); add-to-cart works (per-tenant `mkt:cart:<slug>` localStorage). Renders
correctly in Arabic/RTL. Note this path lives on the **platform host**, so F2 (tenant-subdomain TLS) does
**not** block it. Two new flaws surfaced:

### F3 — [MED] marketplace shows prices in **US$** for a Moroccan (tanger) restaurant
- On `/order/daseknahri` (business "matsco", city tanger, cuisine moroccan) every price + the delivery fee
  renders as **`US$`** — DOM scan: **43× `US$`, 0× `MAD`**.
- The app is single-**MAD** in prod (per `CLAUDE.md`), so a customer in Morocco seeing USD is wrong. Confirm
  whether it's a **tenant currency misconfiguration** (owner set USD) or the **marketplace defaulting to USD**
  instead of reading the tenant currency. Either way it's a trust/clarity problem on the whole ordering surface.
- (Prices are obvious test data — bread 400, tacos 100 — so this is the demo tenant, but the currency *label*
  is the concern.)

### F4 — [MED] contradictory open/closed status on the storefront header
- The `/order/<slug>` header shows **"مفتوح" (Open, green dot)** and **"مغلق اليوم" (Closed today)**
  simultaneously (both confirmed present in the DOM). Confusing to customers — verify the business-hours
  display logic (is it "open now but closed later today", or a genuine state contradiction?).

### Not exercised (deliberate / still blocked)
- **Place-order / checkout submit** — that's a real order mutation on prod; stopped at the cart. Needs a
  controlled test on staging (or an owner-run test order).
- **Authenticated surfaces** (owner/waiter/driver/admin) — need test credentials / staging.
- **Tenant-subdomain storefronts** (`<slug>.menu.…`) — still blocked by **F2** (expired/mismatched TLS).

---

## F2 — confirmed root cause + fix runbook (2026-09-19)

Confirmed live in Coolify + Hostinger DNS:
- **DNS is fine** — a `*.menu` A record → the Coolify box (85.31.239.111) exists, so every
  `<slug>.menu.ibnbatoutaweb.com` **resolves**. An `_acme-challenge.menu` TXT is present too.
- **The Coolify app has only 2 domains configured:** `menu.ibnbatoutaweb.com` (frontend) and
  `admin.menu.ibnbatoutaweb.com` (admin). **No wildcard `*.menu.…` and no per-tenant `<slug>.menu.…`
  domain.** So Traefik holds certs only for those two, and every tenant storefront falls through to
  Traefik's **fallback = the expired apex cert**. That is F2.
- The `_acme-challenge.menu` TXT is a **static** value — Let's Encrypt DNS-01 rotates the token each
  renewal, so a hand-set static record issues **once** then can't auto-renew (why it expired).

### Fix path ① — interim, unblocks the live tenant(s) now (HTTP-01, no secrets)
1. Coolify → app → **Domains → Add**: `https://daseknahri.menu.ibnbatoutaweb.com` (+ any other live
   `<slug>.menu.ibnbatoutaweb.com`) → route to the **frontend** service (internal port 3000).
2. **Save → Redeploy** the app. Traefik requests an HTTP-01 cert per subdomain.
3. Verify: `curl -I https://daseknahri.menu.ibnbatoutaweb.com` → no cert error.
- Caveat: the redeploy also applies the existing **"Changes pending"** and pulls current `main` — review
  the pending changes first. Manual per tenant → fine for the handful live today, not for self-serve.

### Fix path ② — durable, right for a multi-tenant SaaS (wildcard via DNS-01)
1. Create a **Hostinger DNS API token**.
2. Configure the Coolify **proxy** (Server → Proxy → dynamic Traefik config) with a
   `certificatesResolvers` using **`dnsChallenge`** (lego provider `hostinger`; verify support, else move
   DNS to a Traefik-supported provider e.g. Cloudflare) + the API token as env.
3. Add **`*.menu.ibnbatoutaweb.com`** as a frontend domain.
4. Traefik issues + **auto-renews** the wildcard, rotating `_acme-challenge.menu`. Delete the stale static
   `_acme-challenge.menu` TXT.
5. Verify: `curl -I https://<anyslug>.menu.ibnbatoutaweb.com` → valid `CN=*.menu.ibnbatoutaweb.com` cert.

> These require a redeploy and/or a DNS API secret, so they're operator-run.
