"""Delivery-job lifecycle helpers shared by views + the stale-job sweep.

These coordinate the public-schema ``DeliveryJob`` with tenant-schema orders, so they
live outside ``views`` to avoid circular imports and can be reused from management
commands.
"""
from decimal import Decimal

from django.db import transaction


def cancel_delivery_job_for_order(tenant_id, order_number):
    """Cancel the active delivery job for an order (call this whenever the order is cancelled).

    Race-safe via ``select_for_update``; a **no-op** when the job is already terminal
    (delivered / failed / cancelled), so it can't un-do a completed delivery. Notifies the
    assigned driver (best-effort, after commit). Returns the job (or None if there was none).
    """
    from django.utils import timezone
    from .models import DeliveryJob

    prev_driver_id = None
    job = None
    with transaction.atomic():
        job = (
            DeliveryJob.objects.select_for_update()
            .filter(tenant_id=tenant_id, order_number=order_number)
            .first()
        )
        if job is None or job.is_terminal:
            return job
        prev_driver_id = job.driver_id
        job.status = DeliveryJob.Status.CANCELLED
        job.cancelled_at = timezone.now()
        job.platform_commission = Decimal("0")
        job.save(update_fields=["status", "cancelled_at", "platform_commission"])

    # Tell the assigned driver to stand down (never blocks / raises).
    if prev_driver_id:
        try:
            from accounts.tasks import enqueue, driver_job_cancelled
            enqueue(driver_job_cancelled, prev_driver_id, order_number)
        except Exception:
            pass
    return job


def complete_delivery_job_for_order(tenant_id, order_number):
    """Reconcile the delivery job when the OWNER completes the order (not the driver's own tap).

    The driver->job direction (their "delivered" tap) closes the job and credits earnings, but the
    owner->order COMPLETED direction historically did neither, leaving the job dangling at
    ``picked_up`` forever: the driver is uncredited (unless they also tap delivered) and — because
    ``picked_up`` is an active status — soft-locked out of new offers.

    Race-safe via ``select_for_update``; a **no-op** when the job is already terminal (so it can't
    fight a driver who also tapped delivered) or has no assigned driver. Otherwise marks the job
    ``DELIVERED`` and credits the driver, reusing ``_credit_driver_earnings`` (idempotent on
    ``earning:{job.id}``) so double-completion never double-pays. Returns the job (or None).

    OPS-5f: the credit is gated on the driver still being ``driver_approved``, exactly as the
    driver's own DELIVERED tap re-checks it (``DriverJobStatusUpdateView`` in ``accounts/views.py``).
    A driver who was approved, accepted + picked up, then had approval revoked (fraud / expired
    docs) must NOT bank earnings through the owner-completion side either. On revocation this is a
    **no-op** — the job is deliberately left un-transitioned rather than marked ``DELIVERED``:
    ``reconcile_driver_earnings`` re-credits any ``DELIVERED`` job with a driver + payout (it
    intentionally does not re-check live approval, so it can't wrongly deny a delivered-then-revoked
    driver), so marking it ``DELIVERED`` here would let the sweep silently re-pay the revoked driver.
    Leaving it un-transitioned mirrors the driver path (which also returns before mutating) and keeps
    the sweep out of it (it only scans ``status=DELIVERED``).
    """
    from django.utils import timezone
    from .models import DeliveryJob, Customer

    job = None
    with transaction.atomic():
        job = (
            DeliveryJob.objects.select_for_update()
            .filter(tenant_id=tenant_id, order_number=order_number)
            .first()
        )
        if job is None or job.is_terminal or not job.driver_id:
            return job
        # OPS-5f approval re-check at the money-emitting transition. Re-read the flag under
        # the lock; a revoked driver is neither credited nor marked DELIVERED (see docstring).
        if not Customer.objects.filter(pk=job.driver_id, driver_approved=True).exists():
            return job
        job.status = DeliveryJob.Status.DELIVERED
        job.delivered_at = timezone.now()
        job.save(update_fields=["status", "delivered_at"])

    # Credit the driver's payout (public schema; idempotent). Lazy import avoids the
    # views<->service cycle, matching this module's convention; best-effort like the driver path.
    try:
        from accounts.views import _credit_driver_earnings
        _credit_driver_earnings(job)
    except Exception:
        pass
    return job


# Sentinel: "no previous-minutes value was supplied" (distinct from None, which
# is a real answer — "no timing applies"). Creation sites pass no previous value
# and always stamp; the owner status-view mirror passes the pre-PATCH answer so a
# status-only tap / note edit can't re-anchor the ready time (Wave M M-05).
_UNSET = object()


def should_restamp_food_ready_on_redispatch(order, job) -> bool:
    """Wave M M-14(b): after a FAILED job is re-dispatched, should the mirror
    re-stamp ``food_ready_at``?

    While the job was FAILED the mirror no-op'd (terminal), so an ETA edit made
    while the job awaited a decision never reached the job. Re-stamp when:
      * the job has no ready time yet, or
      * the order carries an explicit ETA whose absolute anchor
        (``order.estimated_ready_at``, re-anchored on every ETA write) no longer
        matches the job's anchor — the ETA was edited while FAILED — or the
        order never had an absolute anchor to compare against.
    Otherwise (same ETA, anchors agree within 30s — they are stamped seconds
    apart at confirm) the original anchor stands: a redispatch with no
    intervening ETA edit must not push the ready time forward.
    """
    if getattr(job, "food_ready_at", None) is None:
        return True
    if getattr(order, "estimated_ready_minutes", None) is None:
        return False
    order_anchor = getattr(order, "estimated_ready_at", None)
    if order_anchor is None:
        return True
    try:
        gap = abs((order_anchor - job.food_ready_at).total_seconds())
    except Exception:
        return True
    return gap > 30


def set_delivery_job_food_ready(tenant_id, order_number, minutes, previous_minutes=_UNSET):
    """Record when the food will be ready on the order's active delivery job.

    Called when the owner confirms a delivery order and enters a prep ETA, so the
    assigned/searching driver knows when to be at the restaurant (pre-dispatch
    timing). Stores an absolute ``food_ready_at`` = now + ``minutes``; a ``minutes``
    of None/blank clears it. Race-safe; a no-op on a terminal job. Returns the job
    (or None). Best-effort — callers wrap in try/except.

    Anchor-aware (Wave M M-05): when ``previous_minutes`` is given (the owner
    status-view mirror passes the pre-PATCH answer), the stamp is SKIPPED when
    the ETA value is unchanged AND the job already has a ``food_ready_at`` — a
    status-only tap or a note edit must not move an existing anchor. Creation
    sites pass no previous value and always stamp (the job is fresh).
    """
    from datetime import timedelta
    from django.utils import timezone
    from .models import DeliveryJob

    try:
        if minutes in (None, ""):
            ready_at = None
        else:
            ready_at = timezone.now() + timedelta(minutes=max(0, int(minutes)))
    except (TypeError, ValueError):
        return None

    with transaction.atomic():
        job = (
            DeliveryJob.objects.select_for_update()
            .filter(tenant_id=tenant_id, order_number=order_number)
            .first()
        )
        if job is None or job.is_terminal:
            return job
        # M-05: unchanged ETA + an existing anchor → keep the anchor. The
        # mirror's input is a duration ("20 min from when the owner said so");
        # re-stamping it on every PATCH would rebase the ready time on every tap.
        if (
            previous_minutes is not _UNSET
            and previous_minutes == minutes
            and job.food_ready_at is not None
        ):
            return job
        job.food_ready_at = ready_at
        job.save(update_fields=["food_ready_at"])
    return job
