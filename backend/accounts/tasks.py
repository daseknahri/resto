"""
Celery tasks for outbound notifications + scheduled jobs, plus the ``enqueue`` helper.

Design goal: the queue must NEVER be load-bearing for the request path. ``enqueue``
runs a task on the worker when a broker is configured, and otherwise falls back to the
historical fire-and-forget daemon thread. So:
  - With Redis + a running worker  → durable, off-process, survives web restarts.
  - Without a broker (dev/local)   → identical to the old behaviour, no worker needed.

Tasks are thin wrappers around the existing synchronous dispatch functions (which already
write NotificationLog rows). ``autoretry_for`` retries on unexpected task-level errors;
provider-level failures (e.g. a Twilio 5xx) are recorded as ``failed`` by the sync
functions — surfacing those for retry is a follow-up that needs the senders to raise.
"""
from __future__ import annotations

import logging
import threading

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)

_RETRY = dict(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})


def enqueue(task, *args, **kwargs) -> None:
    """Dispatch *task* via Celery when a broker is configured, else run it inline in a
    daemon thread. Never raises, never blocks the caller."""
    if getattr(settings, "CELERY_BROKER_URL", ""):
        try:
            task.delay(*args, **kwargs)
            return
        except Exception:  # broker unreachable → don't lose the notification
            logger.warning("Celery enqueue failed for %s; running inline",
                           getattr(task, "name", task), exc_info=True)
    threading.Thread(target=_run_inline, args=(task, args, kwargs), daemon=True).start()


def _run_inline(task, args, kwargs) -> None:
    try:
        task.run(*args, **kwargs)  # execute the task body directly (no broker)
    except Exception:
        logger.warning("inline task %s failed", getattr(task, "name", task), exc_info=True)


# ── Notification tasks ──────────────────────────────────────────────────────────

@shared_task(name="accounts.tasks.web_push_tenant", acks_late=True, **_RETRY)
def web_push_tenant(schema_name, title, body, url="/owner/orders"):
    from menu.push import _push_to_tenant
    _push_to_tenant(schema_name, title, body, url)


@shared_task(name="accounts.tasks.sms_order_ready", **_RETRY)
def sms_order_ready(phone, tenant_name, order_number, tenant_id=None):
    from menu.sms import send_order_ready_sms
    send_order_ready_sms(phone, tenant_name, order_number, tenant_id=tenant_id)


@shared_task(name="accounts.tasks.whatsapp_new_order", **_RETRY)
def whatsapp_new_order(schema_name, order_id, tenant_name, whatsapp_phone, tenant_id=None):
    from django_tenants.utils import schema_context
    from menu.models import Order
    from menu.views import _notify_restaurant_new_order
    with schema_context(schema_name):
        order = Order.objects.prefetch_related("items").filter(id=order_id).first()
        if order is None:
            return
        _notify_restaurant_new_order(
            order, tenant_name=tenant_name, whatsapp_phone=whatsapp_phone, tenant_id=tenant_id,
        )


@shared_task(name="accounts.tasks.driver_dispatch", **_RETRY)
def driver_dispatch(restaurant_name=None):
    from accounts.push import notify_online_drivers_new_job_sync
    notify_online_drivers_new_job_sync(restaurant_name)


@shared_task(name="accounts.tasks.driver_job_cancelled", **_RETRY)
def driver_job_cancelled(driver_id, order_number):
    from accounts.push import notify_driver_job_cancelled_sync
    notify_driver_job_cancelled_sync(driver_id, order_number)


@shared_task(name="accounts.tasks.driver_job_offer", **_RETRY)
def driver_job_offer(driver_id, restaurant_name=None):
    from accounts.push import notify_driver_job_offer_sync
    notify_driver_job_offer_sync(driver_id, restaurant_name)


@shared_task(name="accounts.tasks.customer_order_milestone", **_RETRY)
def customer_order_milestone(order_number, tenant_id, event):
    from accounts.push import notify_customer_order_milestone_sync
    notify_customer_order_milestone_sync(order_number, tenant_id, event)


