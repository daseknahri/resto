"""Recover stuck ride requests — the safety net + heartbeat for the dispatch loop.

Idempotent; runs every ~120s (Beat or a Coolify scheduled task) so trip offers
stay live between driver polls:

    python manage.py sweep_ride_requests

Rules (policy: re-dispatch, auto-cancel only on timeout, never touch in_progress):
  (a) SEARCHING > 3 min  → re-push (throttled, ~110s cache key so re-push fires at most
      once per sweep cycle).  push_new_ride_to_drivers branches on kind internally:
        ride    → car drivers with car_approved.
        package → all approved online drivers.
  (b) SEARCHING > 15 min → auto-cancel (status CANCELLED + cancelled_at) + web-push
      rider "no driver found". select_for_update + re-check inside atomic.
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
from django.utils import timezone

from accounts.models import RideRequest
from accounts.push import push_new_ride_to_drivers, push_ride_event_to_rider

REDISPATCH_AFTER = timedelta(minutes=3)
AUTO_CANCEL_AFTER = timedelta(minutes=15)
STALE_DRIVER_AFTER = timedelta(minutes=10)
_PUSH_THROTTLE_SECONDS = 110  # ~ one sweep interval, so re-push fires at most once per run


class Command(BaseCommand):
    help = "Re-dispatch, auto-cancel, and recover stuck ride requests."

    def handle(self, *args, **options):

        now = timezone.now()
        repushed = cancelled = released = 0

        # (a) Re-push unclaimed SEARCHING rides older than 3 min (cache-throttled).
        for ride in RideRequest.objects.filter(
            status=RideRequest.Status.SEARCHING,
            driver__isnull=True,
            created_at__lte=now - REDISPATCH_AFTER,
            created_at__gt=now - AUTO_CANCEL_AFTER,  # skip the >15 min ones (handled by (b))
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

        # (b) Auto-cancel SEARCHING rides older than 15 min → notify rider.
        for ride in RideRequest.objects.filter(
            status=RideRequest.Status.SEARCHING,
            driver__isnull=True,
            created_at__lte=now - AUTO_CANCEL_AFTER,
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

            # Notify rider — best-effort, after commit (use the locked row's
            # fields, not the stale scan object)
            try:
                push_ride_event_to_rider(r.rider_id, "no_driver_found")
            except Exception:
                pass
            cancelled += 1

        # (c) Release pre-passenger rides whose driver went offline or stale.
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
            f"sweep_ride_requests: repushed={repushed} cancelled={cancelled} released={released}"
        ))
