"""Single source of truth for the marketplace-commission policy.

Two policy facts used to live inline at three different call sites and had already
drifted apart (the analytics "billable" list silently dropped ``out_for_delivery``,
so a delivery order in flight was billed by the owner statement but not counted in
the owner's analytics). They are defined ONCE here and imported everywhere:

  1. WHICH order statuses have earned commission (``COMMISSIONABLE_STATUSES``) —
     used by the owner commission statement (``menu.views``) and owner analytics
     (``sales.views``); the two MUST stay identical.
  2. WHAT the commission is charged on (``commissionable_food_base``) — the
     POST-discount food total, used at marketplace checkout (``accounts.views``).

Commission is EARNED once the restaurant CONFIRMS the order, and is kept through
every downstream state up to COMPLETED. ``pending`` / ``scheduled`` orders can
still be cancelled before the kitchen commits, so they are not yet billable;
``cancelled`` orders had their food revenue refunded and never count.

These are the ``menu.models.Order.Status`` *values*, kept here as raw strings on
purpose: this module stays a pure leaf (it imports nothing) so any app's views —
``accounts``, ``menu``, ``sales`` — can import it with zero circular-import risk.
The strings are pinned to the live enum by ``tests/test_commission_policy.py`` so
they can never silently drift from ``Order.Status``.
"""
from decimal import Decimal

# Order.Status.CONFIRMED, PREPARING, READY, OUT_FOR_DELIVERY, COMPLETED.
COMMISSIONABLE_STATUSES = [
    "confirmed",
    "preparing",
    "ready",
    "out_for_delivery",
    "completed",
]


def commissionable_food_base(food_subtotal, promo_discount, loyalty_discount):
    """The base the platform commission is charged on.

    The POST-discount food total the restaurant actually keeps — food subtotal
    minus the promo and loyalty discounts — floored at zero. The delivery fee and
    the customer's tip are intentionally EXCLUDED: the platform only takes a cut of
    food revenue, not the driver's fee or the staff's gratuity.

    All three arguments are expected to be ``Decimal`` (the checkout path already
    computes them as Decimals). Returns a ``Decimal``.
    """
    base = food_subtotal - promo_discount - loyalty_discount
    return base if base > Decimal("0") else Decimal("0")
