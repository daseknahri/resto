"""
Celery tasks for outbound notifications + scheduled jobs, plus the ``enqueue`` helper.

Design goal: the queue must NEVER be load-bearing for the request path. ``enqueue``
runs a task on the worker when a broker is configured, and otherwise falls back to the
historical fire-and-forget daemon thread. So:
  - With Redis + a running worker  → durable, off-process, survives web restarts.
  - Without a broker (dev/local)   → identical to the old behaviour, no worker needed.

Tasks are thin wrappers around the existing synchronous dispatch functions (which already
write NotificationLog rows). ``autoretry_for=(Exception,)`` retries on task-level errors.
SMS transient failures (Twilio 5xx / network) raise ``menu.sms.SmsProviderError`` (a
subclass of Exception) so they are retried automatically; permanent failures (no
credentials, invalid phone) return False without raising and are NOT retried.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from celery import Task, shared_task
from django.conf import settings
from django.db import InterfaceError, OperationalError

logger = logging.getLogger(__name__)

_RETRY = dict(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})

# RISK ASYNC-2: retry policy for the scheduled cron/sweep tasks. Unlike the notification
# tasks (which retry on ANY Exception because a paid send is worth re-attempting), the
# cron tasks retry ONLY on a TRANSIENT DB error — so a brief Postgres blip during a tick
# retries instead of silently dropping it, while a genuine bug in a command still fails
# fast (no 3x re-run of broken logic). Backoff is bounded and jittered so a high-frequency
# sweep (e.g. the 60s sweep_delivery_jobs) can't build a retry storm.
_CRON_RETRY = dict(
    autoretry_for=(OperationalError, InterfaceError),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)

# ── ASYNC-4: send dedupe (idempotent notifications) ──────────────────────────────
# CELERY_TASK_ACKS_LATE is True globally (config/settings.py) and CELERY_TASK_TIME_LIMIT
# hard-kills a stuck send at 120s, so a worker killed mid-send (time-limit / OOM) does
# NOT ack its message → the broker REDELIVERS it → the send runs again. For a paid /
# customer-facing channel (SMS, WhatsApp, order-status push) that means a duplicate the
# customer sees and we pay for. `autoretry_for` can re-run a task the same way.
#
# Guard: claim a one-time send key BEFORE dispatching. The FIRST attempt claims and
# sends; a redelivered / retried duplicate finds the key already claimed and skips. The
# claim is released on an exception so a genuine transient-failure retry (SmsProviderError
# → autoretry) can re-send. cache.add is atomic (SETNX), matching the app's existing
# cache-idempotency pattern. Keys embed the global tenant_id so they can't collide across
# tenant schemas. Fails OPEN: a cache blip must never silently drop a notification.
_DEDUPE_TTL_SECONDS = 3600  # >> the retry window (max_retries=3 w/ backoff) + redelivery
_DEDUPE_PREFIX = "notif-dedupe:"


def _dedupe_key(*parts) -> str:
    return _DEDUPE_PREFIX + ":".join("" if p is None else str(p) for p in parts)


def _claim_send(key: str) -> bool:
    """Atomically claim a one-time send. True → proceed (first claim); False → skip
    (a redelivered/retried duplicate whose original already claimed). Fails OPEN."""
    try:
        from django.core.cache import cache
        return bool(cache.add(key, "1", _DEDUPE_TTL_SECONDS))
    except Exception:
        logger.debug("notification dedupe claim failed; proceeding", exc_info=True)
        return True


def _release_send(key: str) -> None:
    """Release a claim so a transient-failure retry can re-send. Best-effort."""
    try:
        from django.core.cache import cache
        cache.delete(key)
    except Exception:
        logger.debug("notification dedupe release failed", exc_info=True)


class _NotificationTask(Task):
    """Base for customer-facing notification tasks — code-level DLQ alert (RISK ASYNC-4 residual).

    Celery invokes ``on_failure`` ONLY on a terminal failure — i.e. after ``autoretry_for`` has
    exhausted ``max_retries`` — never on an intermediate retry (that's ``on_retry``, which is left
    unoverridden). So this fires exactly once, when a paid / customer-facing send is being dropped
    for good, turning the otherwise-silent ``NotificationLog(status=failed)`` row into a loud ERROR
    that surfaces in ops/error tracking. A true broker dead-letter exchange
    (``task_reject_on_worker_lost`` + a DLX) is deferred infra work; this is the code-level signal.

    PII rule (money/PII logging discipline): NEVER log the task's ``args``/``kwargs`` — they carry
    phone numbers / message bodies. Only the task name + exception TYPE are logged; the correlating
    ``NotificationLog`` row holds the rest.
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(
            "NOTIFICATION DROPPED (retries exhausted): task=%s exc=%s — a customer-facing "
            "notification was NOT delivered; see the NotificationLog(status=failed) row "
            "(args/kwargs omitted — they contain PII). RISK ASYNC-4.",
            self.name, type(exc).__name__,
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)

