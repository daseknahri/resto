"""
Management command: send_predispatch_reminders

Designed to run on a cron schedule (every ~15 minutes). Finds advance/scheduled
orders (status=SCHEDULED) whose scheduled_for time is between 55 and 90 minutes
from now — well before the 45-min kitchen-release window — that have NOT yet
received a pre-dispatch reminder, and sends each customer a Web Push letting them
know their order is coming up soon.

Because the transition window is checked against ``predispatch_reminder_sent_at IS NULL``
and the field is stamped on first send, this is naturally idempotent: a missed run
broadens the window; a duplicate run skips already-stamped orders.

Cron (Coolify / crontab) — every 15 minutes:
    */15 * * * * cd /app && python manage.py send_predispatch_reminders >> /var/log/predispatch_reminders.log 2>&1

Usage:
    python manage.py send_predispatch_reminders
    python manage.py send_predispatch_reminders --dry-run
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django_tenants.utils import schema_context

from tenancy.models import Tenant

logger = logging.getLogger(__name__)

# Send the reminder when scheduled_for is inside this window from now.
# Lower bound (55 min): far enough ahead of the 45-min release so the customer
#   gets the nudge before the kitchen starts working on it.
# Upper bound (90 min): safety net — if a run was missed, we still catch it on
#   the next run as long as it's within the wider window.
WINDOW_MIN_MINUTES = 55
WINDOW_MAX_MINUTES = 90


class Command(BaseCommand):
    help = "Send a pre-dispatch reminder push to customers ~60 min before their scheduled order time."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List what would be sent without sending or stamping the DB.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        now = timezone.now()
        window_start = now + timedelta(minutes=WINDOW_MIN_MINUTES)
        window_end = now + timedelta(minutes=WINDOW_MAX_MINUTES)

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Pre-dispatch reminders — scheduled_for between "
                f"{window_start.strftime('%H:%M')} and {window_end.strftime('%H:%M')} UTC"
                + (" [DRY RUN]" if dry_run else "")
            )
        )

        from menu.models import Order
        from accounts.push import send_predispatch_reminder_sync

        tenants = Tenant.objects.filter(
            is_active=True,
            lifecycle_status=Tenant.LifecycleStatus.ACTIVE,
        ).exclude(schema_name="public")

        total_sent = 0
        total_processed = 0

        for tenant in tenants:
            try:
                with schema_context(tenant.schema_name):
                    eligible = list(
                        Order.objects
                        .filter(
                            status=Order.Status.SCHEDULED,
                            scheduled_for__gte=window_start,
                            scheduled_for__lte=window_end,
                            predispatch_reminder_sent_at__isnull=True,
                            customer_id__isnull=False,
                        )
                        .only("id", "order_number", "customer_id", "scheduled_for")[:200]
                    )

                    for order in eligible:
                        self.stdout.write(
                            f"  → {tenant.slug} | {order.order_number} "
                            f"(scheduled {order.scheduled_for:%Y-%m-%d %H:%M}, customer {order.customer_id})"
                        )
                        if dry_run:
                            continue

                        try:
                            sent = send_predispatch_reminder_sync(
                                order.customer_id,
                                tenant.name or tenant.slug,
                                order.order_number,
                            )
                            total_sent += sent
                        except Exception:
                            logger.exception(
                                "predispatch push failed for order %s (tenant %s)",
                                order.order_number, tenant.slug,
                            )

                        # Stamp regardless of delivery so we never double-nudge
                        # this order on the next run.
                        order.predispatch_reminder_sent_at = timezone.now()
                        order.save(update_fields=["predispatch_reminder_sent_at", "updated_at"])
                        total_processed += 1
            except Exception:
                logger.exception("send_predispatch_reminders: error processing tenant %s", tenant.slug)

        label = "would notify" if dry_run else "processed"
        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {total_processed} order(s) {label}, {total_sent} push(es) delivered."
            )
        )
