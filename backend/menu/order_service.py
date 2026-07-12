"""Order domain service (RISK STRUCT-1).

`PlaceOrderView.post` is a ~1,100-line method that inlines the whole order pipeline
(pricing, delivery fee, promo, loyalty, wallet, stock, persistence). This module is the
home the register calls for — a tested domain service the view delegates to, mirroring
`accounts/wallet_service.py`. It is being grown one cohesive, behavior-preserving slice at a
time; the view keeps a thin function-local import at each call site (the codebase's standard
menu↔accounts/tenancy cycle-avoidance convention).

Slice 1: delivery-fee computation — a pre-atomic, side-effect-free sub-phase that already
delegated to the tested `tenancy` pricing/routing helpers, so moving it changes no behavior and
breaks no existing mock (no test patched these via `menu.views.*`).
"""
from decimal import Decimal

from menu.models import Order


def compute_order_delivery_fee(profile, *, fulfillment_type, food_subtotal, delivery_lat, delivery_lng):
    """Compute the delivery fee for an order (RISK STRUCT-1, extracted from PlaceOrderView.post).

    Returns ``(fee: Decimal, distance_km: float | None, error_code: str | None)`` where
    ``error_code`` is ``"delivery_out_of_range"`` when the address is outside the delivery area
    (the caller maps this to a 400), else ``None``.

    Behavior is identical to the former inline block:
    * Non-delivery fulfillment → ``(Decimal("0"), None, None)`` (no fee, no computation).
    * Delivery → distance is computed ONLY when BOTH the restaurant and the address have a valid,
      real coordinate (a missing / ``(0,0)`` / out-of-range coord → distance unknown → the flat
      fallback fee, never a false "outside area"), then `tenancy.delivery_pricing.compute_delivery_fee`
      decides the fee and whether the address is out of range.
    """
    if fulfillment_type != Order.FulfillmentType.DELIVERY:
        return Decimal("0"), None, None

    # Function-local (menu↔tenancy cycle-avoidance convention), matching the original call site.
    from tenancy.delivery_pricing import compute_delivery_fee, valid_coord
    from tenancy.routing import road_distance_km

    plat = getattr(profile, "lat", None)
    plng = getattr(profile, "lng", None)
    distance_km = None
    if valid_coord(plat, plng) and valid_coord(delivery_lat, delivery_lng):
        # Road distance (haversine × factor, or a real OSRM route when DELIVERY_OSRM_URL is set).
        distance_km = road_distance_km(plat, plng, delivery_lat, delivery_lng)

    pricing = compute_delivery_fee(profile, distance_km=distance_km, food_subtotal=food_subtotal)
    if pricing["out_of_range"]:
        return Decimal("0"), distance_km, "delivery_out_of_range"
    return pricing["fee"], distance_km, None