# ── Inline (no-broker) dispatch pool ────────────────────────────────────────────
# Inline mode is a DEV / DEGRADED fallback only — the durable path is Celery (see R3):
# with a broker configured, ``enqueue`` hands off to a worker and never touches this.
#
# When no broker is set, notifications were historically run by spawning ONE raw daemon
# thread per call. Django opens a fresh DB connection per thread, so a mealtime burst
# (hundreds of concurrent order/notification events) would spawn hundreds of threads +
# Postgres connections at once with NO backpressure — exhausting the connection limit
# and taking the DB down (a self-inflicted outage). A MODULE-LEVEL bounded pool caps
# the concurrency: at most `max_workers` threads (→ connections) run at once, and excess
# work waits in the executor's internal queue instead of fanning out unbounded.
_INLINE_MAX_WORKERS = 4
_inline_executor = ThreadPoolExecutor(
    max_workers=_INLINE_MAX_WORKERS, thread_name_prefix="inline-notify"
)


def enqueue(task, *args, **kwargs) -> None:
    """Dispatch *task* via Celery when a broker is configured, else run it inline on a
    bounded thread pool. Never raises, never blocks the caller.

    Inline mode is a dev/degraded fallback (no broker); the durable path is Celery.
    The bounded pool + its internal queue provide backpressure so a burst cannot spawn
    unbounded threads / DB connections."""
    if getattr(settings, "CELERY_BROKER_URL", ""):
        try:
            task.delay(*args, **kwargs)
            return
        except Exception:  # broker unreachable → don't lose the notification
            logger.warning("Celery enqueue failed for %s; running inline",
                           getattr(task, "name", task), exc_info=True)
    # RISK ASYNC-1: in production this fallback means the work is running in-process
    # with NO durability — it is lost outright on the next deploy/restart, silently,
    # unless something screams about it. config.checks.celery_broker_configured_for_durability
    # blocks a *new* deploy from shipping without a broker (deploy=True check, so it
    # never runs in dev/tests); this log line is the equivalent signal for a box that
    # already booted (e.g. the broker died after startup) so it shows up in prod logs
    # / alerting instead of vanishing quietly.
    if not settings.DEBUG:
        logger.error(
            "PROD inline task fallback: %s is running on the in-process ThreadPoolExecutor "
            "(no durable Celery broker) — this work will be LOST on the next deploy/restart. "
            "Set CELERY_BROKER_URL. (RISK ASYNC-1)",
            getattr(task, "name", task),
        )
    # Submit to the bounded pool (not a raw unbounded Thread): excess work queues
    # instead of opening a connection-per-call all at once.
    _inline_executor.submit(_run_inline, task, args, kwargs)


def _run_inline(task, args, kwargs) -> None:
    try:
        task.run(*args, **kwargs)  # execute the task body directly (no broker)
    except Exception:
        logger.warning("inline task %s failed", getattr(task, "name", task), exc_info=True)
    finally:
        # CRITICAL: pool threads are REUSED across submissions, so a connection opened
        # for this task would otherwise stay open and accumulate (one idle Postgres
        # connection per pool thread, held for the worker's lifetime). Close it so the
        # next task on this thread opens a fresh one and we never leak idle connections.
        try:
            from django.db import connection
            connection.close()
        except Exception:
            logger.debug("inline task connection.close() failed", exc_info=True)


# ── Notification tasks ──────────────────────────────────────────────────────────

@shared_task(name="accounts.tasks.web_push_tenant", acks_late=True, **_RETRY)
def web_push_tenant(schema_name, title, body, url="/owner/orders"):
    from menu.push import _push_to_tenant
    _push_to_tenant(schema_name, title, body, url)


