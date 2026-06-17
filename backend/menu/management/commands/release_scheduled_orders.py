"""
Management command: release_scheduled_orders

Designed to run on a cron schedule (every ~5 minutes). Finds advance/scheduled
orders (status=SCHEDULED) whose requested fulfilment time is now within the
release lead window, and moves them into the live kitchen flow as PENDING —
firing the same "new order" notifications a fresh order would (web push to
owner/staff, a realtime ping, a platform delivery job for delivery orders, and
a best-effort WhatsApp to the restaurant).

Because the transition is SCHEDULED → PENDING, an order can only be released
once: the next run won't match it again, so this is naturally idempotent.

Cron (Coolify / crontab) — every 5 minutes:
    */5 * * * * cd /app && python manage.py release_scheduled_orders >> /var/log/release_scheduled_orders.log 2>&1

Usage:
    python manage.py release_scheduled_orders
    python manage.py release_scheduled_orders --dry-run
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django_tenants.utils import schema_context

from tenancy.models import Tenant

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Release advance/scheduled orders into the live kitchen flow as their time approaches."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List what would be released without changing the DB or notifying.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        now = timezone.now()

        # Imported here so the module loads even if optional deps are missing, and to
        # share the single source of truth for the lead window + helpers.
        from menu.models import Order
        from menu.views import (
            _SCHEDULE_RELEASE_LEAD_MINUTES,
            _broadcast_order_change,
            _notify_restaurant_new_order,
        )

        release_by = now + timedelta(minutes=_SCHEDULE_RELEASE_LEAD_MINUTES)

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Releasing scheduled orders due by {release_by.strftime('%Y-%m-%d %H:%M')} UTC"
                + (" [DRY RUN]" if dry_run else "")
            )
        )

        tenants = Tenant.objects.filter(
            is_active=True,
            lifecycle_status=Tenant.LifecycleStatus.ACTIVE,
        ).exclude(schema_name="public")

        total_released = 0

        for tenant in tenants:
            try:
                with schema_context(tenant.schema_name):
                    due = list(
                        Order.objects
                        .filter(
                            status=Order.Status.SCHEDULED,
                            scheduled_for__isnull=False,
                            scheduled_for__lte=release_by,
                        )
                        .order_by("scheduled_for")[:200]
                    )

                    for order in due:
                        self.stdout.write(
                            f"  → {tenant.slug} | {order.order_number} "
                            f"(scheduled {order.scheduled_for:%Y-%m-%d %H:%M})"
                        )
                        if dry_run:
                            continue

                        order.status = Order.Status.PENDING
                        order.status_updated_at = timezone.now()
                        order.save(update_fields=["status", "status_updated_at", "updated_at"])
                        total_released += 1

                        # Live ping to the customer's tracking page + owner/kitchen sockets.
                        try:
                            _broadcast_order_change(order)
                        except Exception:
                            logger.exception("release: broadcast failed for %s", order.order_number)

                        # Web push to subscribed owner/staff (the kitchen alert).
                        try:
                            from menu.push import push_new_order as _push_new_order
                            _push_new_order(
                                schema_name=tenant.schema_name,
                                order_number=order.order_number,
                                customer_name=order.customer_name or "",
                                total=str(order.total),
                                currency=order.currency,
                            )
                        except Exception:
                            logger.exception("release: web push failed for %s", order.order_number)

                        # Platform delivery: spawn the searching driver job now (opt-in).
                        profile = getattr(tenant, "profile", None)
                        if (
                            order.fulfillment_type == Order.FulfillmentType.DELIVERY
                            and profile is not None
                            and getattr(profile, "platform_delivery_enabled", False)
                        ):
                            try:
                                from accounts.models import DeliveryJob as _DJob
                                from tenancy.delivery_pricing import split_delivery_fee as _split_fee
                                # Split fee into driver payout + platform cut (default 0%).
                                _dsplit = _split_fee(profile, order.delivery_fee)
                                _job = _DJob.objects.create(
                                    tenant_id=tenant.id,
                                    order_number=order.order_number,
                                    status=_DJob.Status.SEARCHING,
                                    pickup_address=(getattr(profile, "address", "") or "")[:200],
                                    pickup_lat=getattr(profile, "lat", None),
                                    pickup_lng=getattr(profile, "lng", None),
                                    delivery_address=(order.delivery_address or "")[:200],
                                    delivery_lat=order.delivery_lat,
                                    delivery_lng=order.delivery_lng,
                                    delivery_fee=order.delivery_fee,
                                    driver_payout=_dsplit["driver_payout"],
                                    platform_commission=_dsplit["platform_commission"],
                                    delivery_commission_rate_applied=_dsplit["commission_pct"],
                                    business_type=getattr(profile, "business_type", "restaurant") or "restaurant",
                                )
                                from accounts.dispatch import start_dispatch
                                start_dispatch(_job)
                            except Exception:
                                logger.exception("release: delivery job failed for %s", order.order_number)

                        # Best-effort WhatsApp to the restaurant (synchronous — small batch).
                        _wa = ""
                        if profile is not None:
                            _wa = (getattr(profile, "whatsapp", "") or getattr(profile, "phone", "") or "").strip()
                        if _wa:
                            try:
                                _notify_restaurant_new_order(
                                    order,
                                    tenant_name=getattr(tenant, "name", "") or tenant.slug,
                                    whatsapp_phone=_wa,
                                    tenant_id=tenant.id,
                                )
                            except Exception:
                                logger.exception("release: WhatsApp failed for %s", order.order_number)
            except Exception:
                logger.exception("release_scheduled_orders: error processing tenant %s", tenant.slug)

        label = "would release" if dry_run else "released"
        self.stdout.write(self.style.SUCCESS(f"\nDone. {total_released} order(s) {label}."))
