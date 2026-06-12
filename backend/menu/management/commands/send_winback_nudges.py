"""
Management command: send_winback_nudges

Hourly sweep (via Celery Beat). For each ACTIVE tenant that has
``Profile.winback_enabled = True``, checks whether the tenant's current local
hour is 11 (pre-lunch) and, if a per-(tenant, date) cache marker is not yet
set, finds lapsed customers and delivers ONE push reminder per qualifying
customer — at most once every 90 days (enforced durably in accounts.WinbackNudge).

Idempotent per-run: uses cache.add with a 2-day TTL keyed on (tenant_id, date)
so re-running the same UTC hour never double-processes.

Audience:
  - Has at least one Order in this tenant.
  - Most recent order is older than profile.winback_inactive_weeks weeks.
  - Customer.notify_promotions is True (re-checked at send time).
  - Has at least one CustomerPushSubscription.
  - No WinbackNudge row for this (tenant, customer) within the last 90 days.

Cap: max 50 nudges per tenant per run; remainder will be picked up on subsequent
eligible days (nudge clock starts fresh after 90 days).

Beat entry (settings.py):
    "send-winback-nudges": {
        "task": "accounts.tasks.run_management_command",
        "schedule": 3600.0,  # hourly
        "args": ("send_winback_nudges",),
    },
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone as _tz
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context

from tenancy.models import Tenant

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "winback"
_CACHE_TTL = 60 * 60 * 24 * 2  # 2 days
_SEND_HOUR = 11                  # tenant-local hour to fire
_DEDUPE_DAYS = 90                # durable 90-day cooldown per (tenant, customer)
_CAP_PER_RUN = 50                # max nudges per tenant per run


def _cache_key(tenant_id: int, day_str: str) -> str:
    return f"{_CACHE_PREFIX}:{tenant_id}:{day_str}"


def _tenant_local_hour(tenant) -> tuple[int, str]:
    """Return (local_hour int, local_date_str 'YYYY-MM-DD') in the tenant's timezone."""
    try:
        profile = getattr(tenant, "profile", None)
        tz_name = (getattr(profile, "timezone", "") or "").strip() or getattr(settings, "TIME_ZONE", "") or "UTC"
        tz = ZoneInfo(tz_name)
    except Exception:
        from datetime import timezone as _stdlib_tz
        tz = _stdlib_tz.utc
    now_local = datetime.now(tz)
    return now_local.hour, now_local.date().isoformat()


def _already_nudged(tenant_id: int, customer_id: int) -> bool:
    """Return True if a WinbackNudge row exists for this (tenant, customer) within 90 days."""
    from accounts.models import WinbackNudge
    cutoff = datetime.now(_tz.utc) - timedelta(days=_DEDUPE_DAYS)
    return WinbackNudge.objects.filter(
        tenant_id=tenant_id,
        customer_id=customer_id,
        sent_at__gte=cutoff,
    ).exists()


def _record_nudge(tenant_id: int, customer_id: int) -> None:
    """Write a WinbackNudge row (public schema)."""
    from accounts.models import WinbackNudge
    WinbackNudge.objects.create(tenant_id=tenant_id, customer_id=customer_id)


