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
       by design, not a fault — always ok).
    2. When configured, whether the cache-backed beat heartbeat key written by
       accounts.tasks.write_beat_heartbeat (every ~60s) is fresh. A MISSING or
       STALE heartbeat (older than ~180s) once the process is past its startup
       grace means beat/worker is down -> ok=False (degraded, non-critical).
  A missing heartbeat during the post-boot startup grace is tolerated (the first
  beat may not have landed yet) so a fresh deploy never produces a false alarm.

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

# Process start (monotonic). Used as the health "start_period" grace: right after a fresh
# deploy the beat may not have written its first heartbeat yet, so a missing key during the
# grace window is NOT a fault. Once the process has been up longer than the grace, a missing
# or stale heartbeat means beat/worker is down -> degraded.
_PROCESS_START_MONOTONIC = time.monotonic()

# A heartbeat older than this (or absent past the grace window) means beat/worker is dead.
# Beat writes every 60s, so 180s tolerates two missed beats before flagging.
_CELERY_HEARTBEAT_STALE_SECONDS = 180
# Grace after process boot before a missing/stale heartbeat is treated as a fault. Kept
# above the staleness threshold so the first beat (within 60s) always lands before the
# grace expires — a fresh deploy can never produce a false "degraded".
_CELERY_HEARTBEAT_START_GRACE_SECONDS = 240


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


def _heartbeat_age_seconds(heartbeat) -> float | None:
    """Seconds since *heartbeat* (an ISO-8601 string or epoch number), or None if unparseable.

    The beat task writes ``now().isoformat()``; we also accept a bare epoch number for
    forward-compatibility. A negative age (clock skew) is clamped to 0.
    """
    if heartbeat is None:
        return None
    try:
        if isinstance(heartbeat, (int, float)):
            ts = float(heartbeat)
        else:
            from datetime import datetime
            ts = datetime.fromisoformat(str(heartbeat)).timestamp()
    except (ValueError, TypeError, OverflowError):
        return None
    from django.utils.timezone import now as _now
    age = _now().timestamp() - ts
    return max(0.0, age)


def _check_celery() -> dict:
    """
    Lightweight Celery/broker reachability check.

    Celery is OPT-IN (CELERY_BROKER_URL must be set).  When it is not set the
    broker is intentionally absent — that is not a fault, and we return ok with a
    ``celery_off`` detail (preserved verbatim so dev / no-broker prod-fallback never
    flips to degraded).

    When it IS set we check the cache-backed beat heartbeat key written by
    accounts.tasks.write_beat_heartbeat (every ~60s):
      * During the post-boot grace window a missing/stale key is tolerated (the first
        beat may not have landed yet) -> ok.
      * Once the process has been up past the grace, a MISSING or STALE heartbeat
        (older than the staleness threshold) means beat/worker is dead -> ok=False
        (the response treats celery as non-critical, so overall status is "degraded").
    """
    try:
        from django.conf import settings
        broker_url = (getattr(settings, "CELERY_BROKER_URL", "") or "").strip()
        if not broker_url:
            return {"ok": True, "detail": "celery_off: CELERY_BROKER_URL not set (by design)"}

        # The heartbeat is a CROSS-PROCESS signal: beat writes it, this web process reads it.
        # That only works through a SHARED cache (Redis). If the cache is a per-process
        # LocMemCache (e.g. an emergency SKIP_DEPLOY_CHECK single-process deploy where
        # CELERY_BROKER_URL is set but REDIS_URL is not, so CACHES fell back to locmem), the
        # web process can NEVER see beat's heartbeat — absence is not evidence of a dead beat,
        # so do not false-flag. (Normal prod can't hit this: kepoli.E001 hard-fails a
        # DEBUG=False boot without REDIS_URL.)
        cache_backend = str(
            (getattr(settings, "CACHES", {}).get("default", {}) or {}).get("BACKEND", "")
        ).lower()
        if "locmem" in cache_backend:
            return {"ok": True, "detail": "broker_configured: heartbeat unavailable (per-process cache; needs shared Redis)"}

        # Beat writes a heartbeat key every minute.  Stale/absent = worker / beat down.
        HEARTBEAT_KEY = "celery_beat_heartbeat"
        heartbeat = cache.get(HEARTBEAT_KEY)
        in_grace = (time.monotonic() - _PROCESS_START_MONOTONIC) < _CELERY_HEARTBEAT_START_GRACE_SECONDS

        if heartbeat is None:
            # Within the boot grace, an absent key is just "not written yet" — not a fault.
            if in_grace:
                return {
                    "ok": True,
                    "detail": "broker_configured: heartbeat key absent (within startup grace)",
                }
            return {
                "ok": False,
                "detail": "beat_down: heartbeat key absent past startup grace (beat/worker not running)",
            }

        age = _heartbeat_age_seconds(heartbeat)
        if age is None:
            # Key exists but is unparseable — treat as present (don't flap on a bad value).
            return {"ok": True, "detail": f"beat_ok: last_heartbeat={heartbeat}"}
        if age > _CELERY_HEARTBEAT_STALE_SECONDS and not in_grace:
            return {
                "ok": False,
                "detail": f"beat_stale: last_heartbeat={heartbeat} age={round(age)}s (beat/worker down?)",
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
        # Do NOT return the absolute path — it leaks server filesystem layout
        # to unauthenticated callers. Return a plain boolean instead.
        return {"ok": True, "detail": True}
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
