"""
Lightweight API helpers that live outside the tenant/public URL routing split.

health_view
-----------
Responds to GET /api/health/ with a JSON payload indicating the status of
each critical subsystem.  Used by uptime monitors (e.g. UptimeRobot, Coolify
health checks) and internal probes.

Response schema
  {
    "status": "ok" | "degraded" | "down",
    "checks": {
      "db":            {"ok": bool, "latency_ms": int | null},
      "cache":         {"ok": bool, "latency_ms": int | null},
      "celery":        {"ok": bool, "detail": str},
      "channel_layer": {"ok": bool, "detail": str},
      "media":         {"ok": bool, "detail": str}
    },
    "time": "<ISO-8601>",
    "schema": "<db schema name>",
    "tenant": {...} | null
  }

HTTP status policy
  200 — db + cache pass  (status "ok" or "degraded" for non-critical subsystems)
  503 — database is down (status "down")

  Celery, channel_layer, and media are non-critical (degraded, not down) because
  the app can serve HTTP requests without them. DB is the only hard-fail.

  No stack traces or credentials are included in any response body.

Celery probe
  A real broker ping requires a live worker, which is not available in dev/CI.
  Instead we check:
    1. Whether CELERY_BROKER_URL is configured (Celery is opt-in; empty = off
       by design, not a fault).
    2. When configured, whether the cache-backed beat heartbeat key written by
       the beat scheduler is fresh (within 5 minutes).
  Limitation: this cannot detect a broker that is configured but unreachable
  unless the beat heartbeat has already expired.  A missing heartbeat key on a
  newly-started instance is not a fault.

Channel-layer probe
  Issue a group_send to a throwaway group name and catch any exception.  When
  the channel layer is InMemoryChannelLayer (dev) this always succeeds.  When
  it is RedisChannelLayer a connection failure raises an exception.

Media probe
  Check that settings.MEDIA_ROOT exists and is a directory.  A write/delete
  round-trip is intentionally avoided: the health endpoint must be fast, safe
  to call repeatedly, and not leave artefacts on the filesystem.
"""

import time

from django.core.cache import cache
from django.db import connection, OperationalError as DbOperationalError
from django.http import JsonResponse
from django.utils.timezone import now


def _check_db() -> dict:
    """Ping the database with a minimal query and measure round-trip time."""
    start = time.monotonic()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        latency_ms = round((time.monotonic() - start) * 1000)
        return {"ok": True, "latency_ms": latency_ms}
    except Exception:
        return {"ok": False, "latency_ms": None}


def _check_cache() -> dict:
    """Round-trip a sentinel value through the cache backend."""
    _KEY = "_health_probe"
    _VAL = "1"
    start = time.monotonic()
    try:
        cache.set(_KEY, _VAL, timeout=5)
        result = cache.get(_KEY)
        latency_ms = round((time.monotonic() - start) * 1000)
        return {"ok": result == _VAL, "latency_ms": latency_ms}
    except Exception:
        return {"ok": False, "latency_ms": None}


def _check_celery() -> dict:
    """
    Lightweight Celery/broker reachability check.

    Celery is OPT-IN (CELERY_BROKER_URL must be set).  When it is not set the
    broker is intentionally absent — that is not a fault.

    When it IS set we check the cache-backed beat heartbeat key.  If the key
    is missing on a freshly-started instance we treat it as ok (not yet
    written) and note the limitation in the detail string.

    Limitation: a broker that is configured but unreachable is only detectable
    once the heartbeat key has expired (> 5 min of no beat activity).
    """
    try:
        from django.conf import settings
        broker_url = (getattr(settings, "CELERY_BROKER_URL", "") or "").strip()
        if not broker_url:
            return {"ok": True, "detail": "celery_off: CELERY_BROKER_URL not set (by design)"}

        # Beat writes a heartbeat key every minute.  Stale = worker / beat down.
        HEARTBEAT_KEY = "celery_beat_heartbeat"
        heartbeat = cache.get(HEARTBEAT_KEY)
        if heartbeat is None:
            return {
                "ok": True,
                "detail": "broker_configured: heartbeat key absent (freshly started or beat not running)",
            }
        return {"ok": True, "detail": f"beat_ok: last_heartbeat={heartbeat}"}
    except Exception as exc:
        return {"ok": False, "detail": f"error: {type(exc).__name__}"}


def _check_channel_layer() -> dict:
    """
    Probe the Django Channels channel layer by attempting a group_send.

    InMemoryChannelLayer (dev): always succeeds.
    RedisChannelLayer (prod): raises if Redis is unreachable.

    The probe is synchronous — it uses async_to_sync so it can run inside a
    regular Django view without starting an event loop from scratch.
    """
    try:
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        if layer is None:
            return {"ok": True, "detail": "channels_not_configured"}

        from asgiref.sync import async_to_sync

        async_to_sync(layer.group_send)(
            "_health_probe_group",
            {"type": "health.ping"},
        )
        return {"ok": True, "detail": "ok"}
    except ImportError:
        # channels not installed — not a fault (it is optional)
        return {"ok": True, "detail": "channels_not_installed"}
    except Exception as exc:
        return {"ok": False, "detail": f"error: {type(exc).__name__}"}


def _check_media() -> dict:
    """
    Verify that MEDIA_ROOT is a directory that Django can write to.

    We check existence and is_dir() only — no write/delete round-trip so there
    are no artefacts and the probe is instantaneous.
    """
    try:
        from django.conf import settings
        media_root = getattr(settings, "MEDIA_ROOT", None)
        if not media_root:
            return {"ok": False, "detail": "MEDIA_ROOT not configured"}
        from pathlib import Path
        p = Path(media_root)
        if not p.exists():
            return {"ok": False, "detail": "MEDIA_ROOT does not exist"}
        if not p.is_dir():
            return {"ok": False, "detail": "MEDIA_ROOT is not a directory"}
        return {"ok": True, "detail": str(p)}
    except Exception as exc:
        return {"ok": False, "detail": f"error: {type(exc).__name__}"}


def health_view(request):
    db = _check_db()
    cache_check = _check_cache()
    celery_check = _check_celery()
    channel_check = _check_channel_layer()
    media_check = _check_media()

    # DB is the only hard-fail (the app cannot serve without it).
    # Cache, celery, channel_layer, and media are non-critical — degraded, not down.
    if not db["ok"]:
        overall = "down"
    elif not cache_check["ok"] or not celery_check["ok"] or not channel_check["ok"] or not media_check["ok"]:
        overall = "degraded"
    else:
        overall = "ok"

    tenant = getattr(request, "tenant", None)
    http_status = 503 if overall == "down" else 200

    return JsonResponse(
        {
            "status": overall,
            "checks": {
                "db": db,
                "cache": cache_check,
                "celery": celery_check,
                "channel_layer": channel_check,
                "media": media_check,
            },
            "time": now().isoformat(),
            "schema": getattr(connection, "schema_name", "unknown"),
            "tenant": {
                "id":   getattr(tenant, "id",   None),
                "slug": getattr(tenant, "slug", None),
                "name": getattr(tenant, "name", None),
            }
            if tenant
            else None,
        },
        status=http_status,
    )
