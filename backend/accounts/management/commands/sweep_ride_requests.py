"""Recover stuck ride requests — the safety net + heartbeat for the dispatch loop.

Idempotent; runs every ~120s (Beat or a Coolify scheduled task) so trip offers
stay live between driver polls:

    python manage.py sweep_ride_requests

Rules (policy: re-dispatch, auto-cancel only on timeout, never touch a *legitimate*
in_progress trip — see rule (e) for the one narrow exception):
  (d) SCHEDULED with scheduled_for <= now+10min: atomic select_for_update re-check,
      flip to SEARCHING, set dispatched_at=now(), then kind-aware driver push. For
      PACKAGE trips it also sends the recipient tracking-link SMS here (deferred from
      create, which skips it for scheduled trips), mirroring the immediate-create path.
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
      Also resets dispatched_at=now() (like rule (d)) so the re-pooled trip gets a
      fresh 3-min re-push / 15-min auto-cancel window instead of measuring from its
      original dispatch time and being cancelled on the very next sweep.
      select_for_update + re-check inside atomic.
      Re-push in rule (c) also uses push_new_ride_to_drivers (kind-aware).
  (e) IN_PROGRESS recovery — two independent rescue conditions, both applied under
      the ride row-lock, so a stuck trip is never stranded forever (the rider can't
      cancel from in_progress and can't book again while one is open):
        (e1) driver is None OR driver_approved=False (revoked for fraud / expired
             docs) → auto-cancel immediately. Backstop for a trip whose driver was
             revoked mid-flight: the assigned driver can still complete it themselves
             (DriverRideStatusView is not gated on driver_approved), but if they never
             do it can never settle for pay (ride_service._do_settle skips crediting a
             revoked driver). Shipped in #276.
        (e2) driver is still APPROVED but has gone ABSENT mid-trip — offline
             (is_driver_online=False) or GPS-stale (driver_position_updated_at older
             than the generous window) — AND the trip has been in_progress past a
             GENEROUS, kind-aware timeout (a courier package may legitimately run much
             longer than a passenger ride). Owner-decision #3: an approved driver who
             simply vanishes past a generous window would otherwise strand the trip.
      In BOTH cases the rider is auto-cancelled (NOT charged) and notified. A driver
      who is still online AND freshly-pinging is NEVER touched — they are legitimately
      in-flight and will complete the trip. select_for_update + re-check inside atomic.
"""
from datetime import timedelta

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import RideRequest
from accounts.push import (
    push_new_ride_to_drivers,
    push_recipient_track_sms,
    push_ride_event_to_rider,
)

RELEASE_BEFORE = timedelta(minutes=10)   # release scheduled trips this far ahead
REDISPATCH_AFTER = timedelta(minutes=3)
AUTO_CANCEL_AFTER = timedelta(minutes=15)
STALE_DRIVER_AFTER = timedelta(minutes=10)
_PUSH_THROTTLE_SECONDS = 110  # ~ one sweep interval, so re-push fires at most once per run

# Rule (e2): GENEROUS, kind-aware "the assigned driver has vanished mid-trip" timeout
# for an IN_PROGRESS trip whose driver is still APPROVED. Deliberately far larger than
# STALE_DRIVER_AFTER (rule c, 10 min): a driver who is genuinely mid-fare pings GPS
# continuously (that is what powers the live tracking), so we only reclaim a
# fare-bearing trip once BOTH the trip has been running longer than any legitimate trip
# of that kind AND the driver currently looks gone (offline or GPS-stale). A courier
# package delivery may legitimately run much longer than a passenger ride, so it gets a
# longer window. The admin force-resolve endpoint covers the impatient/urgent case, so
# the automatic net can afford to be this generous.
IN_PROGRESS_ABSENT_AFTER_RIDE = timedelta(hours=2)
IN_PROGRESS_ABSENT_AFTER_PACKAGE = timedelta(hours=8)


