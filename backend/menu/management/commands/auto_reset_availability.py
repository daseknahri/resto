"""
Management command: auto_reset_availability

Runs hourly (via Celery Beat). For each ACTIVE tenant that has
``Profile.auto_reset_availability = True``, checks whether the tenant's current
local hour is 5 (i.e. ~05:00) and, if a per-(tenant, date) cache marker is not
yet set, runs the morning reset: all published sold-out dishes are re-enabled,
and auto-zeroed stock counts are cleared.

Idempotent: uses cache.add with a 2-day TTL so re-running the same UTC hour
never double-resets.

Beat entry (add to CELERY_BEAT_SCHEDULE in settings.py):

    "auto-reset-availability": {
        "task": "cron.auto_reset_availability",
        "schedule": 3600.0,  # hourly
    },

LAUNCH_CHECKLIST:
  - [ ] Beat entry "auto-reset-availability" added to CELERY_BEAT_SCHEDULE
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context

from tenancy.models import Tenant

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "auto_reset_avail"
_CACHE_TTL = 60 * 60 * 24 * 2  # 2 days
_RESET_HOUR = 5  # local time hour to trigger the reset


def _cache_key(schema_name: str, day_str: str) -> str:
    return f"{_CACHE_PREFIX}:{schema_name}:{day_str}"


def _tenant_local_hour(tenant) -> tuple[int, str]:
    """Return (local_hour int, local_date_str 'YYYY-MM-DD') for the tenant's timezone."""
    try:
        profile = getattr(tenant, "profile", None)
        tz_name = (getattr(profile, "timezone", "") or "").strip() or getattr(settings, "TIME_ZONE", "") or "UTC"
        tz = ZoneInfo(tz_name)
    except Exception:
        from datetime import timezone as _stdlib_tz
        tz = _stdlib_tz.utc
    now_local = datetime.now(tz)
    return now_local.hour, now_local.date().isoformat()


def reset_dishes_for_schema() -> dict:
    """Re-enable sold-out published dishes that were auto-zeroed by checkout.

    Only touches dishes where stock_auto_zeroed=True (set by the checkout
    decrement logic) so that owner-deliberately-zeroed dishes are left alone.
    The re-enable clears the marker and also resets stock_qty=0 → None so the
    dish is fully available again (unlimited until the next order).

    Returns {"restored": int, "stock_cleared": int}.
    """
    from menu.models import Dish

    # Re-enable only dishes the checkout auto-zeroed; clear the marker and
    # reset stock_qty to None so the dish has unlimited stock again.
    # Both is_available=False and is_available=True dishes with stock_auto_zeroed
    # may exist (e.g. if someone manually re-enabled the dish but didn't adjust
    # stock_qty), so we filter on stock_auto_zeroed=True regardless of
    # is_available to handle the stock_qty cleanup too.
    target_qs = Dish.objects.filter(is_published=True, stock_auto_zeroed=True)

    # Restore availability for those that are still sold-out.
    restored = target_qs.filter(is_available=False).update(
        is_available=True, stock_qty=None, stock_auto_zeroed=False
    )

    # Clear the marker (and reset stock_qty) for any already-available ones
    # that still carry the flag (e.g. owner manually re-enabled mid-day).
    stock_cleared = target_qs.filter(is_available=True).update(
        stock_qty=None, stock_auto_zeroed=False
    )

    return {"restored": restored, "stock_cleared": stock_cleared}


class Command(BaseCommand):
    help = (
        "Hourly: re-enable all sold-out dishes at ~05:00 local time for tenants "
        "that have Profile.auto_reset_availability enabled."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be reset without changing the DB or setting cache markers.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "auto_reset_availability" + (" [DRY RUN]" if dry_run else "")
            )
        )

        tenants = Tenant.objects.filter(
            is_active=True,
            lifecycle_status=Tenant.LifecycleStatus.ACTIVE,
        ).exclude(schema_name="public").select_related("profile")

        total_reset = 0
        total_skipped_hour = 0
        total_skipped_flag = 0
        total_skipped_marker = 0

        for tenant in tenants:
            try:
                profile = getattr(tenant, "profile", None)
                if not profile or not profile.auto_reset_availability:
                    total_skipped_flag += 1
                    continue

                local_hour, day_str = _tenant_local_hour(tenant)
                if local_hour != _RESET_HOUR:
                    total_skipped_hour += 1
                    continue

                cache_key = _cache_key(tenant.schema_name, day_str)

                if not dry_run and not cache.add(cache_key, "1", _CACHE_TTL):
                    self.stdout.write(
                        f"  {tenant.slug}: already reset for {day_str} — skipping"
                    )
                    total_skipped_marker += 1
                    continue

                if dry_run:
                    self.stdout.write(
                        f"  {tenant.slug} ({day_str} local hour={local_hour}): would reset"
                    )
                    continue

                with schema_context(tenant.schema_name):
                    result = reset_dishes_for_schema()

                self.stdout.write(
                    f"  {tenant.slug} ({day_str}): "
                    f"restored={result['restored']} stock_cleared={result['stock_cleared']}"
                )
                total_reset += 1

            except Exception:
                logger.exception(
                    "auto_reset_availability: error processing tenant %s", tenant.slug
                )

        label = "would reset" if dry_run else "reset"
        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {total_reset} tenant(s) {label}, "
                f"{total_skipped_hour} not at hour {_RESET_HOUR}, "
                f"{total_skipped_flag} flag-off, "
                f"{total_skipped_marker} already-reset (idempotent) skips."
            )
        )
