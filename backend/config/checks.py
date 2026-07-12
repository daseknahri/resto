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
from urllib.parse import urlparse

from django.conf import settings
from django.core.checks import Error, Warning, register


@register(deploy=True)
def redis_and_celery_configured(app_configs, **kwargs):
    """In production REDIS_URL is REQUIRED (cache + channel layer). Missing Redis is
    an Error (broken realtime on multi-worker prod).

    The Celery-broker half of this used to live here too (kepoli.W001, a Warning).
    RISK ASYNC-1 replaced it with ``celery_broker_configured_for_durability`` below,
    which is an Error (kepoli.E002) instead of a Warning — see that function for why.
    """
    if settings.DEBUG:
        return []

    issues = []
    redis_url = os.getenv("REDIS_URL", "").strip()

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

    return issues


@register(deploy=True)
def celery_broker_configured_for_durability(app_configs, **kwargs):
    """RISK ASYNC-1: accounts.tasks.enqueue() falls back to an in-process
    ThreadPoolExecutor whenever ``settings.CELERY_BROKER_URL`` is unset — so every
    notification / scheduled job in flight is silently LOST on each deploy or worker
    restart (no durability, no operator-visible signal). enqueue() also lands here on
    a broker hiccup (``.delay()`` raising), but that path is transient by nature and
    deliberately NOT hard-failed at runtime — a broker blip must never turn into a
    user-facing 500. A *permanently* missing broker in production, however, is a
    misconfiguration we can and should catch before it ships, so it is an Error here
    at deploy time instead.

    This supersedes the old kepoli.W001 Warning on ``redis_and_celery_configured``
    above: the identical condition is now an Error, so
    ``check --deploy --fail-level ERROR`` (docker/entrypoint.sh) refuses to boot a
    build that would silently run production on the lossy inline fallback. Escape
    hatch: SKIP_DEPLOY_CHECK=1 on the entrypoint, same as kepoli.E001.

    Reads ``settings.CELERY_BROKER_URL`` (not ``os.environ``, unlike the checks
    above) so it mirrors EXACTLY the condition ``accounts.tasks.enqueue()`` branches
    on at runtime.
    """
    if settings.DEBUG:
        return []

    if getattr(settings, "CELERY_BROKER_URL", ""):
        return []

    return [Error(
        "CELERY_BROKER_URL is not set in production.",
        hint=(
            "Without a broker, accounts.tasks.enqueue() dispatches every notification / "
            "scheduled job inline on an in-process ThreadPoolExecutor — that queued work "
            "is silently LOST on every deploy or worker restart (RISK ASYNC-1). Set "
            "CELERY_BROKER_URL (typically = REDIS_URL) and run a worker "
            "(celery -A config worker) + Beat before shipping. Bypass only in an emergency "
            "with SKIP_DEPLOY_CHECK=1 on the entrypoint."
        ),
        id="kepoli.E002",
    )]


@register(deploy=True)
def redis_has_auth_credentials(app_configs, **kwargs):
    """A6: in production the REDIS_URL must carry authentication credentials.

    An unauthenticated Redis instance holding session data, OTP guards,
    idempotency-key mutexes, and channel state with real money flowing is a
    defence-in-depth failure.  Set Redis requirepass (or a Redis 6+ ACL user)
    and include the credentials in REDIS_URL: redis://:yourpassword@host:port/db.
    """
    if settings.DEBUG:
        return []

    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return []  # Already caught by kepoli.E001.

    try:
        parsed = urlparse(redis_url)
        has_password = bool(parsed.password)
    except Exception:
        has_password = False

    if not has_password:
        return [Warning(
            "REDIS_URL has no password in production.",
            hint=(
                "An unauthenticated Redis instance holding session data, OTP "
                "guards, idempotency-key mutexes, and channel-layer state is a "
                "security risk once real money flows through the system. "
                "Enable Redis requirepass (or a Redis 6+ ACL user) and include "
                "the credentials in REDIS_URL: redis://:yourpassword@host:port/db."
            ),
            id="kepoli.W002",
        )]
    return []
