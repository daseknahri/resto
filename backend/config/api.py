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
      "db": {"ok": bool, "latency_ms": int | null},
      "cache": {"ok": bool, "latency_ms": int | null}
    },
    "time": "<ISO-8601>",
    "schema": "<db schema name>",
    "tenant": {...} | null
  }

HTTP status:
  200 — all checks pass  (status = "ok")
  200 — partial failure  (status = "degraded", non-critical subsystem down)
  503 — database down    (status = "down")
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


def health_view(request):
    db = _check_db()
    cache_check = _check_cache()

    if not db["ok"]:
        overall = "down"
    elif not cache_check["ok"]:
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
