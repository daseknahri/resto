"""
Management command: send_daily_summary

Designed to run once per day (e.g. 23:30 UTC). For each ACTIVE tenant, computes
YESTERDAY's order totals in the tenant's local timezone and delivers a brief digest
to the owner via:
  - Owner web push (via accounts.tasks.web_push_tenant)
  - Owner email (plain-text, same pattern as _send_owner_new_reservation_email)
  - record_notification for audit trail

Idempotent: uses cache.add with a 2-day TTL keyed on (schema_name, date) so
re-running the same UTC day does not double-send.

Cron (Coolify / crontab) — once per day at 23:30 UTC:
    30 23 * * * cd /app && python manage.py send_daily_summary >> /var/log/daily_summary.log 2>&1

Usage:
    python manage.py send_daily_summary
    python manage.py send_daily_summary --dry-run
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone as _tz
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context

from tenancy.models import Tenant

logger = logging.getLogger(__name__)

# Cache-key prefix — changing this resets all idempotency markers.
_CACHE_PREFIX = "daily_summary_sent"
_CACHE_TTL = 60 * 60 * 24 * 2  # 2 days


def _cache_key(schema_name: str, day: date) -> str:
    return f"{_CACHE_PREFIX}:{schema_name}:{day.isoformat()}"


def _tenant_yesterday(tenant) -> tuple[datetime, datetime, date]:
    """
    Return (day_start_utc, day_end_utc, local_date) for *yesterday* in the
    tenant's configured timezone, using the same _profile_now / ZoneInfo pattern
    as menu/views.py business-hours logic.
    """
    try:
        from zoneinfo import ZoneInfo
        profile = getattr(tenant, "profile", None)
        tz_name = (getattr(profile, "timezone", "") or "").strip() or getattr(settings, "TIME_ZONE", "") or "UTC"
        tz = ZoneInfo(tz_name)
    except Exception:
        from datetime import timezone as _stdlib_tz
        tz = _stdlib_tz.utc

    now_local = datetime.now(tz)
    today_midnight = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    yesterday_midnight = today_midnight - timedelta(days=1)

    local_date = yesterday_midnight.date()
    day_start_utc = yesterday_midnight.astimezone(_tz.utc)
    day_end_utc = today_midnight.astimezone(_tz.utc)
    return day_start_utc, day_end_utc, local_date


def _compute_summary(schema_name: str, day_start_utc: datetime, day_end_utc: datetime) -> dict | None:
    """Compute yesterday's stats for a single tenant schema. Returns None if zero orders."""
    # Imported inside the function so this module loads cleanly even if Django's ORM
    # is not yet set up (e.g. during management-command import phase in tests).
    from django.db.models import Count, Sum
    from menu.models import Order, OrderItem

    paid_statuses = [
        Order.Status.COMPLETED,
        Order.Status.READY,
        Order.Status.PREPARING,
        Order.Status.CONFIRMED,
    ]

    qs = Order.objects.filter(
        created_at__gte=day_start_utc,
        created_at__lt=day_end_utc,
        status__in=paid_statuses,
    )
    agg = qs.aggregate(
        order_count=Count("id"),
        total_revenue=Sum("total"),
        wallet_revenue=Sum("wallet_amount_paid"),
    )
    order_count = agg["order_count"] or 0
    if order_count == 0:
        return None

    total_revenue = float(agg["total_revenue"] or 0)
    wallet_revenue = round(float(agg["wallet_revenue"] or 0), 2)
    cash_revenue = round(total_revenue - wallet_revenue, 2)

    # Top 3 dishes by qty
    top_dishes = list(
        OrderItem.objects
        # Voided items (wrong dish, customer refused) were not consumed —
        # excluding them keeps the top-items list honest. R5 review minor.
        .filter(order__in=qs, is_voided=False)
        .values("dish_name")
        .annotate(qty=Sum("qty"))
        .order_by("-qty")[:3]
    )

    return {
        "order_count": order_count,
        "total_revenue": round(total_revenue, 2),
        "wallet_revenue": wallet_revenue,
        "cash_revenue": cash_revenue,
        "top_dishes": top_dishes,
    }


def _send_owner_push(schema_name: str, tenant_name: str, summary: dict, local_date: date) -> None:
    """Enqueue an owner web push via the existing accounts.tasks.web_push_tenant path."""
    try:
        from accounts.tasks import enqueue, web_push_tenant
        title = f"Daily summary — {local_date.strftime('%d %b')}"
        body = (
            f"{summary['order_count']} orders · "
            f"{summary['total_revenue']:.2f} total "
            f"(wallet {summary['wallet_revenue']:.2f} / cash {summary['cash_revenue']:.2f})"
        )
        enqueue(web_push_tenant, schema_name, title, body, "/owner/dashboard")
    except Exception:
        logger.exception("send_daily_summary: push failed for %s", schema_name)


