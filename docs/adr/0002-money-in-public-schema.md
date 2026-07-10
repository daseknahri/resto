# ADR-0002: Money, drivers & directory live in the public schema (cross-schema loose refs)

- **Status:** Accepted — forced by [ADR-0001](0001-schema-per-tenant.md), carries an integrity gap
- **Date:** documented 2026-07-10
- **Related risk:** [DATA-1](../RISK_REGISTER.md), [DATA-2](../RISK_REGISTER.md), [MONEY-1](../RISK_REGISTER.md)

## Context
With `menu` tenant-scoped ([ADR-0001](0001-schema-per-tenant.md)), any data that must be
queried *across* restaurants cannot live in a tenant schema without an O(N-schemas) fan-out.
The wallet ledger, driver payouts, delivery jobs, the customer's cross-restaurant order
history, and the marketplace directory are all inherently cross-tenant.

## Decision
Put all cross-tenant data in the **`public` schema** (`accounts`, `tenancy`, `sales`). Because a
public-schema row cannot hold a foreign key to a tenant-schema `Order`, join the two planes with
a **stringly-typed pair**: `(tenant_id IntegerField, order_number CharField)`. Denormalize a
public **`CustomerOrderRef`** mirror of each customer's orders so "My Orders" doesn't fan out,
and mirror a few tenant aggregates (`rating_avg`, `marketplace_promos`, `closure_dates`) onto
the public `Profile` for the directory.

## Consequences

### Good
- Cross-tenant reads (customer history, payouts, directory) are single-schema and fast.
- The money ledger lives in one place with normal indexes and — implicitly — proves that
  shared-schema multitenancy works for Kepoli (relevant to [ADR-0001](0001-schema-per-tenant.md)'s
  "when to revisit").
- Point-in-time **snapshots** on financial rows (`commission_rate_applied`,
  `OrderItem.unit_price/dish_name`) are correct and must-freeze — this is event-sourcing-lite done
  right, *not* drift.

### Bad / honest tradeoffs
- **The database enforces no cross-plane integrity.** No FK → no cascade, no orphan protection.
  There is **no `Order` `post_delete` handler**; a purged order or dropped schema leaves live
  `DeliveryJob`/`WalletTransaction`/`CustomerOrderRef` rows pointing at nothing — a driver could
  be paid for an order that no longer exists (DATA-1).
- **`order_number` is unique only per-schema.** Any public query by `order_number` without
  `tenant_id` cross-contaminates restaurants — the exact class behind the leaks already fixed.
- **The `CustomerOrderRef` mirror can silently drift** — it syncs on `post_save` only, has no
  `post_delete`, and swallows errors (`except: pass`) (DATA-2).
- **The `Profile` aggregate mirrors** are maintained by four scattered best-effort signals; a
  missed signal shows wrong ratings/promos with nothing to catch it (DATA-5).

## Alternatives considered
- **Shared-schema + RLS** would make these real FKs and delete the whole class — see
  [ADR-0001](0001-schema-per-tenant.md). It's the greenfield answer; not a quick patch now.
- **Globally-unique `order_number`** (`{tenant_id}-{seq}` or UUID) would let public refs use one
  column and remove cross-contamination risk without changing the schema model — a cheaper partial
  mitigation worth doing regardless (see DATA-1 fix).

## When to revisit
Do the cheap mitigations now (globally-unique order numbers + a reconciliation job for orphaned
refs + `post_delete` cleanup — DATA-1/DATA-2). Revisit the whole model only alongside
[ADR-0001](0001-schema-per-tenant.md).
