"""Recover stuck delivery jobs — the safety net + heartbeat for the dispatch loop.

Idempotent; runs every ~60s (Beat or a Coolify scheduled task) so ranked-offer
cascades stay live between driver polls:

    python manage.py sweep_delivery_jobs

Rules (policy: re-dispatch + alert restaurant; refund only as a bounded last resort):
  (0) Exclusive offer window lapsed → cascade to the next-nearest driver / open pool.
  (a) Unclaimed OPEN-POOL SEARCHING > 3 min  → re-broadcast to online drivers (throttled).
  (b) Unclaimed SEARCHING > 10 min → alert the restaurant ONCE (owner_alerted_at).
  (c) ASSIGNED/AT_RESTAURANT (not yet picked up) whose driver went offline / stale
      → release back to the pool + re-offer + alert the restaurant. Wave M M-11:
      an EXPLICITLY OFFLINE driver releases after 2 min (they told us they are
      gone — waiting 10 min wastes the customer's dinner); a merely stale GPS
      still waits the full 10 min. Wave M M-15: a NULL assigned_at (legacy /
      missed stamp) falls back to created_at as the clock, under the lock.
  (d) Still PRE-PICKUP and provably unfulfillable past the tenant's
      Profile.delivery_auto_refund_minutes deadline (never assigned, OR abandoned after the
      re-dispatch cap) → auto-refund & cancel, reusing the owner's manual idempotent
      "refund & cancel" path. 0 = disabled. Prepaid delivery money is otherwise stranded
      indefinitely when no driver ever completes. A driver assigned within the grace
      window (D G1) is never refunded out from under — the deadline is measured from
      creation, so a freshly accepted cap-exhausted job is given its grace window.
  (c2) ASSIGNED/AT_RESTAURANT (not yet picked up) whose driver is still online but idle
      past the pickup SLA (default 15 min from the later of assignment and the
      food-ready time, see PICKUP_SLA_DEFAULT_MINUTES)
      → release back to the pool + re-offer + alert the restaurant. Rule (c) already
      released the stale/offline ones; this catches the online-but-idle driver.
  (f) FAILED jobs still awaiting an owner decision past 60 min → re-alert the restaurant
      (throttled to once per hour per job via owner_alerted_at). No money moves here and
      no auto-refund: the failed-job auto-refund timeout is an owner decision, not yet set.
      (f2) Wave M M-12: the same hourly re-alert for long-UNCLAIMED SEARCHING jobs
      (no driver ever accepted) — rule (b) alerts once at 10 min, then the job went
      silent; past 60 min unclaimed it re-alerts hourly, same throttle.
  (c3) R6-23: the same hourly re-alert for cap-exhausted pre-pickup jobs
      (ASSIGNED/AT_RESTAURANT, redispatch_count >= 3) — rules (c)/(c2) escalate once
      and then go silent forever; past 60 min since that first escalation the owner
      is nudged again, hourly, same atomic-claim throttle.
  (g) Delivery orders (platform delivery on, not SCHEDULED/CANCELLED/COMPLETED) with no
      DeliveryJob past a short grace (5 min) → create the missing job + start dispatch.
      Covers orders whose job creation failed at checkout (those sites now log instead
      of swallowing the error).
  (h) R6-11: WATCH-ONLY rule for PICKED_UP jobs — a driver who vanishes after pickup
      (phone dies / app crashes / goes offline) is otherwise invisible: no rule scans
      PICKED_UP at all. Past 15 min without a position fix, or a pickup older than
      60 min, the owner is alerted hourly (same atomic-claim throttle as (f)/(f2)/
      (c3)). NO auto-fail, NO auto-refund, NO status change — the food is with the
      driver, so this stays an owner decision.
Picked-up jobs are NEVER auto-touched or auto-refunded (the food is with the driver — that
stays a `failed` case + owner decision).
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

REDISPATCH_AFTER = timedelta(minutes=3)
OWNER_ALERT_AFTER = timedelta(minutes=10)
STALE_DRIVER_AFTER = timedelta(minutes=10)
# Wave M M-11: an explicitly-offline driver releases after 2 min, not 10.
OFFLINE_RELEASE_AFTER = timedelta(minutes=2)
MAX_AUTO_REDISPATCH = 3  # match menu.views MAX_REDISPATCH — then escalate, don't loop forever
_PUSH_THROTTLE_SECONDS = 170  # ~ one sweep interval, so re-push fires at most once per run
# D G5 pickup SLA — CONFIGURABLE DEFAULT, 15 min proposed. The owner has NOT confirmed
# this value yet: treat it as a proposal, not policy. Override with the
# DELIVERY_PICKUP_SLA_MINUTES Django setting (minutes). See _pickup_sla().
PICKUP_SLA_DEFAULT_MINUTES = 15
# D G4: a FAILED job re-alerts the owner once per hour once it is this old.
FAILED_REALERT_AFTER = timedelta(minutes=60)
# D G3 backfill grace: a delivery order this old with no job is stranded, not just slow.
JOB_BACKFILL_GRACE = timedelta(minutes=5)


def _pre_pickup_release_due(*, assigned_at, created_at, driver_online,
                          driver_position_updated_at, now) -> bool:
    """Wave M M-11/M-15: is this pre-pickup job due for release under rule (c)?

    Split gate: an EXPLICITLY OFFLINE driver releases after OFFLINE_RELEASE_AFTER
    (2 min) — they told us they are gone. An ONLINE driver only releases after
    STALE_DRIVER_AFTER (10 min) AND a stale GPS fix (a fresh fix means they are
    alive, just slow). A NULL assigned_at falls back to created_at as the clock
    (M-15); with no clock at all the job is releasable (nothing says it is fresh).
    A driverless job counts as offline.
    """
    clock = assigned_at if assigned_at is not None else created_at
    if clock is None:
        return True
    gps_stale = (
        driver_position_updated_at is None
        or driver_position_updated_at <= now - STALE_DRIVER_AFTER
    )
    if not driver_online:
        return clock <= now - OFFLINE_RELEASE_AFTER
    return clock <= now - STALE_DRIVER_AFTER and gps_stale


def _pickup_sla() -> timedelta:
    """Pickup SLA (D G5) as a timedelta, from settings or the proposed default."""
    from django.conf import settings
    try:
        minutes = int(getattr(settings, "DELIVERY_PICKUP_SLA_MINUTES", PICKUP_SLA_DEFAULT_MINUTES)
                      or PICKUP_SLA_DEFAULT_MINUTES)
    except (TypeError, ValueError):
        minutes = PICKUP_SLA_DEFAULT_MINUTES
    return timedelta(minutes=max(1, minutes))


def _fresh_driver_state(driver_id):
    """R6-24: fresh (is_driver_online, driver_position_updated_at) for one driver,
    read at call time — i.e. under the job lock, not from the scan. A missing driver
    (or an unreadable row) counts as offline with no fix, matching the scan's
    driverless-means-offline rule."""
    if driver_id is None:
        return False, None
    try:
        from accounts.models import Customer as _Cust
        row = _Cust.objects.filter(pk=driver_id).values_list(
            "is_driver_online", "driver_position_updated_at").first()
    except Exception:
        return False, None
    if row is None:
        return False, None
    return bool(row[0]), row[1]


def _order_is_terminal(tenant_id, order_number) -> bool:
    """R6-05: has the owner already resolved this failed job by completing or
    cancelling the order themselves? Reads the tenant-schema order. Fail-open
    (False) when the tenant/order can't be read — a lookup hiccup must never
    suppress an alert for a job that still needs a decision."""
    try:
        from django_tenants.utils import schema_context
        from menu.models import Order as _Order
        from tenancy.models import Tenant as _Tenant
        schema = _Tenant.objects.filter(id=tenant_id).values_list(
            "schema_name", flat=True).first()
        if not schema:
            return False
        with schema_context(schema):
            status = _Order.objects.filter(order_number=order_number).values_list(
                "status", flat=True).first()
        return status in (_Order.Status.COMPLETED, _Order.Status.CANCELLED)
    except Exception:
        return False


# R6-06: en-route allowance — how long an ASSIGNED driver gets to REACH the
# restaurant before the (c2) release treats them as idle. PROPOSED default, 30 min:
# twice the pickup SLA — the owner has NOT confirmed this value (D G5 family).
# Override with the DELIVERY_EN_ROUTE_ALLOWANCE_MINUTES Django setting.
EN_ROUTE_ALLOWANCE_DEFAULT_MINUTES = 30


def _en_route_allowance() -> timedelta:
    """En-route allowance (R6-06) as a timedelta, from settings or the proposed default."""
    from django.conf import settings
    try:
        minutes = int(getattr(settings, "DELIVERY_EN_ROUTE_ALLOWANCE_MINUTES", EN_ROUTE_ALLOWANCE_DEFAULT_MINUTES)
                      or EN_ROUTE_ALLOWANCE_DEFAULT_MINUTES)
    except (TypeError, ValueError):
        minutes = EN_ROUTE_ALLOWANCE_DEFAULT_MINUTES
    return timedelta(minutes=max(1, minutes))


class Command(BaseCommand):
    help = "Re-dispatch, escalate, and recover stuck delivery jobs."

    def handle(self, *args, **options):
        from django.core.cache import cache
        from accounts.models import DeliveryJob
        from accounts.dispatch import expire_and_cascade_stale_offers, offer_to_next_driver
        from accounts.push import push_new_job_to_drivers
        from accounts.tasks import enqueue, web_push_tenant
        from tenancy.models import Tenant

        now = timezone.now()
        _names: dict = {}

        # (0) Advance ranked-offer cascades whose exclusive window lapsed — offer to
        #     the next-nearest driver, or open to the pool. The cornerstone of the
        #     dispatch loop's liveness between driver polls.
        offers_advanced = expire_and_cascade_stale_offers()

        def tenant_info(tid):
            if tid not in _names:
                t = Tenant.objects.filter(id=tid).first()
                _names[tid] = ((t.name if t else ""), (t.schema_name if t else ""))
            return _names[tid]

        def alert_owner(tid, order_number, title, body):
            _, schema = tenant_info(tid)
            if not schema:
                return
            enqueue(web_push_tenant, schema, title, body, "/owner/orders")
            try:
                from accounts.notifications import record_notification
                record_notification(channel="push", event="delivery.no_driver", status="sent",
                                     recipient=f"tenant:{tid}", reference=str(order_number))
            except Exception:
                pass

        repushed = alerted = released = 0

        # (a) Re-push unclaimed OPEN-POOL SEARCHING jobs (cache-throttled). Exclusive
        #     offers are advanced by the cascade above, not broadcast here.
        for job in DeliveryJob.objects.filter(
            status=DeliveryJob.Status.SEARCHING, driver__isnull=True, is_open_pool=True,
            created_at__lte=now - REDISPATCH_AFTER,
        ):
            ckey = f"redispatch_push:{job.id}"
            if cache.get(ckey):
                continue
            name, _ = tenant_info(job.tenant_id)
            push_new_job_to_drivers(name)
            cache.set(ckey, 1, _PUSH_THROTTLE_SECONDS)
            repushed += 1

        # (b) Escalate to the restaurant once when still unclaimed after 10 min.
        for job in DeliveryJob.objects.filter(
            status=DeliveryJob.Status.SEARCHING, driver__isnull=True,
            owner_alerted_at__isnull=True, created_at__lte=now - OWNER_ALERT_AFTER,
        ):
            if DeliveryJob.objects.filter(pk=job.id, owner_alerted_at__isnull=True).update(owner_alerted_at=now):
                alert_owner(job.tenant_id, job.order_number, "No driver yet",
                            f"Order #{job.order_number} still has no driver — you may need to deliver it yourself.")
                alerted += 1

        # (c) Release abandoned pre-pickup jobs back to the pool.
        # Wave M M-11/M-15 scan: (assigned 2+ min ago AND driver offline) OR
        # (assigned 10+ min ago) OR (no assigned_at stamp at all — the clock
        # falls back to created_at under the lock).
        from django.db.models import Q as _Q
        candidates = DeliveryJob.objects.filter(
            _Q(assigned_at__isnull=True)
            | _Q(assigned_at__lte=now - OFFLINE_RELEASE_AFTER, driver__is_driver_online=False)
            | _Q(assigned_at__lte=now - STALE_DRIVER_AFTER),
            status__in=[DeliveryJob.Status.ASSIGNED, DeliveryJob.Status.AT_RESTAURANT],
            picked_up_at__isnull=True,
        ).select_related("driver")
        for job in candidates:
            drv = job.driver
            if not _pre_pickup_release_due(
                assigned_at=job.assigned_at, created_at=job.created_at,
                driver_online=bool(drv and drv.is_driver_online),
                driver_position_updated_at=getattr(drv, "driver_position_updated_at", None),
                now=now,
            ):
                continue
            with transaction.atomic():
                j = (
                    DeliveryJob.objects.select_for_update()
                    .filter(
                        pk=job.id,
                        status__in=[DeliveryJob.Status.ASSIGNED, DeliveryJob.Status.AT_RESTAURANT],
                        picked_up_at__isnull=True,
                    )
                    .first()
                )
                if j is None:
                    continue  # someone advanced/accepted it between the scan and the lock
                # M-15: re-check the age gate under the lock with the locked
                # row's own clock — the scanned row may be minutes old, and a
                # job created seconds ago must not be released by a stale scan.
                # R6-24: re-read the DRIVER row under the lock too — the scanned
                # drv may be seconds stale, and the 2-min offline fast path turns
                # on the online flag. A driver who flipped back online + heartbeated
                # in the gap must not be released on stale offline data.
                _fresh_online, _fresh_pos = _fresh_driver_state(j.driver_id)
                if not _pre_pickup_release_due(
                    assigned_at=j.assigned_at, created_at=j.created_at,
                    driver_online=_fresh_online,
                    driver_position_updated_at=_fresh_pos,
                    now=now,
                ):
                    continue
                # Cap auto-redispatch: after MAX_AUTO_REDISPATCH cycles, stop re-offering
                # forever (driver-push spam + churn) and escalate to the owner ONCE for a
                # manual reassign/refund instead.
                capped = (j.redispatch_count or 0) >= MAX_AUTO_REDISPATCH
                first_escalation = False
                if capped:
                    if j.owner_alerted_at is None:
                        j.owner_alerted_at = now
                        j.save(update_fields=["owner_alerted_at"])
                        first_escalation = True
                else:
                    j.driver = None
                    j.status = DeliveryJob.Status.SEARCHING
                    j.assigned_at = None
                    j.owner_alerted_at = None
                    j.redispatch_count = (j.redispatch_count or 0) + 1
                    # Fresh ranked-offer cascade for the re-opened job (any driver eligible again).
                    j.offered_to = None
                    j.offer_expires_at = None
                    j.declined_by = []
                    j.offer_round = 0
                    j.is_open_pool = False
                    j.save(update_fields=[
                        "driver", "status", "assigned_at", "owner_alerted_at", "redispatch_count",
                        "offered_to", "offer_expires_at", "declined_by", "offer_round", "is_open_pool",
                    ])
            if capped:
                if first_escalation:
                    alert_owner(job.tenant_id, job.order_number, "Delivery needs manual attention",
                                f"Order #{job.order_number} couldn't be auto-re-assigned after "
                                f"{MAX_AUTO_REDISPATCH} tries — please reassign or refund from Orders.")
                    alerted += 1
                continue
            offer_to_next_driver(job.id)
            alert_owner(job.tenant_id, job.order_number, "Driver dropped — re-assigning",
                        f"Order #{job.order_number}'s driver went offline; finding another.")
            released += 1

        # (c2) Pickup SLA: release online-but-idle assigned drivers (D G5). Extracted
        #     so the release logic is unit-testable.
        sla_released = self._release_idle_assigned_jobs(now, alert_owner)

        # (f) FAILED-job re-alert (D G4): escalate stuck failed jobs hourly. Extracted
        #     so the throttle logic is unit-testable.
        failed_realerted = self._realert_failed_jobs(now, alert_owner)

        # (f2) Wave M M-12: same hourly re-alert for long-unclaimed SEARCHING jobs.
        searching_realerted = self._realert_unclaimed_searching_jobs(now, alert_owner)

        # (c3) R6-23: same hourly re-alert for cap-exhausted pre-pickup jobs.
        capped_realerted = self._realert_capped_assigned_jobs(now, alert_owner)

        # (h) R6-11: watch-only alerts for silent picked-up drivers.
        silent_alerted = self._watch_silent_picked_up_jobs(now, alert_owner)

        # (d) Bounded auto-refund for stuck PRE-PICKUP jobs (money safety net). See
        #     _auto_refund_stuck_jobs — extracted so its money logic is unit-testable.
        refunded = self._auto_refund_stuck_jobs(now, tenant_info, alert_owner)

        # (g) Backfill jobs for delivery orders whose checkout job creation failed (D G3).
        jobs_backfilled = self._backfill_missing_jobs(now)

        # (e) Expire stale PENDING cash-out requests (lazily expired on confirm, but a code
        #     that's never shown would otherwise linger as 'pending').
        from accounts.models import DriverCashoutRequest
        cashouts = DriverCashoutRequest.objects.filter(
            status=DriverCashoutRequest.Status.PENDING, expires_at__lte=now,
        ).update(status=DriverCashoutRequest.Status.EXPIRED, resolved_at=now)

        self.stdout.write(self.style.SUCCESS(
            f"sweep_delivery_jobs: repushed={repushed} alerted={alerted} "
            f"released={released} sla_released={sla_released} "
            f"failed_realerted={failed_realerted} "
            f"searching_realerted={searching_realerted} "
            f"capped_realerted={capped_realerted} "
            f"silent_alerted={silent_alerted} refunded={refunded} "
            f"jobs_backfilled={jobs_backfilled} cashouts_expired={cashouts}"
        ))

    def _release_idle_assigned_jobs(self, now, alert_owner) -> int:
        """Release ASSIGNED/AT_RESTAURANT jobs whose driver is idle past the pickup SLA.

        Rule (c) already released the stale/offline drivers; this rule catches the
        ONLINE-but-idle driver (accepted, never moved, never picked up). The SLA is
        measured from the later of assigned_at and food_ready_at (Wave L L-02),
        so a driver waiting on food that isn't ready yet is never released as
        idle; with no ready time set it measures from assigned_at as before.
        There is no at_restaurant_at timestamp, so an
        AT_RESTAURANT job's whole assignment counts). Same redispatch cap as rule (c):
        past MAX_AUTO_REDISPATCH cycles, escalate once instead of looping forever.
        Returns the count released. Never touches a picked-up job.
        """
        from accounts.dispatch import offer_to_next_driver
        from accounts.models import DeliveryJob

        from django.db.models import Q as _Q
        sla = _pickup_sla()
        allowance = _en_route_allowance()
        released = 0
        # Wave M M-15: a NULL assigned_at is releasable too — the clock falls
        # back to created_at under the lock below.
        # R6-06: the scan is the coarse pre-filter for BOTH clocks — a job is a
        # candidate when it is past the en-route allowance from assignment, past
        # the pickup SLA from arrival, or has no assignment stamp at all.
        candidates = DeliveryJob.objects.filter(
            _Q(assigned_at__isnull=True)
            | _Q(assigned_at__lte=now - allowance)
            | _Q(at_restaurant_at__lte=now - sla),
            status__in=[DeliveryJob.Status.ASSIGNED, DeliveryJob.Status.AT_RESTAURANT],
            picked_up_at__isnull=True,
        ).select_related("driver")
        for job in candidates:
            with transaction.atomic():
                j = (
                    DeliveryJob.objects.select_for_update()
                    .filter(
                        pk=job.id,
                        status__in=[DeliveryJob.Status.ASSIGNED, DeliveryJob.Status.AT_RESTAURANT],
                        picked_up_at__isnull=True,
                    )
                    .first()
                )
                if j is None:
                    continue  # advanced/picked up between the scan and the lock
                # Re-check the SLA under the lock — the driver may have picked up or
                # been released by rule (c) between the scan and now.
                # R6-06: split SLA. An AT_RESTAURANT job waits the pickup SLA from
                # ARRIVAL (at_restaurant_at) — food-aware (L-02, preserved): the wait
                # only counts from the later of arrival and the food-ready time, so
                # a driver standing at the restaurant while the food is still
                # cooking is never released as "idle". An ASSIGNED job gets the
                # longer en-route allowance measured FROM ASSIGNMENT (food readiness
                # doesn't slow the drive — the driver can always arrive and wait).
                # Legacy AT_RESTAURANT rows without an arrival stamp fall back to
                # the en-route clock. Never gate on GPS staleness: the 120-s
                # heartbeat makes a stationary idle driver look exactly as fresh
                # as an en-route one.
                # Wave M M-15: NULL assigned_at → created_at is the clock.
                if j.status == DeliveryJob.Status.AT_RESTAURANT and j.at_restaurant_at is not None:
                    sla_start = j.at_restaurant_at
                    ready_at = j.food_ready_at
                    if ready_at is not None and ready_at > sla_start:
                        sla_start = ready_at
                    _sla = sla
                else:
                    sla_start = j.assigned_at if j.assigned_at is not None else j.created_at
                    _sla = allowance
                if sla_start is None or sla_start > now - _sla:
                    continue
                capped = (j.redispatch_count or 0) >= MAX_AUTO_REDISPATCH
                if capped:
                    if j.owner_alerted_at is None:
                        j.owner_alerted_at = now
                        j.save(update_fields=["owner_alerted_at"])
                        alert_owner(job.tenant_id, job.order_number,
                                    "Delivery needs manual attention",
                                    f"Order #{job.order_number}'s driver stayed idle past the pickup "
                                    f"SLA after {MAX_AUTO_REDISPATCH} tries — please reassign or refund "
                                    f"from Orders.")
                    continue
                j.driver = None
                j.status = DeliveryJob.Status.SEARCHING
                j.assigned_at = None
                j.owner_alerted_at = None
                j.redispatch_count = (j.redispatch_count or 0) + 1
                # Fresh ranked-offer cascade for the re-opened job (any driver eligible again).
                j.offered_to = None
                j.offer_expires_at = None
                j.declined_by = []
                j.offer_round = 0
                j.is_open_pool = False
                j.save(update_fields=[
                    "driver", "status", "assigned_at", "owner_alerted_at", "redispatch_count",
                    "offered_to", "offer_expires_at", "declined_by", "offer_round", "is_open_pool",
                ])
            offer_to_next_driver(job.id)
            alert_owner(job.tenant_id, job.order_number, "Driver idle — re-assigning",
                        f"Order #{job.order_number}'s driver was idle past the pickup SLA; "
                        f"finding another.")
            released += 1
        return released

    def _realert_failed_jobs(self, now, alert_owner, order_is_terminal=None) -> int:
        """Re-alert the owner for FAILED jobs still awaiting a decision (D G4).

        _on_job_failed already alerted once at failure time; this is the hourly
        escalation so a prepaid order's failure can't strand silently forever. Throttled
        to once per FAILED_REALERT_AFTER per job via an atomic owner_alerted_at claim
        (only the caller that flips the timestamp alerts). Jobs whose owner already
        decided are done and never re-alerted: R6-22 — any stamped resolution means
        decided, so only blank-resolution jobs are scanned (this covers both
        REFUNDED_CANCELLED and NOSHOW_PAID); R6-05 — a FAILED job whose order is
        already COMPLETED/CANCELLED was resolved by the owner delivering it
        themselves, so it is skipped per job (injectable `order_is_terminal` for
        tests; defaults to the real tenant-schema read, fail-open). No money moves
        and no auto-refund here — the failed-job auto-refund timeout is an owner
        decision, not yet set. Returns the count re-alerted.
        """
        from django.db.models import Q
        from accounts.models import DeliveryJob

        _order_done = order_is_terminal or _order_is_terminal
        realerted = 0
        for job in DeliveryJob.objects.filter(
            status=DeliveryJob.Status.FAILED,
            failed_at__lte=now - FAILED_REALERT_AFTER,
            resolution="",
        ):
            if _order_done(job.tenant_id, job.order_number):
                continue  # R6-05: owner already resolved it via the order
            claimed = DeliveryJob.objects.filter(
                pk=job.id, status=DeliveryJob.Status.FAILED,
            ).filter(
                Q(owner_alerted_at__isnull=True)
                | Q(owner_alerted_at__lte=now - FAILED_REALERT_AFTER)
            ).update(owner_alerted_at=now)
            if not claimed:
                continue  # alerted within the last hour (or resolved) — skip
            try:
                _reason = job.get_failure_reason_display()
            except Exception:
                _reason = job.failure_reason or "failed"
            alert_owner(job.tenant_id, job.order_number, "Delivery still failed",
                        f"Order #{job.order_number} failed ({_reason}) and still needs a "
                        f"decision — re-dispatch or refund from Orders.")
            realerted += 1
        return realerted

    def _realert_capped_assigned_jobs(self, now, alert_owner) -> int:
        """R6-23: hourly re-alert for cap-exhausted pre-pickup jobs.

        Rules (c)/(c2) escalate once when redispatch_count hits MAX_AUTO_REDISPATCH
        and then go silent: every later sweep sees owner_alerted_at set and does
        nothing. The only backstop was rule (d) auto-refund — and only when the
        tenant hasn't disabled it. This pass is the (f)/(f2) pattern applied to
        capped ASSIGNED/AT_RESTAURANT jobs: past FAILED_REALERT_AFTER (60 min) since
        the first escalation, re-alert hourly via the same atomic owner_alerted_at
        claim (only the caller that flips the timestamp alerts). Never touches a
        picked-up job; no money moves. Returns the count re-alerted.
        """
        from django.db.models import Q
        from accounts.models import DeliveryJob

        realerted = 0
        for job in DeliveryJob.objects.filter(
            status__in=[DeliveryJob.Status.ASSIGNED, DeliveryJob.Status.AT_RESTAURANT],
            redispatch_count__gte=MAX_AUTO_REDISPATCH,
            picked_up_at__isnull=True,
            owner_alerted_at__lte=now - FAILED_REALERT_AFTER,
        ):
            claimed = DeliveryJob.objects.filter(
                pk=job.id,
                status__in=[DeliveryJob.Status.ASSIGNED, DeliveryJob.Status.AT_RESTAURANT],
                redispatch_count__gte=MAX_AUTO_REDISPATCH,
                picked_up_at__isnull=True,
            ).filter(
                Q(owner_alerted_at__isnull=True)
                | Q(owner_alerted_at__lte=now - FAILED_REALERT_AFTER)
            ).update(owner_alerted_at=now)
            if not claimed:
                continue  # alerted within the last hour — skip
            alert_owner(job.tenant_id, job.order_number, "Delivery still needs attention",
                        f"Order #{job.order_number} still has no driver after "
                        f"{MAX_AUTO_REDISPATCH} re-assignments — please reassign or refund "
                        "from Orders.")
            realerted += 1
        return realerted

    def _watch_silent_picked_up_jobs(self, now, alert_owner) -> int:
        """R6-11: watch-only alerts for PICKED_UP jobs whose driver went silent.

        A driver who vanishes after pickup (phone dies / app crashes / goes
        offline) is otherwise invisible: no rule scans PICKED_UP at all, and the
        sweep's design statement ("never auto-touch picked-up jobs") correctly
        forbids auto-refund — but nothing ever prompts the owner to look. This
        pass alerts hourly (same atomic owner_alerted_at claim + 60-min throttle
        as (f)/(f2)/(c3)) when the driver's position is stale past
        SILENT_POSITION_AFTER (15 min — well past the 120-s heartbeat) or the
        pickup itself is older than SILENT_PICKED_UP_AFTER (60 min). NO auto-fail,
        NO auto-refund, NO status change: the food is with the driver, so this
        stays an owner decision. The scan gates on picked_up_at 15+ min old so a
        driver who just picked up (and tapped, proving they are alive) is never
        nagged about a stale pre-pickup fix. Returns the count alerted.
        """
        from django.db.models import Q
        from accounts.delivery_service import (
            SILENT_POSITION_AFTER,
            is_job_driver_silent as _is_silent,
        )
        from accounts.models import DeliveryJob

        alerted = 0
        for job in DeliveryJob.objects.filter(
            status=DeliveryJob.Status.PICKED_UP,
            picked_up_at__lte=now - SILENT_POSITION_AFTER,
        ).select_related("driver"):
            if not _is_silent(job, now):
                continue
            claimed = DeliveryJob.objects.filter(
                pk=job.id, status=DeliveryJob.Status.PICKED_UP,
            ).filter(
                Q(owner_alerted_at__isnull=True)
                | Q(owner_alerted_at__lte=now - FAILED_REALERT_AFTER)
            ).update(owner_alerted_at=now)
            if not claimed:
                continue  # alerted within the last hour — skip
            _mins = (
                int((now - job.picked_up_at).total_seconds() // 60)
                if job.picked_up_at else 0
            )
            alert_owner(job.tenant_id, job.order_number, "Delivery picked up, driver silent",
                        f"Order #{job.order_number} was picked up {_mins} min ago and the driver "
                        "hasn't updated position — check with the customer.")
            alerted += 1
        return alerted

    def _realert_unclaimed_searching_jobs(self, now, alert_owner) -> int:
        """Wave M M-12: re-alert the owner for SEARCHING jobs nobody claimed.

        Rule (b) alerts once at 10 min unclaimed; after that the job went silent
        even though no driver ever accepted. Past FAILED_REALERT_AFTER (60 min)
        unclaimed it re-alerts hourly, throttled exactly like the FAILED
        re-alert: an atomic owner_alerted_at claim (only the caller that flips
        the timestamp alerts). Jobs with a driver are not SEARCHING-unclaimed
        by definition. Returns the count re-alerted.
        """
        from django.db.models import Q
        from accounts.models import DeliveryJob

        realerted = 0
        for job in DeliveryJob.objects.filter(
            status=DeliveryJob.Status.SEARCHING,
            driver__isnull=True,
            created_at__lte=now - FAILED_REALERT_AFTER,
        ):
            claimed = DeliveryJob.objects.filter(
                pk=job.id, status=DeliveryJob.Status.SEARCHING, driver__isnull=True,
            ).filter(
                Q(owner_alerted_at__isnull=True)
                | Q(owner_alerted_at__lte=now - FAILED_REALERT_AFTER)
            ).update(owner_alerted_at=now)
            if not claimed:
                continue  # alerted within the last hour — skip
            alert_owner(job.tenant_id, job.order_number, "Still no driver",
                        f"Order #{job.order_number} still has no driver after an hour — "
                        "you may need to deliver it yourself.")
            realerted += 1
        return realerted

    def _backfill_missing_jobs(self, now) -> int:
        """Create DeliveryJobs for delivery orders whose job creation failed (D G3).

        A delivery order (platform delivery on, live status) older than JOB_BACKFILL_GRACE
        with no DeliveryJob is stranded: the customer paid, the kitchen sees the order,
        but no driver is ever dispatched. The checkout creation sites now log their
        failures instead of swallowing them; this pass recreates the job + starts
        dispatch. Scheduled orders are excluded — release_scheduled_orders creates their
        job at release time, and creating one here would duplicate it. Idempotent: the
        unique (tenant_id, order_number) on DeliveryJob makes get_or_create safe against
        a racing checkout or a re-run. Returns the count created.
        """
        from django_tenants.utils import schema_context
        from accounts.dispatch import start_dispatch
        from accounts.models import DeliveryJob
        from tenancy.delivery_pricing import split_delivery_fee as _split_fee
        from tenancy.models import Tenant

        backfilled = 0
        tenants = Tenant.objects.filter(
            is_active=True,
            lifecycle_status=Tenant.LifecycleStatus.ACTIVE,
        ).exclude(schema_name="public").select_related("profile")
        for tenant in tenants:
            profile = getattr(tenant, "profile", None)
            if profile is None or not getattr(profile, "platform_delivery_enabled", False):
                continue
            schema = getattr(tenant, "schema_name", "")
            if not schema:
                continue
            try:
                job_numbers = set(
                    DeliveryJob.objects.filter(tenant_id=tenant.id)
                    .values_list("order_number", flat=True)
                )
                with schema_context(schema):
                    from menu.models import Order
                    orders = list(
                        Order.objects.filter(
                            fulfillment_type=Order.FulfillmentType.DELIVERY,
                            created_at__lte=now - JOB_BACKFILL_GRACE,
                        ).exclude(status__in=[
                            Order.Status.SCHEDULED,
                            Order.Status.CANCELLED,
                            Order.Status.COMPLETED,
                        ]).exclude(order_number__in=job_numbers)
                    )
                    for order in orders:
                        _dsplit = _split_fee(profile, order.delivery_fee)
                        job, created = DeliveryJob.objects.get_or_create(
                            tenant_id=tenant.id,
                            order_number=order.order_number,
                            defaults={
                                "status": DeliveryJob.Status.SEARCHING,
                                "pickup_address": (getattr(profile, "address", "") or "")[:200],
                                "pickup_lat": getattr(profile, "lat", None),
                                "pickup_lng": getattr(profile, "lng", None),
                                "delivery_address": (order.delivery_address or "")[:200],
                                "delivery_lat": order.delivery_lat,
                                "delivery_lng": order.delivery_lng,
                                "delivery_fee": order.delivery_fee,
                                "driver_payout": _dsplit["driver_payout"],
                                "platform_commission": _dsplit["platform_commission"],
                                "delivery_commission_rate_applied": _dsplit["commission_pct"],
                                "business_type": getattr(profile, "business_type", "restaurant") or "restaurant",
                            },
                        )
                        if not created:
                            continue  # a racing checkout created it first
                        try:
                            start_dispatch(job)
                        except Exception:
                            logger.exception(
                                "backfill: dispatch failed for %s", order.order_number
                            )
                        # Wave M M-04: stamp the food-ready time on the
                        # recreated job — a backfilled CONFIRMED order already
                        # carries an ETA the driver would otherwise never see.
                        try:
                            from accounts.delivery_service import set_delivery_job_food_ready
                            from menu.views import _delivery_job_ready_minutes as _djrm
                            set_delivery_job_food_ready(
                                tenant.id, order.order_number,
                                _djrm(order, tenant),
                            )
                        except Exception:
                            pass
                        backfilled += 1
            except Exception:
                logger.exception("backfill: failed for tenant %s", tenant.id)
                continue
        return backfilled

    def _auto_refund_stuck_jobs(self, now, tenant_info, alert_owner) -> int:
        """Auto-refund & cancel delivery jobs that are stuck PRE-PICKUP and provably
        unfulfillable, once past the tenant's Profile.delivery_auto_refund_minutes
        deadline (0 = disabled). "Provably unfulfillable" = still unassigned/SEARCHING,
        OR abandoned after the re-dispatch cap is exhausted.

        Reuses the owner's manual "refund & cancel" implementation
        (menu.views.refund_and_cancel_delivery_order) so the two paths share ONE
        idempotent, keyed-wallet-credit money path. A picked-up job is NEVER refunded
        (the food is with the driver — an owner decision). Best-effort per job: a
        failure logs + is retried next sweep, and the shared credit is idempotent so a
        partial-then-full pass never double-refunds. Returns the count refunded.
        """
        from django.db.models import Q
        from django_tenants.utils import schema_context
        from accounts.models import DeliveryJob
        from tenancy.models import Profile
        from menu.views import refund_and_cancel_delivery_order

        deadline_cache: dict = {}

        def refund_deadline_minutes(tid):
            """Per-tenant auto-refund deadline (0 = disabled). Profile is in the shared
            public schema keyed by tenant, so it reads directly with no schema switch."""
            if tid not in deadline_cache:
                p = (
                    Profile.objects.filter(tenant_id=tid)
                    .values_list("delivery_auto_refund_minutes", flat=True)
                    .first()
                )
                deadline_cache[tid] = int(p or 0)
            return deadline_cache[tid]

        # Scan pre-pickup, non-terminal jobs that are provably unfulfillable:
        #   (a) still SEARCHING with no driver ever assigned, OR
        #   (b) re-dispatch cap exhausted (abandoned).
        refund_candidates = DeliveryJob.objects.filter(
            picked_up_at__isnull=True,
            status__in=[
                DeliveryJob.Status.SEARCHING,
                DeliveryJob.Status.ASSIGNED,
                DeliveryJob.Status.AT_RESTAURANT,
            ],
        ).filter(
            Q(status=DeliveryJob.Status.SEARCHING, driver__isnull=True)
            | Q(redispatch_count__gte=MAX_AUTO_REDISPATCH)
        )

        refunded = 0
        for job in refund_candidates:
            minutes = refund_deadline_minutes(job.tenant_id)
            if minutes <= 0:
                continue  # auto-refund disabled for this tenant
            if job.created_at > now - timedelta(minutes=minutes):
                continue  # not stuck long enough yet
            _, schema = tenant_info(job.tenant_id)
            if not schema:
                continue
            did_refund = False
            try:
                with transaction.atomic():
                    # Re-lock and re-verify UNDER the lock — a driver may have accepted or
                    # even picked up between the scan and now. We must NEVER refund a
                    # picked-up job, and only refund one that is still provably stuck.
                    j = (
                        DeliveryJob.objects.select_for_update()
                        .filter(pk=job.id, picked_up_at__isnull=True)
                        .exclude(status__in=[
                            DeliveryJob.Status.PICKED_UP,
                            DeliveryJob.Status.DELIVERED,
                            DeliveryJob.Status.FAILED,
                            DeliveryJob.Status.CANCELLED,
                        ])
                        .first()
                    )
                    if j is None:
                        continue  # picked up / terminal / gone since the scan
                    # D G1: a driver assigned within the grace window must not have
                    # the order refunded out from under them. The deadline is measured
                    # from job.created_at, so a cap-exhausted job that a driver JUST
                    # accepted would otherwise be refunded minutes after assignment.
                    # STALE_DRIVER_AFTER (10 min) is the grace: by then rule (c) has
                    # already released a stale/offline driver, so an assigned driver
                    # older than that is genuinely stuck. (An assigned_at of None with
                    # a driver set predates the timestamp tracking — treat it as stale,
                    # i.e. refundable, as before.)
                    freshly_assigned = (
                        j.driver_id is not None
                        and j.assigned_at is not None
                        and j.assigned_at > now - STALE_DRIVER_AFTER
                    )
                    still_stuck = (
                        (j.status == DeliveryJob.Status.SEARCHING and j.driver_id is None)
                        or (
                            (j.redispatch_count or 0) >= MAX_AUTO_REDISPATCH
                            and not freshly_assigned
                        )
                    )
                    if not still_stuck:
                        continue  # a driver was just assigned — let dispatch play out
                    with schema_context(schema):
                        from menu.models import Order
                        order = Order.objects.filter(order_number=j.order_number).first()
                        if order is None:
                            continue  # order gone — leave the orphan for reconcile_order_refs
                        # R6-04: the owner already fulfilled (COMPLETED) or cancelled
                        # this order — never refund it. (The shared helper guards
                        # COMPLETED too; this skip avoids even calling it.)
                        if order.status in (Order.Status.COMPLETED, Order.Status.CANCELLED):
                            continue
                        # Shared idempotent path: cancel + wallet-refund + reverse loyalty
                        # + restock + stand the driver down + realtime-broadcast to the
                        # customer's tracking page AND the owner's orders screen.
                        # Use the helper's return: True only if THIS call performed the
                        # cancellation. If the order was already cancelled (e.g. the owner
                        # manually refunded first), it returns False — so we don't re-count
                        # or re-alert "auto-refunded" for a job a later sweep re-examines.
                        did_refund = refund_and_cancel_delivery_order(order, j.tenant_id)
            except Exception:
                logger.exception("auto-refund failed for delivery job %s", job.id)
                continue
            if did_refund:
                refunded += 1
                # Actively notify the owner via the sweep's existing push mechanism (the
                # customer's realtime tracking page was refreshed by the broadcast above).
                alert_owner(
                    job.tenant_id, job.order_number, "Delivery auto-refunded",
                    f"Order #{job.order_number} had no driver after {minutes} min and was "
                    f"auto-cancelled; any wallet prepayment was refunded to the customer.",
                )
        return refunded