# SECURITY: run_management_command is registered by name on the Celery broker, which
# is unauthenticated by default — anyone who can enqueue could otherwise run shell /
# dbshell / flush / migrate. We hardcode the ONLY commands Beat is allowed to invoke;
# this is the exact set scheduled in config/settings.py CELERY_BEAT_SCHEDULE. Adding a
# new scheduled command means adding its name here too.
_MANAGEMENT_COMMAND_ALLOWLIST = frozenset({
    "release_scheduled_orders",
    "send_review_prompts",
    "send_reservation_reminders",
    "expire_charge_requests",
    "sweep_delivery_jobs",
    "sweep_ride_requests",
    "enforce_subscriptions",
    "fetch_currency_rates",
    "send_daily_summary",
    "auto_reset_availability",
    "send_winback_nudges",
    "prune_analytics_events",
    "prune_admin_audit_logs",
    "prune_notification_logs",
    "prune_winback_nudges",
    "prune_staff_messages",
    "prune_auth_tokens",
})


@shared_task(name="accounts.tasks.write_beat_heartbeat", acks_late=True, ignore_result=True)
def write_beat_heartbeat():
    """Write a freshness heartbeat that /api/health/ reads to detect a dead beat/worker.

    config.api._check_celery reads the cache key ``celery_beat_heartbeat``; nothing else
    writes it. Scheduled every ~60s in CELERY_BEAT_SCHEDULE, this stamps the current UTC
    time so a crashed/hung beat (no writes) lets the key go stale and the health probe flips
    that subsystem to degraded. The 300s cache timeout is deliberately well above both the
    60s beat cadence and the 180s staleness threshold the probe applies, so a single missed
    beat never trips a false alarm. Uses the SAME Django cache the health check reads.
    """
    from django.core.cache import cache
    from django.utils.timezone import now as _now
    cache.set("celery_beat_heartbeat", _now().isoformat(), timeout=300)


@shared_task(name="accounts.tasks.run_management_command", acks_late=True)
def run_management_command(name, *args, **kwargs):
    """Run a Django management command from Beat (lets Beat own the cron jobs).

    Only commands in ``_MANAGEMENT_COMMAND_ALLOWLIST`` may run. A rejected name is
    logged and dropped WITHOUT raising — raising under acks_late would re-queue the
    poisoned message and spin the worker. The guard lives in the task body so it
    protects both the Celery path and the inline-thread ``enqueue`` fallback.
    """
    if name not in _MANAGEMENT_COMMAND_ALLOWLIST:
        logger.warning("run_management_command refused disallowed command: %r", name)
        return
    from django.core.management import call_command
    call_command(name, *args, **kwargs)


# ── Ride-hailing push tasks ──────────────────────────────────────────────────────

@shared_task(name="accounts.tasks.ride_dispatch_to_drivers", **_RETRY)
def ride_dispatch_to_drivers(ride_id):
    """Push a new ride offer to nearby online car drivers."""
    from accounts.push import notify_car_drivers_new_ride_sync
    notify_car_drivers_new_ride_sync(ride_id)


@shared_task(name="accounts.tasks.ride_notify_rider", **_RETRY)
def ride_notify_rider(rider_id, event):
    """Push a ride status event to the rider."""
    from accounts.push import notify_rider_sync
    notify_rider_sync(rider_id, event)


@shared_task(name="accounts.tasks.campaign_push", **_RETRY)
def campaign_push(customer_id, tenant_name, title, message, url):
    """Send a promotional campaign push to one customer."""
    from accounts.push import send_campaign_push_sync
    send_campaign_push_sync(customer_id, tenant_name, title, message, url)


@shared_task(name="accounts.tasks.campaign_email", **_RETRY)
def campaign_email(customer_id, tenant_name, title, message, tenant_id=None):
    """Send a promotional campaign email to one customer (B1).

    Off the request path (mirrors campaign_push). Re-checks notify_promotions
    and reads the email from the public Customer row, so an opt-out between
    enqueue and delivery still suppresses the message.
    """
    from accounts.push import send_campaign_email_sync
    send_campaign_email_sync(customer_id, tenant_name, title, message, tenant_id)
