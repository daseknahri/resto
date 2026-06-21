"""
Management command: escalate_stale_pending_orders

Designed to run on a cron schedule (every ~few minutes). A server-side safety net
so a missed order is caught even when the owner isn't looking at the dashboard.

Finds orders still PENDING (placed but not yet confirmed by the restaurant) for
longer than the tenant's ``Profile.pending_sla_minutes`` (a sensible platform
default applies when unset) and sends an escalation Web Push to the subscribed
owner/manager devices — "Order #N has been waiting X min — confirm it" —
deep-linking to OwnerOrders filtered to that order (``?q=order_number``).

Idempotency: each order is stamped with ``Order.sla_notified_at`` on first
escalation and the query excludes already-stamped rows, so every stale order
escalates at most once. A missed run simply widens the lookback; a duplicate run
skips already-stamped orders.

Cron (Coolify / crontab) — every 3 minutes:
    */3 * * * * cd /app && python manage.py escalate_stale_pending_orders >> /var/log/escalate_stale_pending_orders.log 2>&1

Usage:
    python manage.py escalate_stale_pending_orders
    python manage.py escalate_stale_pending_orders --dry-run
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django_tenants.utils import schema_context

from tenancy.models import Tenant

logger = logging.getLogger(__name__)

# Platform default used when a tenant has not set Profile.pending_sla_minutes.
DEFAULT_PENDING_SLA_MINUTES = 10

# Hard lower bound so a misconfigured 0 can't escalate orders the instant they
# land (which would fire on every fresh order). Clamp the effective SLA to this.
MIN_PENDING_SLA_MINUTES = 1


class Command(BaseCommand):
    help = (
        "Escalate stale PENDING orders: push the owner when an order has waited "
        "longer than Profile.pending_sla_minutes without being confirmed."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List what would be escalated without pushing or stamping the DB.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        now = timezone.now()

        from menu.models import Order
        from menu.push import push_sla_escalation

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "Escalating stale pending orders"
                + (" [DRY RUN]" if dry_run else "")
            )
        )

        tenants = Tenant.objects.filter(
            is_active=True,
            lifecycle_status=Tenant.LifecycleStatus.ACTIVE,
        ).exclude(schema_name="public")

        total_escalated = 0

        for tenant in tenants:
            try:
                profile = getattr(tenant, "profile", None)
                configured = getattr(profile, "pending_sla_minutes", None) if profile is not None else None
                sla_minutes = configured if configured else DEFAULT_PENDING_SLA_MINUTES
                if sla_minutes < MIN_PENDING_SLA_MINUTES:
                    sla_minutes = MIN_PENDING_SLA_MINUTES

                cutoff = now - timedelta(minutes=sla_minutes)

                with schema_context(tenant.schema_name):
                    stale = list(
                        Order.objects
                        .filter(
                            status=Order.Status.PENDING,
                            sla_notified_at__isnull=True,
                            created_at__lte=cutoff,
                        )
                        .only("id", "order_number", "created_at")
                        .order_by("created_at")[:200]
                    )

                    for order in stale:
                        waited_minutes = int((now - order.created_at).total_seconds() // 60)
                        self.stdout.write(
                            f"  → {tenant.slug} | {order.order_number} "
                            f"(waiting {waited_minutes} min, SLA {sla_minutes} min)"
                        )
                        if dry_run:
                            continue

                        try:
                            push_sla_escalation(
                                schema_name=tenant.schema_name,
                                order_number=order.order_number,
                                waited_minutes=waited_minutes,
                            )
                        except Exception:
                            logger.exception(
                                "sla escalation push failed for order %s (tenant %s)",
                                order.order_number, tenant.slug,
                            )

                        # Stamp regardless of push outcome so we never double-escalate
                        # this order on the next run.
                        order.sla_notified_at = timezone.now()
                        order.save(update_fields=["sla_notified_at", "updated_at"])
                        total_escalated += 1
            except Exception:
                logger.exception(
                    "escalate_stale_pending_orders: error processing tenant %s", tenant.slug
                )

        label = "would escalate" if dry_run else "escalated"
        self.stdout.write(
            self.style.SUCCESS(f"\nDone. {total_escalated} order(s) {label}.")
        )
