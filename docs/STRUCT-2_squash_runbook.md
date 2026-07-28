# STRUCT-2 — migration squash runbook

> Operational procedure for squashing the 216 migrations flagged by
> [RISK STRUCT-2](RISK_REGISTER.md). **This is a deliberate release-boundary operation, not a
> casual refactor** — it changes the deploy machinery of a multi-tenant money app and must be
> validated on a real multi-tenant DB (it cannot be validated locally without Postgres). Do NOT
> squash blind. The elidability audit (below) has been done; everything else here is the plan.

## Why it's not just `squashmigrations`

Two complications, both discovered by inspection (2026-07-27):

1. **6 `RunPython` data migrations.** Django keeps non-`elidable` `RunPython` in a squash. Five of the
   six are one-time backfills a fresh schema doesn't need and are now marked **`elidable=True`** (done —
   see below), so a squash will drop them. The sixth (`menu/0005` `attach_default_super_category`) is
   **deliberately NOT elidable** — it also *seeds* the default "Menu" `SuperCategory` that a fresh tenant
   schema requires (`Category.super_category` is NOT NULL). A squash of any range covering `menu/0005`
   must keep that RunPython.
2. **3 `AddIndexConcurrently` migrations** (`menu/0060`, `0062`, `0066`, all `atomic = False`). `CREATE
   INDEX CONCURRENTLY` cannot run inside a transaction, so these **cannot be folded into an atomic
   squash**. Squash `menu` only up to **`0059`** (before the first concurrent-index migration) and leave
   `0060+` as individual migrations. `accounts` / `tenancy` / `sales` have no concurrent-index migrations
   and can be squashed fully.

## Elidability audit — DONE (2026-07-27)

Marked `elidable=True` (one-time backfills; fresh schema no-ops):

| Migration | What it backfills |
|---|---|
| `accounts/0050_customer_phone_digits` | `Customer.phone_digits` from existing `phone` |
| `accounts/0058_backfill_vertical_tags` | `vertical` on existing `CustomerOrderRef`/`WalletTransaction` |
| `menu/0035_backfill_completed_orders_paid` | `payment_status`/`paid_at` on historical completed orders |
| `menu/0062_order_phone_digits` | `Order.customer_phone_digits` (the RunPython op only; the migration itself stays un-squashable, see #2) |
| `tenancy/0008_set_basic_plan_max_languages` | `max_languages` on the "starter" plan (redundant — `seed_plans` sets it) |

Left non-elidable: `menu/0005_super_category` (seeds the default SuperCategory — a fresh schema needs it).

`elidable=True` is **behavior-neutral today**: non-squashed migrations still run the RunPython normally; the
flag only takes effect when a squash is generated. Verified: `makemigrations --check` clean, `manage.py
check` clean.

## Preconditions (verify on the target DB before squashing)

1. **Every schema is at/past the squash endpoint.** For each app, confirm all tenant schemas have applied
   through the last migration in the squash range (a schema mid-range would fall back to replaying the
   originals, which must therefore still exist during the transition). Check per schema, e.g.
   `python manage.py migrate_schemas --list` / inspect `django_migrations` in each schema. At the current
   pre-launch scale (public + the `demo` tenant) this is trivially true, but re-verify on the real target.
2. A clean, backed-up DB and a staging environment that mirrors prod tenant topology.

## Procedure (two releases)

**Release 1 — introduce the squashes (keep the originals):**
```
python manage.py squashmigrations accounts 0067        # full
python manage.py squashmigrations tenancy 0049         # full
python manage.py squashmigrations sales  0023          # full
python manage.py squashmigrations menu   0059          # STOP before 0060 (AddIndexConcurrently)
```
Each writes a `NNNN_squashed_*` migration carrying `replaces = [...]`. Review each:
- confirm the elidable RunPython ops were dropped and `menu/0005`'s default-SuperCategory RunPython was
  KEPT;
- confirm no `AddIndexConcurrently` landed inside a squash.
Ship release 1 with both the squash **and** the originals present. A schema past the range picks up the
squash via `replaces` (no replay); a fresh schema runs the squash directly.

**Validate (staging, blocking):**
- Fresh DB: `migrate_schemas --shared && migrate_schemas --tenant` from empty, then
  `manage.py check_schema_health` — the schema must match the models exactly.
- Migrated DB: apply on a staging copy that already has tenants; confirm no migration re-runs and
  `check_schema_health` passes under an active tenant schema.
- Provision a brand-new tenant end-to-end (the e2e CI job already does this) — confirms the default
  SuperCategory + all seed paths still work post-squash.
- Watch error tracking for a full deploy cycle.

**Release 2 — delete the originals** (only after every schema is confirmed past the squash range in prod):
remove the original `0001..NNNN` files that each squash `replaces`, leaving just the squashed migration.
Re-run the same validation.

## Scope / value note

At the current scale this is **low urgency** — the per-schema migrate-chain cost only bites at the
hundreds-of-tenants ceiling that [MULTITENANCY-1](RISK_REGISTER.md) treats as a conscious decision. Do this
at a deliberate release boundary when either that scale approaches or a migration window becomes an
operational pain — not as a speculative cleanup. The elidability prep above is the safe, done part; the
squash itself is the owner/release-boundary step.
