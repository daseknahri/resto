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
