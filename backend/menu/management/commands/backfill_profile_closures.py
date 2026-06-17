"""Backfill the denormalized closure dates on every public Profile.

The menu.ClosureDate post_save/post_delete signals keep
Profile.closure_dates in sync from the moment they are deployed — but
existing ClosureDate rows predate the signals, so the new column starts out
an empty list. This one-off command walks every active tenant and recomputes
its denormalized closure date list.

Idempotent — safe to re-run.

    python manage.py backfill_profile_closures

Run it ONCE on deploy, after the tenancy migration that adds the column.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Backfill denormalized Profile.closure_dates from per-tenant menu.ClosureDate rows."

    def handle(self, *args, **options):
        from tenancy.models import Tenant
        from menu.closure_denorm import recompute_tenant_closures

        processed = 0
        failed = 0
        for tenant in Tenant.objects.filter(
            lifecycle_status=Tenant.LifecycleStatus.ACTIVE
        ):
            try:
                recompute_tenant_closures(tenant)
                processed += 1
            except Exception as exc:  # pragma: no cover
                failed += 1
                self.stderr.write(
                    f"  ! failed for {getattr(tenant, 'schema_name', '?')}: {exc}"
                )

        msg = f"Backfilled denormalized closures for {processed} active tenant(s)."
        if failed:
            msg += f" {failed} failed."
        self.stdout.write(self.style.SUCCESS(msg))
