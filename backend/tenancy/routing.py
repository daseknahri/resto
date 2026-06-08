"""
Road-distance routing — a pluggable seam over the pure ``delivery_pricing``
haversine helper.

Why this module exists
----------------------
``delivery_pricing.haversine_km`` returns the *straight-line* great-circle
distance. Real delivery fees should follow the **road** a driver actually
drives, which is typically ~1.3–1.4× the straight-line distance in a city.

``road_distance_km()`` is the single place the rest of the app asks "how far is
this delivery, by road?". It is **pluggable**:

* **No infra (default).** Multiply the haversine distance by ``ROAD_FACTOR``
  (env ``DELIVERY_ROAD_FACTOR``, default ``1.3``). Zero dependencies, instantly
  more accurate than straight-line, and good enough for fee estimation.

* **Real routing engine (opt-in).** Set ``DELIVERY_OSRM_URL`` to a running
  `OSRM <https://project-osrm.org/>`_ instance (self-hosted on a cheap VPS with
  a country OSM extract → unlimited, free, owned) and this module fetches the
  real driving distance from its ``/route`` API, caches it, and falls back to
  the road-factor on any error/timeout. The same seam will later power
  driver-assignment matrices and ride-hailing routing.

Switching engines is **one env var** — no code change at the call sites.

Keep this module dependency-light: ``requests`` and the Django cache are
imported lazily inside the OSRM branch so the default (factor) path has no
import cost and is trivially unit-testable.
"""
from __future__ import annotations

import logging
import os

from .delivery_pricing import haversine_km

logger = logging.getLogger(__name__)

# Default multiplier applied to straight-line distance to approximate road
# distance when no routing engine is configured. ~1.3 is a widely used urban
# detour factor (Google/Mapbox/OSRM road distances run ~1.3–1.4× crow-flies).
DEFAULT_ROAD_FACTOR = 1.3
# Cache real routing results for a week — road distance between two fixed points
# does not change. Keyed on coords rounded to ~11 m so repeat addresses dedupe.
_ROUTE_CACHE_TTL = 7 * 24 * 3600
_OSRM_TIMEOUT = 4  # seconds; on timeout we fall back to the factor, never block checkout
# Average urban driving speed (km/h) for the ETA estimate when no engine returns a
# real duration. ~22 km/h matches the customer-tracker's previous straight-line guess.
AVG_SPEED_KMH = 22.0
# Live-route geometry is cached on coarser (~110 m) coords so a moving driver only
# triggers a recompute every ~100 m, not on every position poll.
_GEOM_CACHE_TTL = 24 * 3600


def _eta_minutes(distance_km) -> int:
    """Rough driving ETA (minutes, floored at 1) for a distance at AVG_SPEED_KMH."""
    try:
        km = float(distance_km)
    except (TypeError, ValueError):
        return 1
    if km <= 0:
        return 1
    return max(1, round(km / AVG_SPEED_KMH * 60.0))


def road_factor() -> float:
    """The straight-line→road multiplier (env ``DELIVERY_ROAD_FACTOR``).

    Read at call time so it can be tuned/tested without reimport. Falls back to
    :data:`DEFAULT_ROAD_FACTOR` for missing/garbage values; never returns < 1.0
    (road distance is never shorter than crow-flies).
    """
    try:
        f = float(os.environ.get("DELIVERY_ROAD_FACTOR", "") or DEFAULT_ROAD_FACTOR)
    except (TypeError, ValueError):
        f = DEFAULT_ROAD_FACTOR
    return f if f >= 1.0 else DEFAULT_ROAD_FACTOR


def _osrm_base_url() -> str:
    """Configured OSRM base URL (``DELIVERY_OSRM_URL``), trimmed, or ""."""
    return (os.environ.get("DELIVERY_OSRM_URL", "") or "").strip().rstrip("/")


def _factor_distance(lat1, lng1, lat2, lng2) -> float:
    """Straight-line distance × road factor, rounded to 2 dp (>= 0)."""
    straight = haversine_km(lat1, lng1, lat2, lng2)
    if not straight:  # 0.0 → same point / unparseable coords
        return 0.0
    return round(straight * road_factor(), 2)