@shared_task(name="accounts.tasks.sms_order_ready", base=_NotificationTask, **_RETRY)
def sms_order_ready(phone, tenant_name, order_number, tenant_id=None):
    key = _dedupe_key("sms:order_ready", tenant_id, order_number, phone)
    if not _claim_send(key):
        logger.info("sms_order_ready deduped (already sent): %s", key)
        return
    from menu.sms import send_order_ready_sms
    try:
        send_order_ready_sms(phone, tenant_name, order_number, tenant_id=tenant_id)
    except Exception:
        _release_send(key)  # transient failure → let autoretry re-send
        raise


@shared_task(name="accounts.tasks.whatsapp_new_order", base=_NotificationTask, **_RETRY)
def whatsapp_new_order(schema_name, order_id, tenant_name, whatsapp_phone, tenant_id=None):
    key = _dedupe_key("whatsapp:new_order", schema_name, order_id)
    if not _claim_send(key):
        logger.info("whatsapp_new_order deduped (already sent): %s", key)
        return
    from django_tenants.utils import schema_context
    from menu.models import Order
    from menu.views import _notify_restaurant_new_order
    try:
        with schema_context(schema_name):
            order = Order.objects.prefetch_related("items").filter(id=order_id).first()
            if order is None:
                return
            _notify_restaurant_new_order(
                order, tenant_name=tenant_name, whatsapp_phone=whatsapp_phone, tenant_id=tenant_id,
            )
    except Exception:
        _release_send(key)  # transient failure → let autoretry re-send
        raise


@shared_task(name="accounts.tasks.charge_request", **_RETRY)
def charge_request(customer_id, restaurant_name, amount):
    """Nudge a customer that they have a wallet charge to approve (money-adjacent,
    request path). Wraps the existing synchronous sender so dispatch goes through the
    bounded ``enqueue`` pool / Celery instead of a raw daemon thread."""
    from accounts.push import _send_charge_request_sync
    _send_charge_request_sync(customer_id, restaurant_name, amount)


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


@shared_task(name="accounts.tasks.customer_order_milestone", base=_NotificationTask, **_RETRY)
def customer_order_milestone(order_number, tenant_id, event):
    key = _dedupe_key("push:milestone", tenant_id, order_number, event)
    if not _claim_send(key):
        logger.info("customer_order_milestone deduped (already sent): %s", key)
        return
    from accounts.push import notify_customer_order_milestone_sync
    try:
        notify_customer_order_milestone_sync(order_number, tenant_id, event)
    except Exception:
        _release_send(key)  # transient failure → let autoretry re-send
        raise


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


# ── Scheduled cron / sweep tasks (RISK ASYNC-2) ──────────────────────────────────
# Each Celery Beat entry dispatches a DEDICATED named "cron.<command>" task rather than
# one generic run_management_command guarded by a parallel allowlist. Consequences:
#   • The task NAME is the allowlist. No task accepts a caller-supplied command name off
#     the (unauthenticated) broker anymore, so the broker can only trigger these exact,
#     fixed commands — the drift-prone _MANAGEMENT_COMMAND_ALLOWLIST is deleted. Each task
#     bakes in its own command name + args; no message field selects what runs.
#   • They route to a dedicated "cron" queue (CELERY_TASK_ROUTES "cron.*") so a slow sweep
#     can't sit ahead of customer-facing sends in the notifications FIFO — see
#     config/celery.py for the worker that must consume BOTH queues (-Q notifications,cron).
#   • _CRON_RETRY (transient-DB retry + backoff) means a brief Postgres blip during a tick
#     retries instead of dropping it. Every command below is idempotent by design
#     (periodic sweep / reconcile / prune), so a retry is always safe.


def _run_command(name, *args, **kwargs):
    """Invoke a Django management command from a cron task (lazy import mirrors the
    historical run_management_command body)."""
    from django.core.management import call_command
    call_command(name, *args, **kwargs)


@shared_task(name="cron.release_scheduled_orders", acks_late=True, **_CRON_RETRY)
def release_scheduled_orders():
    _run_command("release_scheduled_orders")


@shared_task(name="cron.escalate_stale_pending_orders", acks_late=True, **_CRON_RETRY)
def escalate_stale_pending_orders():
    _run_command("escalate_stale_pending_orders")


@shared_task(name="cron.send_predispatch_reminders", acks_late=True, **_CRON_RETRY)
def send_predispatch_reminders():
    _run_command("send_predispatch_reminders")


@shared_task(name="cron.send_ride_predispatch_reminders", acks_late=True, **_CRON_RETRY)
def send_ride_predispatch_reminders():
    _run_command("send_ride_predispatch_reminders")


