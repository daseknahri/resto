"""Periodically reconcile the four denormalized Profile mirrors (RISK DATA-5).

`Profile.rating_avg` / `rating_count` (menu.ratings.recompute_tenant_rating),
`Profile.marketplace_promos` (menu.promos_denorm.recompute_tenant_promos) and
`Profile.closure_dates` (menu.closure_denorm.recompute_tenant_closures) are all
denormalized copies of per-tenant-schema data, kept in sync by post_save /
post_delete signals at write time (see the one-off `backfill_profile_ratings`
/ `backfill_profile_promos` / `backfill_profile_closures` commands that first
populated them).

Signals are fire-and-forget: if one is ever missed — a bulk `.update()` that
bypasses `save()`, a signal handler exception swallowed before it reaches the
recompute call, a schema restored from a backup taken between signal and
commit — the public Profile mirror silently drifts out of sync with the
tenant-schema source of truth. Unlike `reconcile_order_refs` (RISK DATA-1)
there is no orphan to *detect* here: these are pure best-effort display
mirrors (rating badge, promo badge, closure-aware "open now" check) with no
money/payout risk, so recompute-and-overwrite in a single pass is safe —
there is nothing to report before fixing, so this command is "fix-only",
unlike the detect/--fix split in reconcile_order_refs.

Reuses the three recompute functions verbatim (no aggregation logic is
duplicated here); each one manages its own tenant/public schema_context
internally and already swallows its own exceptions (logging and returning)
so a single bad tenant never breaks a rating/promo/closure save. The
try/except per tenant below is defensive: it protects the run against
anything unexpected (e.g. the Tenant row itself misbehaving) so one tenant
can never abort the whole sweep.

No --dry-run: a preview would have to reimplement each recompute's
aggregation to show what *would* change, which would duplicate the very
logic this command is meant to reuse. The recompute functions are already
idempotent (recomputing an unchanged tenant is a no-op update), so simply
re-running this command is the safe, cheap way to check for drift.

    python manage.py reconcile_profile_denorms

Schedule on a light cadence (e.g. hourly) alongside `sweep_delivery_jobs` /
`reconcile_driver_earnings`.
"""
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Recompute the denormalized Profile mirrors (rating_avg/rating_count, "
        "marketplace_promos, closure_dates) for every active tenant (RISK DATA-5)."
    )

    def handle(self, *args, **options):
        from tenancy.models import Tenant
        from menu.ratings import recompute_tenant_rating
        from menu.promos_denorm import recompute_tenant_promos
        from menu.closure_denorm import recompute_tenant_closures

        processed = 0
        failed = 0

        # Only ACTIVE tenants are discoverable in the marketplace/directory, so they
        # are the only ones whose denormalized Profile mirrors are ever read —
        # mirrors the backfill_profile_* commands' tenant selection.
        for tenant in Tenant.objects.filter(
            lifecycle_status=Tenant.LifecycleStatus.ACTIVE
        ):
            try:
                recompute_tenant_rating(tenant)
                recompute_tenant_promos(tenant)
                recompute_tenant_closures(tenant)
                processed += 1
            except Exception:
                # Defensive only — each recompute already catches and logs its own
                # failures. This guards the sweep itself so one bad tenant can never
                # abort reconciliation for the rest.
                failed += 1
                logger.exception(
                    "reconcile_profile_denorms: error processing tenant %s",
                    getattr(tenant, "slug", "?"),
                )

        msg = f"reconcile_profile_denorms: {processed} tenant(s) reconciled."
        if failed:
            msg += f" {failed} failed."
        self.stdout.write(self.style.SUCCESS(msg))
