"""Backfill the denormalized promo schedule on every public Profile (B8-followup).

The menu.Promotion post_save/post_delete signals keep
Profile.marketplace_promos in sync from the moment they are deployed — but
existing promos predate the signals, so the new column starts out an empty list.
This one-off command walks every ACTIVE tenant and recomputes its denormalized
promo schedule, populating the public Profile rows so the marketplace promo badge
reflects existing promos immediately.

Idempotent — safe to re-run.

    python manage.py backfill_profile_promos

Run it ONCE on deploy, after the tenancy migration that adds the column.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Backfill denormalized Profile.marketplace_promos from per-tenant menu.Promotion rows."

    def handle(self, *args, **options):
        from tenancy.models import Tenant
        from menu.promos_denorm import recompute_tenant_promos

        processed = 0
        failed = 0
        # Only ACTIVE tenants are discoverable in the marketplace, so they are the
        # only ones whose denormalized promo schedule is ever read.
        for tenant in Tenant.objects.filter(
            lifecycle_status=Tenant.LifecycleStatus.ACTIVE
        ):
            try:
                recompute_tenant_promos(tenant)
                processed += 1
            except Exception as exc:  # pragma: no cover - defensive, recompute already guards
                failed += 1
                self.stderr.write(
                    f"  ! failed for {getattr(tenant, 'schema_name', '?')}: {exc}"
                )

        msg = f"Backfilled denormalized promos for {processed} active tenant(s)."
        if failed:
            msg += f" {failed} failed."
        self.stdout.write(self.style.SUCCESS(msg))
