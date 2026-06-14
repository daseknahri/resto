"""Deployment system checks (A7).

Fail a misconfigured PRODUCTION deploy loudly instead of letting it silently
degrade to in-process cache / channel layer / inline task queue — which would
lose money-adjacent events (live order/paid broadcasts, in-flight notifications)
on a multi-worker prod box.

These are Django deploy checks (``register(deploy=True)``), surfaced by
``python manage.py check --deploy``. The container entrypoint runs that with
``--fail-level ERROR`` before starting the server, so a prod deploy without Redis
hard-fails (Coolify keeps the old healthy container) rather than coming up broken.

In DEBUG (dev / test) the in-memory fallbacks are intentional, so every check
here returns nothing.
"""
import os

from django.conf import settings
from django.core.checks import Error, Warning, register


@register(deploy=True)
def redis_and_celery_configured(app_configs, **kwargs):
    """In production REDIS_URL is REQUIRED (cache + channel layer); CELERY_BROKER_URL
    is recommended (durable task queue). Missing Redis is an Error (broken realtime
    on multi-worker prod); missing broker is a Warning (degraded-but-functional
    inline-thread mode — kept opt-in by design)."""
    if settings.DEBUG:
        return []

    issues = []
    redis_url = os.getenv("REDIS_URL", "").strip()
    broker_url = os.getenv("CELERY_BROKER_URL", "").strip()

    if not redis_url:
        issues.append(Error(
            "REDIS_URL is not set in production.",
            hint=(
                "Without REDIS_URL the cache falls back to in-process LocMemCache and the "
                "channel layer to InMemoryChannelLayer, so a broadcast from one web worker "
                "never reaches sockets on another worker — live order/paid updates are lost "
                "on multi-worker prod, and the cache (idempotency mutexes, throttles, OTP "
                "guards) is not shared. Set REDIS_URL (and CELERY_BROKER_URL to the same "
                "Redis). Bypass only in an emergency single-process deploy with "
                "SKIP_DEPLOY_CHECK=1 on the entrypoint."
            ),
            id="kepoli.E001",
        ))

    if not broker_url:
        issues.append(Warning(
            "CELERY_BROKER_URL is not set in production.",
            hint=(
                "The durable task queue is OFF, so accounts.tasks.enqueue() runs work inline "
                "in a daemon thread with no retry — in-flight notifications are dropped on a "
                "restart. Set CELERY_BROKER_URL (typically = REDIS_URL) AND run a worker "
                "(celery -A config worker) + Beat to make notifications durable."
            ),
            id="kepoli.W001",
        ))

    return issues