def _osrm_distance_km(base_url, lat1, lng1, lat2, lng2):
    """Real driving distance (km) from an OSRM ``/route`` call, or None on failure.

    Cached on rounded coordinates. Any network/parse error returns None so the
    caller falls back to the road-factor estimate — routing must never block or
    break checkout.
    """
    # ~4 decimals ≈ 11 m precision: tight enough to be accurate, loose enough that
    # the same restaurant→address pair reuses one cached result.
    try:
        key = "osrm:{:.4f},{:.4f}:{:.4f},{:.4f}".format(
            float(lat1), float(lng1), float(lat2), float(lng2)
        )
    except (TypeError, ValueError):
        return None

    try:
        from django.core.cache import cache
    except Exception:  # pragma: no cover - Django always present in app runtime
        cache = None

    if cache is not None:
        try:
            cached = cache.get(key)
        except Exception:
            cached = None
        if cached is not None:
            return cached

    try:
        import requests
    except Exception:  # pragma: no cover - requests is a project dependency
        return None

    # OSRM expects {lng},{lat};{lng},{lat} (longitude first).
    url = "{}/route/v1/driving/{},{};{},{}".format(base_url, lng1, lat1, lng2, lat2)
    try:
        resp = requests.get(url, params={"overview": "false"}, timeout=_OSRM_TIMEOUT)
        if not resp.ok:
            return None
        data = resp.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            return None
        meters = data["routes"][0].get("distance")
        if meters is None:
            return None
        km = round(float(meters) / 1000.0, 2)
    except Exception as exc:  # network error, timeout, bad JSON, etc.
        logger.warning("OSRM routing failed (%s); falling back to road factor", exc)
        return None

    if cache is not None:
        try:
            cache.set(key, km, _ROUTE_CACHE_TTL)
        except Exception:
            pass
    return km


def road_distance_km(lat1, lng1, lat2, lng2) -> float:
    """Estimated **driving** distance in km between two lat/lng points.

    Uses a configured OSRM engine (``DELIVERY_OSRM_URL``) when available — with
    caching and a hard timeout — and otherwise falls back to
    ``haversine × DELIVERY_ROAD_FACTOR``. Always returns a non-negative float
    (``0.0`` for the same point or unparseable coords); never raises.

    This is a drop-in replacement for ``haversine_km`` at fee-calculation call
    sites: it yields a more realistic distance today and a *real* road distance
    the moment a routing engine is pointed at it — no caller changes needed.
    """
    base_url = _osrm_base_url()
    if base_url:
        km = _osrm_distance_km(base_url, lat1, lng1, lat2, lng2)
        if km is not None:
            return km
    return _factor_distance(lat1, lng1, lat2, lng2)


def _osrm_route(base_url, lat1, lng1, lat2, lng2):
    """Full driving route from OSRM: {"geometry": [[lat,lng],...], "distance_km",
    "duration_min"} or None on failure. Cached on coarse (~110 m) coords."""
    try:
        key = "osrmgeom:{:.3f},{:.3f}:{:.3f},{:.3f}".format(
            float(lat1), float(lng1), float(lat2), float(lng2)
        )
    except (TypeError, ValueError):
        return None

    try:
        from django.core.cache import cache
    except Exception:  # pragma: no cover
        cache = None
    if cache is not None:
        try:
            cached = cache.get(key)
        except Exception:
            cached = None
        if cached is not None:
            return cached

    try:
        import requests
    except Exception:  # pragma: no cover
        return None

    url = "{}/route/v1/driving/{},{};{},{}".format(base_url, lng1, lat1, lng2, lat2)
    try:
        resp = requests.get(
            url, params={"overview": "full", "geometries": "geojson"}, timeout=_OSRM_TIMEOUT
        )
        if not resp.ok:
            return None
        data = resp.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            return None
        route = data["routes"][0]
        # GeoJSON coordinates are [lng, lat]; the map wants [lat, lng].
        coords = route.get("geometry", {}).get("coordinates") or []
        geometry = [[float(c[1]), float(c[0])] for c in coords if len(c) >= 2]
        km = round(float(route.get("distance", 0)) / 1000.0, 2)
        dur = max(1, round(float(route.get("duration", 0)) / 60.0))
        out = {"geometry": geometry, "distance_km": km, "duration_min": dur}
    except Exception as exc:
        logger.warning("OSRM route failed (%s); falling back to a straight line", exc)
        return None

    if cache is not None:
        try:
            cache.set(key, out, _GEOM_CACHE_TTL)
        except Exception:
            pass
    return out


def road_route(lat1, lng1, lat2, lng2) -> dict:
    """Driving route geometry + distance + ETA from point 1 → point 2, for drawing a
    live delivery line on the map and showing a real ETA.

    Returns::

        {"geometry": [[lat, lng], ...], "distance_km": float, "duration_min": int}

    With a routing engine configured (``DELIVERY_OSRM_URL``) this is the real street
    route (cached). Otherwise it's a **straight two-point line** with a road-factor
    distance and a speed-based ETA — so the map always has something to draw and the
    upgrade to real routes is a single env var. Never raises; ``geometry`` is ``[]``
    only when the coordinates are unusable.
    """
    from .delivery_pricing import valid_coord

    if not (valid_coord(lat1, lng1) and valid_coord(lat2, lng2)):
        return {"geometry": [], "distance_km": 0.0, "duration_min": 0}

    base_url = _osrm_base_url()
    if base_url:
        data = _osrm_route(base_url, lat1, lng1, lat2, lng2)
        if data is not None:
            return data

    # Fallback: straight line, road-factor distance, speed-based ETA.
    km = _factor_distance(lat1, lng1, lat2, lng2)
    return {
        "geometry": [[float(lat1), float(lng1)], [float(lat2), float(lng2)]],
        "distance_km": km,
        "duration_min": _eta_minutes(km),
    }
