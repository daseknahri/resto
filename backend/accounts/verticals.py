"""
Canonical vertical taxonomy — the single source of truth for Kepoli's super-app
verticals. See KEPOLI_ACCOUNT_ARCHITECTURE.md §3.

A "vertical" is a consumer-facing service line. It is derived from the tenant's
``business_type`` (food / shops / pharmacy), the ride ``kind`` (rides / courier),
or the driver flag (driver). This module is the ONE place that maps those inputs
to a vertical, so order indexing, wallet tagging, and the frontend all agree.

Money-movement rows with no consumer vertical (top-up, transfer, adjustment,
bonus) are tagged ``None`` and treated as global in spend views — that is
expected, not a gap.

Mirrored on the frontend by ``frontend/src/lib/verticals.js`` — keep in sync.
The token set here intentionally matches the live ``VERTICALS_ENABLED`` env
default (``food,shops,pharmacy,courier,driver``) and the ``services.js`` registry
ids, so this module does not redefine or break either.
"""
from __future__ import annotations

# ── Consumer-facing verticals ────────────────────────────────────────────────
FOOD = "food"
SHOPS = "shops"
PHARMACY = "pharmacy"
RIDES = "rides"
COURIER = "courier"
DRIVER = "driver"

ALL_VERTICALS = (FOOD, SHOPS, PHARMACY, RIDES, COURIER, DRIVER)

# tenancy.Profile.business_type → consumer vertical.
# pharmacy is its OWN vertical token (it is a separate token in VERTICALS_ENABLED
# and the services.js registry), NOT folded into shops.
_BUSINESS_TYPE_TO_VERTICAL = {
    "restaurant": FOOD,
    "cafe": FOOD,
    "bakery": SHOPS,
    "grocery": SHOPS,
    "retail": SHOPS,
    "pharmacy": PHARMACY,
}


def vertical_for_business_type(business_type) -> str:
    """Map a tenant ``business_type`` to its consumer vertical.

    Unknown / blank → ``FOOD`` (matches the platform's restaurant-first default
    posture, where a missing business_type is treated as a restaurant)."""
    if not business_type:
        return FOOD
    return _BUSINESS_TYPE_TO_VERTICAL.get(str(business_type).strip().lower(), FOOD)


def vertical_for_ride_kind(kind) -> str:
    """``RideRequest.kind`` ('ride' | 'package') → vertical ('rides' | 'courier')."""
    return COURIER if str(kind or "").strip().lower() == "package" else RIDES


def enabled_verticals() -> frozenset:
    """The platform's currently enabled verticals (from ``settings.VERTICALS_ENABLED``)."""
    from django.conf import settings

    return frozenset(getattr(settings, "VERTICALS_ENABLED", frozenset()))


def is_vertical_enabled(vertical) -> bool:
    """Whether *vertical* is currently enabled platform-wide."""
    return vertical in enabled_verticals()
