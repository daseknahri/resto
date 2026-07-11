"""Detect (and optionally clean) orphaned public order-refs — RISK DATA-1.

`DeliveryJob`, `CustomerOrderRef` and `CustomerRating` live in the PUBLIC schema and
reference a tenant order by a LOOSE `(tenant_id, order_number)` pair — there is NO FK.
If an `Order` is ever removed (a dropped tenant schema, a manual/bulk delete, a
data-migration bug) those public rows become ORPHANS with nothing to catch them. The
money one bites: an orphaned DELIVERED `DeliveryJob` still carries `driver_payout` and
feeds `reconcile_driver_earnings`, so a driver could be (re)paid for a delivery whose
order no longer exists.

This command scans each tenant's public refs against the `order_number`s that actually
exist in that tenant's schema and reports the orphans. It is **detect-only by default**
(mirrors `reconcile_wallet_balances`):

  • a money-carrying orphan — a `DeliveryJob` with a `driver_payout` — is escalated to the
    `payments` channel for human triage and is **NEVER auto-deleted** (deleting a
    delivery/earning record could erase a legitimate payout);
  • a `CustomerRating` orphan is reported only (authoritative trust data, not a mirror);
  • `--fix` deletes ONLY the pure-mirror `CustomerOrderRef` orphans (the customer
    cross-restaurant "My Orders" index — safe to drop; already removed on `Order`
    post_delete, so this only catches signal misses such as a bulk delete or schema drop).

    python manage.py reconcile_order_refs [--fix] [--limit 1000]

Safe to re-run; makes no money mutations. `WalletTransaction` is intentionally out of
scope — it references orders through a fuzzy free-form `reference` string, and a money
ledger must never be reconciled by deletion. Schedule on a light cadence (e.g. daily).
"""
import logging

from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context

payments_logger = logging.getLogger("payments")


class Command(BaseCommand):
    help = (
        "Detect orphaned public order-refs (DeliveryJob / CustomerOrderRef / CustomerRating) "
        "whose tenant Order no longer exists (RISK DATA-1)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix", action="store_true",
            help="Delete orphaned CustomerOrderRef mirror rows (pure denormalized index; safe). "
                 "Money/authoritative refs (DeliveryJob, CustomerRating) are NEVER auto-deleted — only reported.",
        )
        parser.add_argument(
            "--limit", type=int, default=1000,
            help="Max orphaned order_numbers to process per tenant (default 1000).",
        )

    def handle(self, *args, **options):
        from tenancy.models import Tenant
        from accounts.models import CustomerOrderRef, CustomerRating, DeliveryJob

        do_fix = options["fix"]
        limit = options["limit"]

        t = dict(tenants=0, delivery_orphans=0, money_orphans=0,
                 mirror_orphans=0, mirror_deleted=0, rating_orphans=0)

        for tenant in Tenant.objects.all():
            tid = tenant.id

            # Pass 1 (cheap — order_number strings only): every order this tenant's public
            # refs point at.
            referenced = set()
            referenced |= set(DeliveryJob.objects.filter(tenant_id=tid).values_list("order_number", flat=True))
            referenced |= set(CustomerOrderRef.objects.filter(tenant_id=tid).values_list("order_number", flat=True))
            referenced |= set(CustomerRating.objects.filter(tenant_id=tid).values_list("order_number", flat=True))
            referenced.discard("")
            referenced.discard(None)
            if not referenced:
                continue
            t["tenants"] += 1

            # Which of those orders actually exist in the tenant schema?
            try:
                with schema_context(tenant.schema_name):
                    from menu.models import Order
                    existing = set(
                        Order.objects.filter(order_number__in=referenced)
                        .values_list("order_number", flat=True)
                    )
            except Exception as exc:  # missing schema / read error — skip, don't fabricate orphans
                self.stdout.write(f"  [warn] tenant {tenant.slug}: cannot read orders ({exc}); skipping")
                continue

            orphan_ons = referenced - existing
            if not orphan_ons:
                continue
            if len(orphan_ons) > limit:
                orphan_ons = set(list(orphan_ons)[:limit])

            # Pass 2 (only orphans): classify + act.
            # DeliveryJob — money; ALERT, never delete.
            for (job_id, on, driver_id, payout, status) in DeliveryJob.objects.filter(
                tenant_id=tid, order_number__in=orphan_ons
            ).values_list("id", "order_number", "driver_id", "driver_payout", "status"):
                t["delivery_orphans"] += 1
                if payout and payout > 0:
                    t["money_orphans"] += 1
                    # order_number only — delivery earnings carry no cash-out code, so safe.
                    payments_logger.error(
                        "orphaned delivery job — order gone: job_id=%s tenant_id=%s order=%s "
                        "driver_id=%s payout=%s status=%s",
                        job_id, tid, on, driver_id, payout, status,
                    )

            # CustomerRating — authoritative trust data; report only.
            t["rating_orphans"] += CustomerRating.objects.filter(
                tenant_id=tid, order_number__in=orphan_ons
            ).count()

            # CustomerOrderRef — pure mirror; safe to drop under --fix.
            mirror_q = CustomerOrderRef.objects.filter(tenant_id=tid, order_number__in=orphan_ons)
            n_mirror = mirror_q.count()
            t["mirror_orphans"] += n_mirror
            if do_fix and n_mirror:
                mirror_q.delete()
                t["mirror_deleted"] += n_mirror

        self.stdout.write(self.style.SUCCESS(
            "reconcile_order_refs: tenants_scanned={tenants} "
            "delivery_orphans={delivery_orphans} (money={money_orphans}) "
            "mirror_orphans={mirror_orphans} mirror_deleted={mirror_deleted} "
            "rating_orphans={rating_orphans}".format(**t)
        ))
        if t["money_orphans"]:
            self.stdout.write(self.style.WARNING(
                f"{t['money_orphans']} orphaned delivery job(s) with a payout escalated to the "
                "payments channel for manual triage (NOT auto-deleted)."
            ))
