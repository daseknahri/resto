"""
Delivery-fee pricing — shared by both checkout paths (menu + marketplace) and
the customer-facing fee preview.

Pricing model (decided with the owner): **per-restaurant distance pricing**.

    fee = delivery_base_fee + delivery_per_km × distance_km

where ``distance_km`` is the straight-line (haversine) distance from the
restaurant's coordinates to the delivery address. When distance pricing is not
configured (``delivery_per_km`` == 0) or coordinates are missing, the flat
``delivery_fee`` is used as a fallback so existing restaurants keep working.

The driver keeps 100% of the delivery fee (``driver_payout = delivery_fee``).

This module has **no Django imports** beyond Decimal helpers so it stays cheap
to import and trivial to unit-test.
"""
from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP

# Earth radius in km (mean).
_EARTH_KM = 6371.0088
_CENT = Decimal("0.01")
# A delivery farther than this is almost certainly a bad/foreign coordinate — refuse it so
# bogus lat/lng can't compute an absurd fee (used even when no per-restaurant radius is set).
MAX_PLAUSIBLE_KM = 100.0


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    """Great-circle distance in km between two lat/lng points.

    Returns 0.0 if any coordinate is missing/unparseable.
    """
    try:
        rlat1, rlng1, rlat2, rlng2 = (
            math.radians(float(lat1)),
            math.radians(float(lng1)),
            math.radians(float(lat2)),
            math.radians(float(lng2)),
        )
    except (TypeError, ValueError):
        return 0.0
    dlat = rlat2 - rlat1
    dlng = rlng2 - rlng1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    )
    return _EARTH_KM * 2 * math.asin(min(1.0, math.sqrt(a)))


def _dec(value) -> Decimal:
    """Best-effort Decimal coercion; treats junk as 0."""
    try:
        if value in (None, ""):
            return Decimal("0")
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def compute_delivery_fee(profile, *, distance_km=None, food_subtotal=Decimal("0")) -> dict:
    """Compute the delivery fee for an order.

    Args:
        profile: the restaurant Profile (reads delivery_base_fee, delivery_per_km,
            delivery_free_over, delivery_fee, delivery_radius_km).
        distance_km: straight-line km from restaurant → delivery address, or None
            when coordinates are unavailable.
        food_subtotal: order subtotal (Decimal) used for the free-over threshold.

    Returns a dict:
        {
          "fee": Decimal,            # amount to charge (0 when free / out of range)
          "distance_km": float|None, # echoed distance (rounded 1dp) or None
          "out_of_range": bool,      # True → address beyond delivery_radius_km
          "free": bool,              # True → free because subtotal ≥ free_over
          "mode": "distance"|"flat", # which pricing model was applied
        }
    """
    base = _dec(getattr(profile, "delivery_base_fee", 0))
    per_km = _dec(getattr(profile, "delivery_per_km", 0))
    flat = _dec(getattr(profile, "delivery_fee", 0))
    free_over = _dec(getattr(profile, "delivery_free_over", 0))
    subtotal = _dec(food_subtotal)

    radius = getattr(profile, "delivery_radius_km", None)
    try:
        radius = float(radius) if radius not in (None, "") else None
    except (TypeError, ValueError):
        radius = None

    dist = None
    if distance_km is not None:
        try:
            dist = round(float(distance_km), 1)
        except (TypeError, ValueError):
            dist = None

    # 1) Out-of-range guard: beyond the restaurant's radius, OR an implausibly far point
    #    (bogus coordinates) even when no radius is configured — never bill a wild fee.
    _out = dist is not None and (
        (radius and dist > radius) or dist > MAX_PLAUSIBLE_KM
    )
    if _out:
        return {
            "fee": Decimal("0.00"),
            "distance_km": dist,
            "out_of_range": True,
            "free": False,
            "mode": "distance" if per_km > 0 else "flat",
        }

    # 2) Free over threshold (applies regardless of pricing mode).
    if free_over > 0 and subtotal >= free_over:
        return {
            "fee": Decimal("0.00"),
            "distance_km": dist,
            "out_of_range": False,
            "free": True,
            "mode": "distance" if per_km > 0 else "flat",
        }

    # 3) Distance pricing when configured AND distance known; else flat fallback.
    if per_km > 0 and dist is not None:
        fee = (base + per_km * Decimal(str(dist))).quantize(_CENT, rounding=ROUND_HALF_UP)
        mode = "distance"
    else:
        # Flat fallback. When distance pricing IS configured (per_km>0) but the distance is
        # unknown (no coordinates), fall back to the larger of the flat fee and the base fee
        # so a restaurant that only set a base never silently delivers for free.
        fee = (max(flat, base) if per_km > 0 else flat).quantize(_CENT, rounding=ROUND_HALF_UP)
        mode = "flat"

    if fee < 0:
        fee = Decimal("0.00")

    return {
        "fee": fee,
        "distance_km": dist,
        "out_of_range": False,
        "free": False,
        "mode": mode,
    }