def _build_audience(tenant_id: int, inactive_weeks: int, cap: int) -> list[int]:
    """
    Return up to ``cap`` customer_ids who:
      - ordered at least once in this tenant
      - most recent order older than inactive_weeks weeks
      - notify_promotions = True
      - have an active CustomerPushSubscription
      - not already nudged within 90 days

    MUST be called from INSIDE schema_context(tenant.schema_name) for the
    Order query; the public-schema queries switch context internally.
    """
    from django.db.models import Max
    from menu.models import Order

    cutoff = datetime.now(_tz.utc) - timedelta(weeks=inactive_weeks)

    # Step 1: customer_ids with an order in this tenant, latest order older than cutoff.
    qs = (
        Order.objects
        .values("customer_id")
        .annotate(last_order=Max("created_at"))
        .filter(customer_id__isnull=False, last_order__lt=cutoff)
    )
    inactive_ids = set(row["customer_id"] for row in qs)
    if not inactive_ids:
        return []

    with schema_context("public"):
        from accounts.models import Customer, CustomerPushSubscription

        # Step 2: opted-in customers only.
        opted_in = set(
            Customer.objects.filter(
                id__in=inactive_ids,
                notify_promotions=True,
            ).values_list("id", flat=True)
        )
        if not opted_in:
            return []

        # Step 3: has at least one push subscription.
        subscribed = set(
            CustomerPushSubscription.objects.filter(
                customer_id__in=opted_in,
            ).values_list("customer_id", flat=True).distinct()
        )
        if not subscribed:
            return []

    # Step 4: not nudged within 90 days — ONE batched query instead of one
    # EXISTS per customer.  _already_nudged is kept for external callers.
    from accounts.models import WinbackNudge
    cutoff = datetime.now(_tz.utc) - timedelta(days=_DEDUPE_DAYS)
    with schema_context("public"):
        recently_nudged = set(
            WinbackNudge.objects.filter(
                tenant_id=tenant_id,
                customer_id__in=subscribed,
                sent_at__gte=cutoff,
            ).values_list("customer_id", flat=True)
        )

    # Sort the set for deterministic iteration order so the capped slice is
    # stable across calls (avoids misleading remaining-count logs).
    eligible = [cid for cid in sorted(subscribed) if cid not in recently_nudged][:cap]

    return eligible


def _send_nudge(customer_id: int, tenant_name: str, slug: str, push_url: str, title: str, body: str) -> int:
    """Send one winback push synchronously. Mirrors campaign_push path.

    Returns the number of push notifications delivered (0 means suppressed or
    all endpoints gone). Never raises — exceptions are logged and 0 is returned.
    """
    from accounts.push import send_campaign_push_sync
    try:
        return send_campaign_push_sync(customer_id, tenant_name, title, body, push_url)
    except Exception:
        logger.exception("send_winback_nudges: push failed for customer %s at %s", customer_id, slug)
        return 0


