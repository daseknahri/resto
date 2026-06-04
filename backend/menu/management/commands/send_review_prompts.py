"""
Management command: send_review_prompts

Designed to run on a cron schedule (every ~10 minutes). Finds orders that were
completed roughly 30 minutes ago, have a linked customer, have NOT yet been
rated, and have NOT yet been nudged, then sends each customer a Web Push
inviting them to rate the order — and stamps ``review_prompt_sent_at`` so a
customer is never nudged twice for the same order.

Why ~30 min after completion: the customer has had time to eat / get home, so
the review reflects the real experience rather than firing the instant the
kitchen marks the order done.

Cron (Coolify / crontab) — every 10 minutes:
    */10 * * * * cd /app && python manage.py send_review_prompts >> /var/log/review_prompts.log 2>&1

Usage:
    python manage.py send_review_prompts
    python manage.py send_review_prompts --dry-run
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django_tenants.utils import schema_context

from tenancy.models import Tenant

logger = logging.getLogger(__name__)

# Nudge orders completed within this age window (minutes ago).
WINDOW_MIN_AGE = 25   # don't nudge sooner than this (let them settle in)
WINDOW_MAX_AGE = 90   # don't nudge older than this — safety net if a run was missed


class Command(BaseCommand):
    help = "Send a post-order review nudge to customers ~30 min after their order completes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List what would be sent without sending or stamping the DB.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        now = timezone.now()
        oldest = now - timedelta(minutes=WINDOW_MAX_AGE)
        newest = now - timedelta(minutes=WINDOW_MIN_AGE)

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Review prompts — orders completed between "
                f"{oldest.strftime('%H:%M')} and {newest.strftime('%H:%M')} UTC"
                + (" [DRY RUN]" if dry_run else "")
            )
        )

        # Imported here so the module loads even if optional deps are missing.
        from menu.models import Order
        from accounts.push import send_review_request_sync

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
                            status=Order.Status.COMPLETED,
                            status_updated_at__gte=oldest,
                            status_updated_at__lte=newest,
                            review_prompt_sent_at__isnull=True,
                            customer_id__isnull=False,
                            rating__isnull=True,  # don't nudge if they already rated
                        )
                        .only("id", "order_number", "customer_id")[:200]
                    )

                    for order in eligible:
                        self.stdout.write(
                            f"  → {tenant.slug} | {order.order_number} (customer {order.customer_id})"
                        )
                        if dry_run:
                            continue

                        try:
                            sent = send_review_request_sync(
                                order.customer_id,
                                tenant.name or tenant.slug,
                                order.order_number,
                            )
                            total_sent += sent
                        except Exception:
                            logger.exception(
                                "review push failed for order %s (tenant %s)",
                                order.order_number, tenant.slug,
                            )

                        # Stamp regardless of delivery so we never double-nudge
                        # this order on the next run.
                        order.review_prompt_sent_at = timezone.now()
                        order.save(update_fields=["review_prompt_sent_at", "updated_at"])
                        total_processed += 1
            except Exception:
                logger.exception("send_review_prompts: error processing tenant %s", tenant.slug)

        label = "would notify" if dry_run else "processed"
        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {total_processed} order(s) {label}, {total_sent} push(es) delivered."
            )
        )