def _approved_driver_absent(ride, drv, now) -> bool:
    """True iff an IN_PROGRESS trip's still-APPROVED driver has vanished mid-trip (e2).

    Two conjuncts, both required so we never disrupt a legitimate in-flight trip:
      * the trip has been in_progress past the GENEROUS, kind-aware window
        (measured from started_at, falling back to created_at for any anomalous row
        with no start stamp), AND
      * the driver currently looks GONE — toggled offline, never pinged, or whose GPS
        has not updated within that same generous window.
    A driver who is still online AND freshly-pinging fails the second conjunct, so an
    actively-driving driver on a long trip is left alone. Caller has already confirmed
    drv is not None and drv.driver_approved.
    """
    absent_after = (
        IN_PROGRESS_ABSENT_AFTER_PACKAGE
        if ride.kind == RideRequest.Kind.PACKAGE
        else IN_PROGRESS_ABSENT_AFTER_RIDE
    )
    ref = ride.started_at or ride.created_at
    trip_running_long = ref is None or ref <= now - absent_after
    pos = drv.driver_position_updated_at
    driver_gone = (
        not drv.is_driver_online
        or pos is None
        or pos <= now - absent_after
    )
    return bool(trip_running_long and driver_gone)


class Command(BaseCommand):
    help = "Re-dispatch, auto-cancel, and recover stuck ride requests."

    def handle(self, *args, **options):

        now = timezone.now()
        repushed = cancelled = released = released_scheduled = 0
        cancelled_stranded = 0

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
            # Recipient tracking SMS for scheduled PACKAGE trips. Immediate packages get
            # this at create; scheduled ones are deferred to here (their release moment)
            # so the recipient's link goes out exactly when the trip enters the search
            # pool. Best-effort, mirroring the immediate-create path.
            if r.kind == RideRequest.Kind.PACKAGE:
                try:
                    push_recipient_track_sms(r.id, "dispatched")
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
                # Reset the dispatch clock so the re-pooled trip gets a fresh search
                # window (rules a/b measure from dispatched_at) instead of being
                # auto-cancelled on the next sweep against its original dispatch time.
                r.dispatched_at = now
                r.save(update_fields=[
                    "driver", "status", "accepted_at", "arrived_at", "dispatched_at",
                ])

            # Re-push to pool — best-effort, after commit (locked row's pk)
            try:
                push_new_ride_to_drivers(r.id)
            except Exception:
                pass
            released += 1

        # ── (e) Recover stuck in_progress trips ──────────────────────────────────
        # Two rescue conditions (see the module docstring):
        #   (e1) driver None / REVOKED  → cancel immediately.
        #   (e2) driver APPROVED but ABSENT past the generous kind-aware window → cancel.
        # In both cases the rider is auto-cancelled (not charged) and notified. A trip
        # whose approved driver is still online and freshly-pinging is left untouched.
        candidates = RideRequest.objects.filter(
            status=RideRequest.Status.IN_PROGRESS,
        ).select_related("driver")
        for ride in candidates:
            drv = ride.driver
            # Skip ONLY a legitimate in-flight trip: an approved driver who has NOT yet
            # gone absent past the generous window. A None / revoked driver (e1) or an
            # approved-but-vanished driver (e2) both fall through to the lock+cancel.
            if drv is not None and drv.driver_approved and not _approved_driver_absent(ride, drv, now):
                continue
            with transaction.atomic():
                r = (
                    RideRequest.objects.select_for_update()
                    .filter(pk=ride.id, status=RideRequest.Status.IN_PROGRESS)
                    .first()
                )
                if r is None:
                    continue  # completed / advanced between scan and lock
                # Re-check under the ride lock: approval could have been restored, or an
                # approved driver could have resumed pinging / completed, between the scan
                # and the lock. We deliberately do NOT lock the driver row.
                rdrv = r.driver
                if rdrv is not None and rdrv.driver_approved and not _approved_driver_absent(r, rdrv, now):
                    continue
                r.status = RideRequest.Status.CANCELLED
                r.cancelled_at = now
                r.save(update_fields=["status", "cancelled_at"])

            # Notify rider — best-effort, after commit (mirrors rule (b)'s auto-cancel)
            try:
                push_ride_event_to_rider(r.rider_id, "no_driver_found")
            except Exception:
                pass
            cancelled_stranded += 1

        self.stdout.write(self.style.SUCCESS(
            f"sweep_ride_requests: repushed={repushed} cancelled={cancelled} "
            f"released={released} released_scheduled={released_scheduled} "
            f"cancelled_stranded={cancelled_stranded}"
        ))
