"""Backfill the denormalized rating summary on every public Profile (B8).

The menu.Rating post_save/post_delete signals keep Profile.rating_avg /
rating_count in sync from the moment they are deployed — but existing ratings
predate the signals, so the new columns start out null/0. This one-off command
walks every ACTIVE tenant and recomputes its denormalized rating, populating the
public Profile rows so the marketplace/directory listing reflects historical
ratings immediately.

Idempotent — safe to re-run.

    python manage.py backfill_profile_ratings

Run it ONCE on deploy, after the tenancy migration that adds the columns.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Backfill denormalized Profile.rating_avg / rating_count from per-tenant menu.Rating rows."

    def handle(self, *args, **options):
        from tenancy.models import Tenant
        from menu.ratings import recompute_tenant_rating

        processed = 0
        failed = 0
        # Only ACTIVE tenants are discoverable in the marketplace/directory, so they
        # are the only ones whose denormalized rating is ever read.
        for tenant in Tenant.objects.filter(
            lifecycle_status=Tenant.LifecycleStatus.ACTIVE
        ):
            try:
                recompute_tenant_rating(tenant)
                processed += 1
            except Exception as exc:  # pragma: no cover - defensive, recompute already guards
                failed += 1
                self.stderr.write(
                    f"  ! failed for {getattr(tenant, 'schema_name', '?')}: {exc}"
                )

        msg = f"Backfilled denormalized ratings for {processed} active tenant(s)."
        if failed:
            msg += f" {failed} failed."
        self.stdout.write(self.style.SUCCESS(msg))
