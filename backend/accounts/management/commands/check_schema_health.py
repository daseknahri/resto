"""Assert that the database physically matches the models for critical tables.

This guards against a specific, nasty failure mode: a migration recorded as
APPLIED in django_migrations while its column-adding operations never actually
ran against the database (e.g. a migration file was edited after it was first
applied). Django's `migrate` trusts its own ledger and reports "No migrations to
apply", so `set -e` in the entrypoint never trips -- yet every query touching the
missing column 500s in production. (This is exactly what happened with
accounts.0016 adding WalletTransaction.idempotency_key/balance_after/currency.)

The check derives the EXPECTED columns from the models themselves (not a
hardcoded list), then verifies each one exists in the public schema. All the
models below live in SHARED_APPS, so their tables are in the public schema.
Wave M M-20: the tenant-schema tables (menu.Order / Dish / OrderItem) are
checked in EVERY active tenant schema too — a tenant migration that never ran
used to 500 only that tenant's orders while the public check stayed green.

    python manage.py check_schema_health              # strict: exit 1 on drift
    python manage.py check_schema_health --warn-only   # report only, exit 0

Wire it into the container entrypoint AFTER migrations so a half-applied schema
fails the deploy loudly (Coolify keeps the old healthy container serving) instead
of silently shipping 500s. Set SKIP_SCHEMA_HEALTHCHECK=1 to bypass in an
emergency.
"""
from django.apps import apps as django_apps
from django.core.management.base import BaseCommand
from django.db import connection

# (app_label, ModelName) for the platform-critical tables. All are SHARED_APPS,
# so their tables live in the public schema. Extend this list as new critical
# money/identity models are added.
CRITICAL_MODELS = [
    ("accounts", "Customer"),
    ("accounts", "WalletTransaction"),
    ("accounts", "TenantFloatTransaction"),
    ("accounts", "DriverPayout"),
    ("accounts", "CustomerOrderRef"),
    ("accounts", "WalletChargeRequest"),
    ("accounts", "PlatformConfig"),
    ("accounts", "CustomerPushSubscription"),
    ("tenancy", "Tenant"),
    # Wave M M-20: the delivery job + the top-up attempt row are money/identity
    # critical too (a missing column here 500s dispatch and top-up status).
    ("accounts", "DeliveryJob"),
    ("accounts", "CustomerTopUpAttempt"),
]

# (app_label, ModelName) for the platform-critical tables that live in TENANT
# schemas (menu app), checked in every active tenant schema (Wave M M-20).
TENANT_CRITICAL_MODELS = [
    ("menu", "Order"),
    ("menu", "Dish"),
    ("menu", "OrderItem"),
]


def _active_tenant_schemas():
    """Schema names of active non-public tenants — the ones that hold orders.

    Fail-closed: a query failure propagates (the entrypoint halts) rather than
    silently skipping the tenant checks.
    """
    from tenancy.models import Tenant
    return list(
        Tenant.objects.filter(
            is_active=True,
            lifecycle_status=Tenant.LifecycleStatus.ACTIVE,
        ).exclude(schema_name="public").values_list("schema_name", flat=True)
    )


def _check_table(cur, app_label, model_name, schema):
    """Check one (schema, table) against its model; return a list of problems."""
    from django.apps import apps as _apps
    try:
        model = _apps.get_model(app_label, model_name)
    except LookupError:
        # Model not installed in this build -- skip rather than crash.
        return []

    table = model._meta.db_table
    expected = {f.column for f in model._meta.local_concrete_fields}

    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s",
        [schema, table],
    )
    actual = {row[0] for row in cur.fetchall()}

    if not actual:
        return [f"  - table {schema}.{table} is MISSING entirely ({app_label}.{model_name})"]

    missing = expected - actual
    if missing:
        cols = ", ".join(sorted(missing))
        return [f"  - {schema}.{table} is missing column(s): {cols} ({app_label}.{model_name})"]
    return []


class Command(BaseCommand):
    help = "Verify the database schema physically matches the models for critical tables (catches recorded-but-not-applied migrations)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--warn-only",
            action="store_true",
            help="Report drift but exit 0. Without this flag, any drift exits non-zero (fails the deploy).",
        )

    def handle(self, *args, **options):
        warn_only = options["warn_only"]
        problems = []

        with connection.cursor() as cur:
            for app_label, model_name in CRITICAL_MODELS:
                problems.extend(_check_table(cur, app_label, model_name, "public"))
            # Wave M M-20: tenant-schema tables, in every active tenant schema.
            # Default-on and fail-closed: a tenant whose Order table drifted
            # fails the deploy like a public drift does.
            for schema in _active_tenant_schemas():
                for app_label, model_name in TENANT_CRITICAL_MODELS:
                    problems.extend(_check_table(cur, app_label, model_name, schema))

        if not problems:
            self.stdout.write(self.style.SUCCESS("Schema health OK: all critical tables match their models."))
            return

        report = "Schema drift detected (migrations recorded as applied but DB out of sync):\n" + "\n".join(problems)

        if warn_only:
            self.stderr.write(self.style.WARNING(report))
            self.stderr.write(self.style.WARNING("Continuing anyway (--warn-only)."))
            return

        # Strict mode: raising SystemExit(1) makes `set -e` in the entrypoint halt
        # the container so a half-migrated schema never starts serving.
        self.stderr.write(self.style.ERROR(report))
        self.stderr.write(self.style.ERROR(
            "Refusing to start. Fix the schema (apply the missing columns), then redeploy. "
            "To bypass in an emergency, set SKIP_SCHEMA_HEALTHCHECK=1."
        ))
        raise SystemExit(1)