@shared_task(name="cron.check_car_doc_expiry", acks_late=True, **_CRON_RETRY)
def check_car_doc_expiry():
    _run_command("check_car_doc_expiry")


@shared_task(name="cron.send_review_prompts", acks_late=True, **_CRON_RETRY)
def send_review_prompts():
    _run_command("send_review_prompts")


@shared_task(name="cron.send_reservation_reminders", acks_late=True, **_CRON_RETRY)
def send_reservation_reminders():
    _run_command("send_reservation_reminders")


@shared_task(name="cron.expire_charge_requests", acks_late=True, **_CRON_RETRY)
def expire_charge_requests():
    _run_command("expire_charge_requests")


@shared_task(name="cron.sweep_delivery_jobs", acks_late=True, **_CRON_RETRY)
def sweep_delivery_jobs():
    _run_command("sweep_delivery_jobs")


@shared_task(name="cron.reconcile_driver_earnings", acks_late=True, **_CRON_RETRY)
def reconcile_driver_earnings():
    _run_command("reconcile_driver_earnings")


@shared_task(name="cron.reconcile_wallet_balances", acks_late=True, **_CRON_RETRY)
def reconcile_wallet_balances():
    _run_command("reconcile_wallet_balances")


@shared_task(name="cron.reconcile_order_refs", acks_late=True, **_CRON_RETRY)
def reconcile_order_refs():
    _run_command("reconcile_order_refs")


@shared_task(name="cron.sweep_ride_requests", acks_late=True, **_CRON_RETRY)
def sweep_ride_requests():
    _run_command("sweep_ride_requests")


@shared_task(name="cron.enforce_subscriptions", acks_late=True, **_CRON_RETRY)
def enforce_subscriptions():
    # apply=True was baked in here (was a Beat kwarg) so no message field controls it.
    _run_command("enforce_subscriptions", apply=True)


@shared_task(name="cron.fetch_currency_rates", acks_late=True, **_CRON_RETRY)
def fetch_currency_rates():
    _run_command("fetch_currency_rates")


@shared_task(name="cron.send_daily_summary", acks_late=True, **_CRON_RETRY)
def send_daily_summary():
    _run_command("send_daily_summary")


@shared_task(name="cron.auto_reset_availability", acks_late=True, **_CRON_RETRY)
def auto_reset_availability():
    _run_command("auto_reset_availability")


@shared_task(name="cron.send_winback_nudges", acks_late=True, **_CRON_RETRY)
def send_winback_nudges():
    _run_command("send_winback_nudges")


@shared_task(name="cron.prune_analytics_events", acks_late=True, **_CRON_RETRY)
def prune_analytics_events():
    _run_command("prune_analytics_events")


@shared_task(name="cron.prune_admin_audit_logs", acks_late=True, **_CRON_RETRY)
def prune_admin_audit_logs():
    _run_command("prune_admin_audit_logs")


@shared_task(name="cron.prune_notification_logs", acks_late=True, **_CRON_RETRY)
def prune_notification_logs():
    _run_command("prune_notification_logs")


@shared_task(name="cron.prune_winback_nudges", acks_late=True, **_CRON_RETRY)
def prune_winback_nudges():
    _run_command("prune_winback_nudges")


@shared_task(name="cron.prune_staff_messages", acks_late=True, **_CRON_RETRY)
def prune_staff_messages():
    _run_command("prune_staff_messages")


@shared_task(name="cron.prune_auth_tokens", acks_late=True, **_CRON_RETRY)
def prune_auth_tokens():
    _run_command("prune_auth_tokens")


@shared_task(name="cron.prune_customer_ratings", acks_late=True, **_CRON_RETRY)
def prune_customer_ratings():
    _run_command("prune_customer_ratings")


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


@shared_task(name="accounts.tasks.recipient_track_sms", base=_NotificationTask, **_RETRY)
def recipient_track_sms(ride_id, event):
    """SMS the package recipient their public tracking link (dispatched | in_progress)."""
    key = _dedupe_key("sms:track", ride_id, event)
    if not _claim_send(key):
        logger.info("recipient_track_sms deduped (already sent): %s", key)
        return
    from accounts.push import send_recipient_track_sms_sync
    try:
        send_recipient_track_sms_sync(ride_id, event)
    except Exception:
        _release_send(key)  # transient failure → let autoretry re-send
        raise


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
