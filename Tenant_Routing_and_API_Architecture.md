# Tenant Routing and API Architecture

## Purpose

This document explains how restaurant tenant routing works today, how DNS and subdomains should be configured, and how the platform can evolve later to support native mobile apps and third-party integrations without forcing an early rewrite.

## Current Production Model

### Domains

- `kepoli.com`
  - public sales landing
  - lead capture
  - shared public API on `/api`
- `admin.kepoli.com`
  - platform superadmin interface
  - shared public/admin API on `/api`
- `slug.kepoli.com`
  - one restaurant tenant
  - customer menu pages
  - owner workspace pages
  - tenant API on `/api`

### Tenant Identity Strategy

The current system is **host-based multi-tenancy**.

Tenant identity comes from the request host:

- `demo.kepoli.com` -> tenant `demo`
- `yassernahri7.kepoli.com` -> tenant `yassernahri7`

This is handled in middleware by resolving the hostname to a `Domain` row and switching Django to the correct tenant context.

### Owner Flow

1. Lead is submitted on `kepoli.com`
2. Platform admin approves and provisions the lead
3. System creates:
   - tenant
   - primary domain
   - owner user
   - activation token
4. Owner receives:
   - activation URL: `https://slug.kepoli.com/activate?token=...`
   - sign-in URL: `https://slug.kepoli.com/signin`
   - workspace URL: `https://slug.kepoli.com/owner`
5. Owner activates account and is redirected into onboarding/workspace

### Why This Model Is Correct Right Now

For the current product, this is the simplest and strongest architecture because:

- the browser is already on the tenant subdomain
- Django can resolve tenant identity without extra headers or URL conventions
- customer and owner interfaces share the same tenant domain cleanly
- same-host `/api` avoids unnecessary cross-subdomain complexity

## DNS and Proxy Requirements

### DNS

At Hostinger, production should include:

- `A` record: `@` -> VPS IP
- `A` record: `admin` -> VPS IP
- `A` record: `*` -> VPS IP

This wildcard record allows any restaurant subdomain to resolve:

- `resto-a.kepoli.com`
- `resto-b.kepoli.com`
- `resto-c.kepoli.com`

### Proxy / Coolify Routing

Reverse proxy rules must preserve the host:

- `kepoli.com` -> frontend service
- `admin.kepoli.com` -> admin service
- `*.kepoli.com` -> frontend service
- `/api` on `kepoli.com`, `admin.kepoli.com`, and `*.kepoli.com` -> Django API service

Important:

- `slug.kepoli.com/api/...` must reach Django with `Host: slug.kepoli.com`
- tenant routing depends on that host remaining intact

## Stage 1: Current Web SaaS

### Shape

- browser-based product only
- landing + admin + tenant subdomains
- host-based tenant routing
- same-host `/api`

### Good Fit For

- QR menu SaaS
- customer browsing
- WhatsApp handoff
- reservations
- owner workspace

### Recommendation

Keep this as the production baseline.

Do not replace it yet.

## Stage 2: Web SaaS + Public API Layer

This stage keeps the current host-based web product, but adds a **central API contract** for future consumers.

### New Addition

- `api.kepoli.com`

This would be used for:

- internal API versioning
- future partner endpoints
- external dashboards
- automation workflows
- first-party integrations

### Tenant Identity In Stage 2

At this stage, the platform may support **two modes**:

1. host-based mode for the web app
   - `slug.kepoli.com/api/...`
2. explicit-tenant mode for central API consumers
   - `api.kepoli.com/v1/...`

Explicit tenant identity can be provided through one of these patterns:

- header
  - `X-Tenant: demo`
- URL
  - `/v1/tenants/demo/menu`
- token claim
  - tenant encoded in JWT/session token

### Why Stage 2 Is Useful

It lets the web product remain stable while giving the platform a more standard integration surface.

This is an **additive architecture**, not a rewrite.

## Stage 3: Web SaaS + Native Mobile + Integrations

This is the point where a central API becomes much more important.

### Why

Native mobile apps and third-party integrations usually prefer:

- one stable API base domain
- versioned endpoints
- explicit tenant identity
- token-based auth

Instead of each client switching between:

- `resto1.kepoli.com`
- `resto2.kepoli.com`
- `resto3.kepoli.com`

they typically use:

- `api.kepoli.com`

and identify tenant explicitly in the request.

### Example

Current web request:

```http
GET /api/categories/
Host: demo.kepoli.com
```

Future mobile/integration request:

```http
GET /v1/categories
Host: api.kepoli.com
Authorization: Bearer <token>
X-Tenant: demo
```

or:

```http
GET /v1/tenants/demo/categories
Host: api.kepoli.com
Authorization: Bearer <token>
```

### Benefits

- easier SDKs
- easier mobile app configuration
- simpler partner integration docs
- cleaner webhook/callback setup
- easier versioning and deprecation policy

## Recommended Evolution Path

### Now

Use only:

- host-based tenant routing
- same-host `/api`
- wildcard subdomain DNS

### Next Structural Step

Add:

- API contract documentation
- versioned API planning
- explicit tenant strategy design for future central API consumers

### Later, When Needed

Add:

- `api.kepoli.com/v1/...`
- explicit tenant identification for mobile/integrations
- token strategy separated from browser session behavior

## Decision Rule

Do **not** switch the platform away from host-based routing just because the number of restaurants grows from 10 to 100.

Reconsider the architecture only when at least one of these becomes true:

- native mobile app is being built
- external integrations are being shipped
- multiple external client types need one stable API domain
- tenant schema operations become an operational bottleneck
- premium tenants require stronger isolation

## Practical Conclusion

- Current model is correct for launch and early growth
- Same-host `/api` is the right production shape today
- Central API should be a future extension, not a present rewrite
