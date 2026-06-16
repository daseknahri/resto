# Migrations guide (django-tenants) — hot-table indexes without write outages

This project is multi-tenant via **django-tenants 3.6.0** (Django 4.2). Tenant
tables (the `menu` app — `Order`, `OrderItem`, `OrderPayment`, …) live in a
**separate Postgres schema per tenant**. At deploy the entrypoint runs:

```sh
python manage.py migrate_schemas --shared   # public schema, once
python manage.py migrate_schemas --tenant   # loops over EVERY tenant schema
```

## The problem: `AddIndex` takes an ACCESS EXCLUSIVE lock — once per schema

A plain `migrations.AddIndex` / `db_index=True` builds the index with
`CREATE INDEX` (no `CONCURRENTLY`), which holds an **ACCESS EXCLUSIVE** lock on
the table for the whole B-tree build — blocking reads *and* writes.

For a **tenant** table this is multiplied: `migrate_schemas --tenant` runs the
index build **once per tenant schema, sequentially**. With N tenants that is N
sequential write-outages on the hottest table (`Order`) during the deploy
migrate step. As tenant count grows, deploy-time write downtime grows with it.

## The fix: `AddIndexConcurrently` + `atomic = False`

`CREATE INDEX CONCURRENTLY` builds the index without blocking writes. It **cannot
run inside a transaction**, so the migration must set `atomic = False`.

Prerequisite (already done — `config/settings.py`): `django.contrib.postgres` is
in `SHARED_APPS`, which provides
`django.contrib.postgres.operations.AddIndexConcurrently`. It has no models, so
it adds no migrations.

### Convention for ALL future hot-table index migrations

When adding an index to a high-write table (`Order`, `OrderItem`,
`OrderPayment`, `WalletTransaction`, `NotificationLog`, `DeliveryJob`,
`RideRequest`, `Profile`, `Lead`), the migration MUST:

```python
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False  # CREATE INDEX CONCURRENTLY cannot run in a transaction

    dependencies = [("menu", "0057_orderpayment_idempotency_key")]

    operations = [
        AddIndexConcurrently(
            model_name="order",
            index=models.Index(fields=["customer_phone"], name="order_customer_phone_idx"),
        ),
    ]
```

Use `RemoveIndexConcurrently` for the reverse. Keep one logical index per
migration where practical so a mid-loop failure is easy to reason about.

> Heads-up for `makemigrations`: Django still auto-generates plain `AddIndex`
> when you add `Meta.indexes`. Hand-edit the generated migration to
> `AddIndexConcurrently` + `atomic = False` before merging. `makemigrations
> --check` stays green because the end state (the index) is identical.

## Pending conversion (GATED on the staging rehearsal below)

Three recent, pure-`AddIndex` migrations on hot tables are the conversion
targets (highest value first). Converting them **edits the files in place** —
the end state is identical so `makemigrations --check` stays clean; already-applied
schemas are unaffected (the index already exists), and **new tenant provisioning**
+ any not-yet-migrated environment get the non-locking build.

| Priority | File | Table / schema | Indexes |
|---|---|---|---|
| 1 (highest) | `menu/migrations/0058_ops4_indexes.py` | `Order` / **per-tenant** (lock ×N tenants) | `order_customer_phone_idx`, `order_status_paid_at_idx` |
| 2 | `accounts/migrations/0043_ops4_wallettransaction_index.py` | `WalletTransaction` / public (×1) | `wallettx_tid_type_cat_idx` on `(tenant_id, type, created_at)` |
| 3 | `tenancy/migrations/0042_profile_profile_marketplace_rate_idx.py` | `Profile` / public (×1) | `profile_marketplace_rate_idx` on `(directory_opt_in, is_menu_published, rating_avg)` |

Example for priority 1 (`menu/0058`):

```python
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [("menu", "0057_orderpayment_idempotency_key")]

    operations = [
        AddIndexConcurrently(
            model_name="order",
            index=models.Index(fields=["customer_phone"], name="order_customer_phone_idx"),
        ),
        AddIndexConcurrently(
            model_name="order",
            index=models.Index(fields=["status", "paid_at"], name="order_status_paid_at_idx"),
        ),
    ]
```

## Why this is GATED (do not ship the conversion un-rehearsed)

`CREATE INDEX CONCURRENTLY` fails hard if it runs inside *any* open transaction.
Two paths in django-tenants 3.6.0 must be confirmed transaction-free for an
`atomic = False` migration, and **neither can be verified without a real Postgres**:

1. **Deploy loop** — `migrate_schemas --tenant` running the migration per schema.
2. **New-tenant provisioning** — `auto_create_schema` runs the full migration
   chain for a brand-new tenant. If provisioning (or any wrapping
   `transaction.atomic()` around tenant creation) holds a transaction while the
   chain runs, the `CONCURRENTLY` migration raises and **onboarding breaks**.

A wrong conversion is worse than the lock it fixes, so it is gated on a rehearsal.

## Staging rehearsal — owner GO/NO-GO gate

Run on a staging DB that has **≥2 real tenant schemas** (mirrors prod loop):

1. Apply the converted migration: `python manage.py migrate_schemas --tenant --verbosity=2`.
   - PASS: completes for every tenant, no "cannot run inside a transaction block".
   - During the build, confirm writes to `Order` are **not** blocked (run a test
     order on one tenant while the index builds on another).
2. Provision a NEW tenant end-to-end (the normal onboarding path) and confirm it
   succeeds — this exercises `auto_create_schema` + the full migration chain
   including the `atomic = False` migration.
3. Verify the indexes exist and are **valid** (not `INVALID`):
   `SELECT indexrelid::regclass, indisvalid FROM pg_index WHERE NOT indisvalid;`
   should return zero rows. A failed/cancelled CONCURRENTLY build leaves an
   INVALID index — `DROP INDEX` it and retry before going to prod.
4. Only after 1–3 pass: deploy to production (Coolify is manual — owner-triggered).

**Rollback:** if the rehearsal fails, revert the migration file to plain
`AddIndex` (remove `atomic = False`) — the lock-y build is the known-good
fallback. The deploy entrypoint runs migrate with `set -e`, so a failed
migration fails the deploy closed (Coolify keeps the old healthy container)
rather than serving a half-migrated app.

This rehearsal also unblocks once a staging env exists (see BACKLOG R20).
