# ADR-0001: Schema-per-tenant multitenancy (django-tenants)

- **Status:** Accepted — with a conscious ceiling to decide (see "When to revisit")
- **Date:** original decision early in the project; documented 2026-07-10
- **Related risk:** [MULTITENANCY-1](../RISK_REGISTER.md), [DATA-1](../RISK_REGISTER.md)

## Context
Kepoli serves many independent restaurants from one deployment. Each restaurant's operational
data (orders, menu, dine-in) must be strongly isolated from every other's. Three standard
models exist: (a) separate databases per tenant, (b) **separate Postgres schemas per tenant**
(shared DB), (c) shared schema with a `tenant_id` column + row-level security.

## Decision
Use **django-tenants** (schema-per-tenant). Each restaurant gets a Postgres schema
`tenant_<slug>`; a middleware resolves the request subdomain to a `Tenant` and calls
`connection.set_tenant()`, which sets `search_path`. **Only the `menu` app is tenant-scoped**
(`TENANT_APPS`); `accounts`, `tenancy`, `sales` live in the shared `public` schema.

## Consequences

### Good
- **Isolation is physical and automatic** for the tenant plane — `Order.objects.all()` inside
  a request can only see the current restaurant's rows. No `WHERE tenant_id` to forget.
- Per-tenant operational data is cleanly partitioned; a runaway query in one schema is
  naturally bounded.
- django-tenants provides provisioning, migration-per-schema, and routing out of the box.

### Bad / honest tradeoffs
- **The isolation boundary landed in the wrong place for a marketplace.** Kepoli's defining
  queries — customer order history, driver payouts, the directory — are inherently *cross*-tenant.
  That is precisely why the entire money/delivery/identity layer had to be pulled **out** of the
  tenant schemas into `public` (see [ADR-0002](0002-money-in-public-schema.md)). The count of
  loose cross-schema references in the codebase is the evidence that this model fights the grain.
- **O(N) deploy migrations.** Each `menu` migration runs once *per schema*. A hot-table index is
  N sequential `ACCESS EXCLUSIVE` locks. At hundreds of tenants, migration windows become an
  operational hazard.
- **No PgBouncer transaction-pooling.** `SET search_path` is session state, so you're limited to
  session-pooling → a connection ceiling well below what shared-schema would allow.
- **O(N) cross-tenant analytics** — any "across all restaurants" query fans out over schemas.
- **A latent landmine:** tenant provisioning wraps schema creation in `transaction.atomic()`, but
  the natural perf fix `AddIndexConcurrently` **cannot run inside a transaction**. Shipping it
  as written would break tenant signup.

## Alternatives considered
- **Shared schema + `tenant_id` FK + Postgres Row-Level Security.** Keeps `Order` in the same
  physical tables as `DeliveryJob`/`WalletTransaction`, so cross-plane relationships become real,
  enforced, cascade-aware FKs — eliminating the entire loose-ref integrity class (DATA-1). Scales
  to thousands of tenants with one migration per deploy and PgBouncer transaction-pooling.
  Tradeoff: isolation becomes a `WHERE`-clause/RLS-policy discipline rather than a physical wall
  (a leak is a bug, not impossible). **The money layer already runs this way successfully** — it's
  proof the pattern works here.
- **Database-per-tenant.** Even stronger isolation, even worse O(N) ops. Rejected.

## When to revisit
**Decide your true tenant ceiling — that single number governs this decision:**
- If the realistic ceiling is **low-hundreds of premium tenants**, schema-per-tenant is a
  reasonable, defensible choice. **Keep it.** Do *not* rewrite.
- If you genuinely target **thousands** of tenants, plan a migration to shared-schema + RLS
  before the migration-per-schema and connection ceilings bite. This is an XL project — start it
  deliberately, not reactively.

Record the chosen ceiling here when you decide it: **_[ceiling not yet decided]_**.
