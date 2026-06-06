"""Recover stuck delivery jobs — the safety net for the dispatch loop.

Idempotent; safe to run every few minutes (Beat or a Coolify scheduled task):

    python manage.py sweep_delivery_jobs

Three rules (policy: re-dispatch + alert restaurant; never auto-cancel/refund):
  (a) Unclaimed SEARCHING > 3 min  → re-offer to online drivers (throttled per job).
  (b) Unclaimed SEARCHING > 10 min → alert the restaurant ONCE (owner_alerted_at).
  (c) ASSIGNED/AT_RESTAURANT (not yet picked up) whose driver went offline / stale > 10 min
      → release back to the pool + re-offer + alert the restaurant.
Picked-up jobs are never auto-touched (the food is with the driver — that's a `failed` case).
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

REDISPATCH_AFTER = timedelta(minutes=3)
OWNER_ALERT_AFTER = timedelta(minutes=10)
STALE_DRIVER_AFTER = timedelta(minutes=10)
_PUSH_THROTTLE_SECONDS = 170  # ~ one sweep interval, so re-push fires at most once per run


class Command(BaseCommand):
    help = "Re-dispatch, escalate, and recover stuck delivery jobs."

    def handle(self, *args, **options):
        from django.core.cache import cache
        from accounts.models import DeliveryJob
        from accounts.push import push_new_job_to_drivers
        from accounts.tasks import enqueue, web_push_tenant
        from tenancy.models import Tenant

        now = timezone.now()
        _names: dict = {}

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

        # (a) Re-push unclaimed SEARCHING jobs (cache-throttled so we don't spam).
        for job in DeliveryJob.objects.filter(
            status=DeliveryJob.Status.SEARCHING, driver__isnull=True,
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
        candidates = DeliveryJob.objects.filter(
            status__in=[DeliveryJob.Status.ASSIGNED, DeliveryJob.Status.AT_RESTAURANT],
            picked_up_at__isnull=True, assigned_at__lte=now - STALE_DRIVER_AFTER,
        ).select_related("driver")
        for job in candidates:
            drv = job.driver
            stale = (
                drv is None
                or not drv.is_driver_online
                or drv.driver_position_updated_at is None
                or drv.driver_position_updated_at <= now - STALE_DRIVER_AFTER
            )
            if not stale:
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
                j.driver = None
                j.status = DeliveryJob.Status.SEARCHING
                j.assigned_at = None
                j.owner_alerted_at = None
                j.redispatch_count = (j.redispatch_count or 0) + 1
                j.save(update_fields=["driver", "status", "assigned_at", "owner_alerted_at", "redispatch_count"])
            name, _ = tenant_info(job.tenant_id)
            push_new_job_to_drivers(name)
            alert_owner(job.tenant_id, job.order_number, "Driver dropped — re-assigning",
                        f"Order #{job.order_number}'s driver went offline; finding another.")
            released += 1

        # (d) Expire stale PENDING cash-out requests (lazily expired on confirm, but a code
        #     that's never shown would otherwise linger as 'pending').
        from accounts.models import DriverCashoutRequest
        cashouts = DriverCashoutRequest.objects.filter(
            status=DriverCashoutRequest.Status.PENDING, expires_at__lte=now,
        ).update(status=DriverCashoutRequest.Status.EXPIRED, resolved_at=now)

        self.stdout.write(self.style.SUCCESS(
            f"sweep_delivery_jobs: repushed={repushed} alerted={alerted} "
            f"released={released} cashouts_expired={cashouts}"
        ))