class Command(BaseCommand):
    help = (
        "Hourly sweep: send a win-back push reminder to lapsed customers "
        "for tenants that have Profile.winback_enabled=True. "
        "Sends at tenant-local hour 11 (pre-lunch), at most once per customer per 90 days."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be sent without touching the DB, cache, or push subscriptions.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "send_winback_nudges" + (" [DRY RUN]" if dry_run else "")
            )
        )

        tenants = Tenant.objects.filter(
            is_active=True,
            lifecycle_status=Tenant.LifecycleStatus.ACTIVE,
        ).exclude(schema_name="public").select_related("profile")

        total_sent = 0
        total_skipped_flag = 0
        total_skipped_hour = 0
        total_skipped_marker = 0
        total_capped = 0

        for tenant in tenants:
            try:
                profile = getattr(tenant, "profile", None)
                if not profile or not profile.winback_enabled:
                    total_skipped_flag += 1
                    continue

                local_hour, day_str = _tenant_local_hour(tenant)
                if local_hour != _SEND_HOUR:
                    total_skipped_hour += 1
                    continue

                _raw_weeks = profile.winback_inactive_weeks
                if isinstance(_raw_weeks, int) and _raw_weeks > 0:
                    inactive_weeks = _raw_weeks
                else:
                    if _raw_weeks is not None:
                        logger.warning(
                            "send_winback_nudges: tenant %s has non-positive "
                            "winback_inactive_weeks=%r — defaulting to 4",
                            tenant.slug, _raw_weeks,
                        )
                    inactive_weeks = 4
                tenant_name = getattr(tenant, "name", "") or tenant.slug

                # Build audience inside the tenant schema.
                with schema_context(tenant.schema_name):
                    audience = _build_audience(tenant.id, inactive_weeks, _CAP_PER_RUN)

                if not audience:
                    self.stdout.write(f"  {tenant.slug} ({day_str}): no eligible customers")
                    continue

                # Derive the remaining-capped count from the audience size alone,
                # without a second _build_audience call.  The audience is capped at
                # _CAP_PER_RUN; if it hit the cap we know at least that many were
                # deferred (the true overflow is unknown without a full scan, so we
                # report the minimum: 1+ deferred when the cap was reached).
                hit_cap = len(audience) >= _CAP_PER_RUN
                if hit_cap:
                    total_capped += 1  # at least one customer deferred; exact count unknowable without re-scan

                # Build push content. Deep link MUST match the manual campaign
                # format (menu/views.py campaign dispatch): a relative
                # marketplace path on the platform domain — NOT a hardcoded
                # subdomain that may not exist in the deployment.
                push_url = f"/order/{tenant.slug}"
                custom_msg = (profile.winback_message or "").strip()
                title = f"We miss you at {tenant_name}!"
                body = custom_msg or f"It's been a while — come back and order from {tenant_name}. We'd love to see you again!"

                self.stdout.write(
                    f"  {tenant.slug} ({day_str}): {len(audience)} nudge(s) to send"
                    + (" (cap reached, more customers deferred)" if hit_cap else "")
                )

                if dry_run:
                    continue

                # Daily idempotency — cache.add returns False if key already exists.
                # Placed AFTER audience build and BEFORE the send loop so:
                #   - We only claim the day when there is actually work to do.
                #   - A process crash after cache.add but before sends on a zero-
                #     audience tenant is harmless (nothing to send anyway).
                #   - The 90-day DB dedupe (WinbackNudge) remains the primary
                #     spam guard; this cache key is a performance optimisation to
                #     avoid re-scanning the audience on every hourly tick.
                cache_key = _cache_key(tenant.id, day_str)
                if not cache.add(cache_key, "1", _CACHE_TTL):
                    self.stdout.write(
                        f"  {tenant.slug}: already run for {day_str} — skipping"
                    )
                    total_skipped_marker += 1
                    continue

                # Send loop.
                # Ordering guarantee (spam safety):
                #   1. Write the WinbackNudge row FIRST — so if the process dies
                #      between the DB write and the push delivery, the customer is
                #      protected from a re-send on the next run (a missed nudge is
                #      preferable to a duplicate nudge).
                #   2. Call _send_nudge.  If the push is suppressed at send time
                #      (e.g. customer opted out between audience build and now),
                #      _send_nudge returns 0 and we delete the pre-written nudge
                #      row so the 90-day dedupe slot is not burned for an
                #      undelivered message.
                delivered = 0
                for cid in audience:
                    with schema_context("public"):
                        _record_nudge(tenant.id, cid)

                    sent_count = _send_nudge(cid, tenant_name, tenant.slug, push_url, title, body)

                    if sent_count == 0:
                        # Push was suppressed (opt-out re-check) or all endpoints
                        # are gone.  Reclaim the dedupe slot.
                        # NOTE: sliced querysets cannot .delete() in Django —
                        # fetch the row then delete it.
                        try:
                            from accounts.models import WinbackNudge
                            with schema_context("public"):
                                row = WinbackNudge.objects.filter(
                                    tenant_id=tenant.id,
                                    customer_id=cid,
                                ).order_by("-sent_at").first()
                                if row is not None:
                                    row.delete()
                        except Exception:
                            logger.exception(
                                "send_winback_nudges: could not reclaim nudge row for customer %s at %s",
                                cid, tenant.slug,
                            )
                    else:
                        delivered += 1
                        # Instrument with record_notification (one row per delivered nudge).
                        try:
                            from accounts.notifications import record_notification
                            record_notification(
                                channel="push",
                                event="winback",
                                status="sent",
                                recipient=str(cid),
                                detail=tenant_name,
                                tenant_id=tenant.id,
                            )
                        except Exception:
                            pass  # best-effort

                total_sent += delivered

            except Exception:
                logger.exception("send_winback_nudges: error processing tenant %s", tenant.slug)

        label = "would send" if dry_run else "sent"
        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {total_sent} nudge(s) {label}, "
                f"{total_skipped_hour} not at hour {_SEND_HOUR}, "
                f"{total_skipped_flag} winback-disabled, "
                f"{total_skipped_marker} already-run (idempotent) skips, "
                f"{total_capped} tenant(s) with deferred customers (cap reached)."
            )
        )