def _send_owner_email(tenant, tenant_name: str, summary: dict, local_date: date) -> None:
    """Send a plain-text digest email to the tenant owner."""
    try:
        from accounts.models import User as _User
        owner_email = (
            _User.objects
            .filter(tenant=tenant, role=_User.Roles.TENANT_OWNER)
            .values_list("email", flat=True)
            .first()
        )
        if not owner_email:
            return

        top_lines = "\n".join(
            f"  {i+1}. {row['dish_name']} × {row['qty']}"
            for i, row in enumerate(summary["top_dishes"])
        ) or "  (no items)"

        body = (
            f"Daily summary for {tenant_name} — {local_date.strftime('%A, %d %B %Y')}\n"
            f"{'=' * 50}\n"
            f"Orders:        {summary['order_count']}\n"
            f"Total revenue: {summary['total_revenue']:.2f}\n"
            f"  Wallet:      {summary['wallet_revenue']:.2f}\n"
            f"  Cash:        {summary['cash_revenue']:.2f}\n"
            f"\nTop items:\n{top_lines}\n"
            f"\n— Kepoli"
        )
        send_mail(
            subject=f"Daily summary — {tenant_name} ({local_date.strftime('%d %b')})",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner_email],
            fail_silently=getattr(settings, "EMAIL_FAIL_SILENTLY", True),
        )

        from accounts.notifications import record_notification
        record_notification(
            channel="email", event="daily_summary", status="sent",
            recipient=owner_email, detail=tenant_name,
            reference=local_date.isoformat(), tenant_id=getattr(tenant, "id", None),
        )
    except Exception:
        logger.exception("send_daily_summary: email failed for %s", getattr(tenant, "slug", "?"))


class Command(BaseCommand):
    help = "Send a daily end-of-day summary (orders, revenue, cash/wallet split, top dishes) to each active tenant owner."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be sent without actually sending or setting idempotency markers.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "Daily summary" + (" [DRY RUN]" if dry_run else "")
            )
        )

        tenants = Tenant.objects.filter(
            is_active=True,
            lifecycle_status=Tenant.LifecycleStatus.ACTIVE,
        ).exclude(schema_name="public")

        total_sent = 0
        total_skipped_zero = 0
        total_skipped_duplicate = 0

        for tenant in tenants:
            try:
                day_start_utc, day_end_utc, local_date = _tenant_yesterday(tenant)
                cache_key = _cache_key(tenant.schema_name, local_date)

                # Idempotency check (skip if already sent today for this tenant/date)
                if not dry_run and not cache.add(cache_key, "1", _CACHE_TTL):
                    self.stdout.write(
                        f"  {tenant.slug}: already sent for {local_date} — skipping"
                    )
                    total_skipped_duplicate += 1
                    continue

                with schema_context(tenant.schema_name):
                    summary = _compute_summary(tenant.schema_name, day_start_utc, day_end_utc)

                if summary is None:
                    self.stdout.write(f"  {tenant.slug}: 0 orders — skipping")
                    # Clear the cache key so a re-run on a non-zero day isn't blocked
                    if not dry_run:
                        cache.delete(cache_key)
                    total_skipped_zero += 1
                    continue

                tenant_name = getattr(tenant, "name", "") or tenant.slug
                self.stdout.write(
                    f"  {tenant.slug} ({local_date}): "
                    f"{summary['order_count']} orders / "
                    f"{summary['total_revenue']:.2f} total "
                    f"(wallet {summary['wallet_revenue']:.2f} cash {summary['cash_revenue']:.2f})"
                )
                if summary["top_dishes"]:
                    for row in summary["top_dishes"]:
                        self.stdout.write(f"      - {row['dish_name']} × {row['qty']}")

                if dry_run:
                    continue

                # Deliver
                with schema_context(tenant.schema_name):
                    _send_owner_push(tenant.schema_name, tenant_name, summary, local_date)
                    _send_owner_email(tenant, tenant_name, summary, local_date)

                total_sent += 1

            except Exception:
                logger.exception("send_daily_summary: error processing tenant %s", tenant.slug)

        label = "would send" if dry_run else "sent"
        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {total_sent} digest(s) {label}, "
                f"{total_skipped_zero} tenant(s) had zero orders, "
                f"{total_skipped_duplicate} already-sent (idempotent) skips."
            )
        )
