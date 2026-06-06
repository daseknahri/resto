"""Delivery-job lifecycle helpers shared by views + the stale-job sweep.

These coordinate the public-schema ``DeliveryJob`` with tenant-schema orders, so they
live outside ``views`` to avoid circular imports and can be reused from management
commands.
"""
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
        job.save(update_fields=["status", "cancelled_at"])

    # Tell the assigned driver to stand down (never blocks / raises).
    if prev_driver_id:
        try:
            from accounts.tasks import enqueue, driver_job_cancelled
            enqueue(driver_job_cancelled, prev_driver_id, order_number)
        except Exception:
            pass
    return job
