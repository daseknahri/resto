"""Recover stuck ride requests — the safety net + heartbeat for the dispatch loop.

Idempotent; runs every ~120s (Beat or a Coolify scheduled task) so trip offers
stay live between driver polls:

    python manage.py sweep_ride_requests

Rules (policy: re-dispatch, auto-cancel only on timeout, never touch in_progress):
  (d) SCHEDULED with scheduled_for <= now+10min: atomic select_for_update re-check,
      flip to SEARCHING, set dispatched_at=now(), then kind-aware driver push.
      This is evaluated FIRST so a just-released trip never hits rules (a)/(b).
  (a) SEARCHING > 3 min  → re-push (throttled, ~110s cache key so re-push fires at most
      once per sweep cycle).  push_new_ride_to_drivers branches on kind internally:
        ride    → car drivers with car_approved.
        package → all approved online drivers.
      Window uses dispatched_at (when the trip entered SEARCHING pool). Pre-0038 rows
      have dispatched_at=None; they fall back to created_at via an OR filter so they
      are still handled correctly.
  (b) SEARCHING > 15 min → auto-cancel (status CANCELLED + cancelled_at) + web-push
      rider "no driver found". select_for_update + re-check inside atomic.
      Window uses dispatched_at with the same pre-0038 fallback as rule (a).
  (c) ACCEPTED or ARRIVED (pre-passenger; NEVER touch in_progress) whose driver
      is_driver_online=False OR driver_position_updated_at stale > 10 min →
      clear driver/accepted_at/arrived_at, back to SEARCHING + re-push pool.
      select_for_update + re-check inside atomic.
      Re-push in rule (c) also uses push_new_ride_to_drivers (kind-aware).
"""
from datetime import timedelta

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import RideRequest
from accounts.push import push_new_ride_to_drivers, push_ride_event_to_rider

RELEASE_BEFORE = timedelta(minutes=10)   # release scheduled trips this far ahead
REDISPATCH_AFTER = timedelta(minutes=3)
AUTO_CANCEL_AFTER = timedelta(minutes=15)
STALE_DRIVER_AFTER = timedelta(minutes=10)
_PUSH_THROTTLE_SECONDS = 110  # ~ one sweep interval, so re-push fires at most once per run


