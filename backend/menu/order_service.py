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


def compute_order_tip(tip_raw, food_subtotal) -> Decimal:
    """Parse + clamp the customer gratuity (RISK STRUCT-1, extracted from PlaceOrderView.post).

    Behavior is byte-identical to the former inline block: coerce to 2 dp; any parse failure or a
    negative value → ``Decimal("0")``; capped at 100% of the food subtotal when the subtotal is
    positive (a fat-finger runaway guard). When the subtotal is 0 (or negative) the cap does not
    apply, matching the original ``if _food_subtotal > 0 and ...`` guard.
    """
    try:
        tip = Decimal(str(tip_raw)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0")
    if tip < Decimal("0"):
        return Decimal("0")
    if food_subtotal > Decimal("0") and tip > food_subtotal:
        return food_subtotal
    return tip


def resolve_prepay_and_wallet(*, user, linked_customer, profile, fulfillment_type, total,
                              is_scheduled, payment_method, use_wallet_flag):
    """Resolve the prepay / cash-on-handover / wallet money-gate (RISK STRUCT-1, extracted from
    PlaceOrderView.post).

    Returns ``(requires_prepay, cod_order, use_wallet, wallet_deduction, error)`` — the four locals
    the order pipeline consumes downstream, plus ``error`` = a ``(detail_dict, http_status)`` tuple
    the caller returns as a Response, or ``None`` when the gate passes.

    Behavior is byte-identical to the former inline block: staff/owner orders (waiter settles in
    person) are EXEMPT; a customer pickup/delivery order with a positive total must either be a
    COD-eligible cash-on-handover (repeat customer, not a scheduled order) or be fully covered by
    wallet balance — else 403 ``auth_required`` (no signed-in customer) or 402 ``wallet_insufficient``.
    Wallet is used when prepay-required-and-not-COD or the client opted in, deducting
    ``min(balance, total)`` (and disabled if that is ≤ 0).
    """
    from accounts.models import User

    is_staff = bool(
        user is not None
        and getattr(user, "is_authenticated", False)
        and getattr(user, "role", None) in (User.Roles.TENANT_OWNER, User.Roles.TENANT_STAFF)
    )
    requires_prepay = (
        not is_staff
        and fulfillment_type in (Order.FulfillmentType.PICKUP, Order.FulfillmentType.DELIVERY)
    )

    cod_order = False
    if requires_prepay and total > Decimal("0"):
        if linked_customer is None:
            return requires_prepay, cod_order, False, Decimal("0"), (
                {"detail": "Sign in and top up your wallet to place a pickup or delivery order.",
                 "code": "auth_required"},
                403,
            )
        pm = str(payment_method or "").strip().lower()
        # Function-local so the patch target stays `menu.views._cod_eligible` (tests patch it there).
        from menu.views import _cod_eligible
        if pm == "cash" and not is_scheduled and _cod_eligible(profile, linked_customer.id):
            cod_order = True
        else:
            wallet_avail = Decimal(str(linked_customer.wallet_balance or "0"))
            if wallet_avail < total:
                return requires_prepay, cod_order, False, Decimal("0"), (
                    {"detail": "Your wallet balance doesn't cover this order. Please top up your wallet.",
                     "code": "wallet_insufficient",
                     "balance": str(wallet_avail), "amount_due": str(total)},
                    402,
                )

    use_wallet = ((requires_prepay and not cod_order) or bool(use_wallet_flag)) and linked_customer is not None
    wallet_deduction = Decimal("0")
    if use_wallet:
        available = Decimal(str(linked_customer.wallet_balance or "0"))
        wallet_deduction = min(available, total)
        if wallet_deduction <= Decimal("0"):
            use_wallet = False
            wallet_deduction = Decimal("0")
    return requires_prepay, cod_order, use_wallet, wallet_deduction, None
