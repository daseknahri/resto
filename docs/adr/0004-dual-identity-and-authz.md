# ADR-0004: Dual identity, shared cross-subdomain cookie, and authorization-by-convention

- **Status:** Accepted historically — **this is the #1 structural liability; changing it is planned**
- **Date:** documented 2026-07-10
- **Related risk:** [AUTHZ-1](../RISK_REGISTER.md) (critical), [IDENTITY-1](../RISK_REGISTER.md), [SER-1](../RISK_REGISTER.md)

## Context
Kepoli has two very different principal types: **staff/owner/admin** (a Django `User`) and
**customers** (a lightweight, high-volume, often-guest identity). The super-app UX wants one
sign-in to work across every restaurant subdomain.

## Decision (as it stands today)
- **Staff/owner/admin** → `request.user` via DRF `SessionAuthentication`.
- **Customers** → a hand-rolled `request.session["customer_id"]`, read directly in views;
  **never** populated into `request.user`.
- **One session cookie for all subdomains:** `SESSION_COOKIE_DOMAIN = ".<suffix>"`.
- **Authorization is enforced imperatively inside handlers** — a first-line
  `if not _is_tenant_owner(request): return 403` — rather than by DRF permission classes on most
  endpoints. Reusable permission classes exist but are applied to only ~60 of ~262 endpoints.

## Consequences

### Good
- Framework-edge defaults are sound: DRF default permission is `IsAuthenticated` (not `AllowAny`);
  BasicAuth + browsable API are disabled in production; error envelope is uniform.
- The team **documented** the shared-cookie hazard and the `_is_tenant_owner` rule (in `CLAUDE.md`).

### Bad / honest tradeoffs (why this is critical)
- **The customer is invisible to DRF.** Because customer identity never reaches `request.user`, a
  permission class *cannot* see it — so customer-owned endpoints are forced to `AllowAny` + manual
  `session.get("customer_id")` checks. You literally cannot write `IsOrderOwner`. (IDENTITY-1)
- **Authorization is opt-in, so "forgot the guard" is the default path.** The tenant-match
  predicate is copy-pasted into 5+ places with **two divergent `_is_tenant_owner` helpers**. Any
  new endpoint that omits the line, or checks the role but not `tenant_id`, is a hole.
- **The shared cookie removes the last backstop.** An authenticated owner of tenant A presents the
  same principal to tenant B. So every forgotten guard is not a within-tenant escalation — it's a
  **cross-tenant data breach** (competitor revenue, PII, customer lists). The Z-report leak and
  order-status IDOR were symptoms of exactly this. (AUTHZ-1)
- **Writes bypass serializers** (242 raw `request.data` reads vs 41 serializer writes) → validation
  is hand-rolled, breeding price/amount-manipulation bugs on money endpoints. (SER-1)

## The target design (planned)
1. **Unify identity** — a `CustomerSessionAuthentication` DRF class hydrates `request.user` from
   `session["customer_id"]`, so all principals flow through one auth stack. (IDENTITY-1)
2. **Central policy layer** — one tested module: `IsTenantMember`, `IsTenantOwner` (always
   tenant-match), `IsOrderOwner`, `IsPlatformAdmin`, applied via `permission_classes` +
   `has_object_permission`. Delete both `_is_tenant_owner` helpers and the ~45 inline guards.
3. **Defense-in-depth backstop** — a `TenantScopedManager`/middleware assertion so any
   public-schema object returned must carry `tenant_id == request.tenant.id`; a forgotten filter
   fails **closed** instead of leaking. **Do this first — it protects everything immediately.**
4. Route money/price writes through serializers (SER-1).

## When to revisit
Before the next tenant onboards at volume. Sequence: backstop (3) → identity (1) → policy layer
(2). This is the highest-leverage refactor in the codebase.