class Command(BaseCommand):
    help = "Re-dispatch, auto-cancel, and recover stuck ride requests."

    def handle(self, *args, **options):

        now = timezone.now()
        repushed = cancelled = released = released_scheduled = 0

        # ── (d) Release SCHEDULED trips whose time is approaching ─────────────────
        # A scheduled trip is released when scheduled_for <= now+10min.
        # We flip it to SEARCHING and set dispatched_at=now() so rules (a)/(b)
        # measure timeout from the release moment, not from created_at hours earlier.
        from django.conf import settings as _settings
        from accounts.verticals import vertical_for_ride_kind as _vert_for_kind
        _enabled_verticals = set(getattr(_settings, "VERTICALS_ENABLED", frozenset()))
        for ride in RideRequest.objects.filter(
            status=RideRequest.Status.SCHEDULED,
            scheduled_for__lte=now + RELEASE_BEFORE,
        ):
            # Don't dispatch a scheduled trip whose vertical was disabled after booking
            # (e.g. courier paused) — it stays SCHEDULED until the vertical is back on.
            if _vert_for_kind(ride.kind) not in _enabled_verticals:
                continue
            with transaction.atomic():
                r = (
                    RideRequest.objects.select_for_update()
                    .filter(
                        pk=ride.id,
                        status=RideRequest.Status.SCHEDULED,
                        scheduled_for__lte=now + RELEASE_BEFORE,
                    )
                    .first()
                )
                if r is None:
                    continue  # already released or cancelled between scan and lock
                r.status = RideRequest.Status.SEARCHING
                r.dispatched_at = now
                r.save(update_fields=["status", "dispatched_at"])

            # Kind-aware push — best-effort, after commit
            try:
                push_new_ride_to_drivers(r.id)
            except Exception:
                pass
            released_scheduled += 1

        # ── (a) Re-push unclaimed SEARCHING rides older than 3 min ────────────────
        # Rules (a) and (b) filter on dispatched_at (set at create for immediate trips,
        # set at release for scheduled trips).  Pre-0038 rows have dispatched_at=None;
        # they fall back to created_at so existing behaviour is preserved.
        redispatch_cutoff = now - REDISPATCH_AFTER
        cancel_cutoff = now - AUTO_CANCEL_AFTER

        for ride in RideRequest.objects.filter(
            status=RideRequest.Status.SEARCHING,
            driver__isnull=True,
        ).filter(
            # dispatched_at present and in the 3–15 min window
            Q(dispatched_at__lte=redispatch_cutoff, dispatched_at__gt=cancel_cutoff)
            # pre-0038 legacy row: dispatched_at null, use created_at
            | Q(dispatched_at__isnull=True, created_at__lte=redispatch_cutoff,
                created_at__gt=cancel_cutoff)
        ):
            ckey = f"ride_redispatch_push:{ride.id}"
            if cache.get(ckey):
                continue
            try:
                push_new_ride_to_drivers(ride.id)
            except Exception:
                pass
            cache.set(ckey, 1, _PUSH_THROTTLE_SECONDS)
            repushed += 1

        # ── (b) Auto-cancel SEARCHING rides older than 15 min ────────────────────
        for ride in RideRequest.objects.filter(
            status=RideRequest.Status.SEARCHING,
            driver__isnull=True,
        ).filter(
            # dispatched_at present and past the 15-min cutoff
            Q(dispatched_at__lte=cancel_cutoff)
            # pre-0038 legacy row: dispatched_at null, fall back to created_at
            | Q(dispatched_at__isnull=True, created_at__lte=cancel_cutoff)
        ):
            with transaction.atomic():
                r = (
                    RideRequest.objects.select_for_update()
                    .filter(
                        pk=ride.id,
                        status=RideRequest.Status.SEARCHING,
                        driver__isnull=True,
                    )
                    .first()
                )
                if r is None:
                    continue  # already accepted or cancelled between scan and lock
                r.status = RideRequest.Status.CANCELLED
                r.cancelled_at = now
                r.save(update_fields=["status", "cancelled_at"])

            # Notify rider — best-effort, after commit
            try:
                push_ride_event_to_rider(r.rider_id, "no_driver_found")
            except Exception:
                pass
            cancelled += 1

        # ── (c) Release pre-passenger rides whose driver went offline or stale ────
        candidates = RideRequest.objects.filter(
            status__in=[RideRequest.Status.ACCEPTED, RideRequest.Status.ARRIVED],
        ).select_related("driver")
        for ride in candidates:
            drv = ride.driver
            stale = (
                drv is None
                or not drv.is_driver_online
                or drv.driver_position_updated_at is None
                or drv.driver_position_updated_at <= now - STALE_DRIVER_AFTER
            )
            if not stale:
                continue
            with transaction.atomic():
                r = (
                    RideRequest.objects.select_for_update()
                    .filter(
                        pk=ride.id,
                        status__in=[RideRequest.Status.ACCEPTED, RideRequest.Status.ARRIVED],
                    )
                    .first()
                )
                if r is None:
                    continue  # advanced between scan and lock
                r.driver = None
                r.status = RideRequest.Status.SEARCHING
                r.accepted_at = None
                r.arrived_at = None
                r.save(update_fields=["driver", "status", "accepted_at", "arrived_at"])

            # Re-push to pool — best-effort, after commit (locked row's pk)
            try:
                push_new_ride_to_drivers(r.id)
            except Exception:
                pass
            released += 1

        self.stdout.write(self.style.SUCCESS(
            f"sweep_ride_requests: repushed={repushed} cancelled={cancelled} "
            f"released={released} released_scheduled={released_scheduled}"
        ))
