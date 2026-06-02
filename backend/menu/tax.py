"""VAT / tax breakdown helpers.

Menu prices are treated as VAT-INCLUSIVE: the amount the customer is charged never
changes. These helpers only *break out* the VAT portion of an already-inclusive
amount, for display on orders, receipts and invoices.

Kept dependency-free (plain Decimal in/out) so the money math is unit-tested in
isolation, away from models and request handling.
"""
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

_CENT = Decimal("0.01")


def _dec(value) -> Decimal:
    try:
        return Decimal(str(value if value is not None else 0))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(0)


def vat_breakdown(gross, rate_percent):
    """Split a VAT-inclusive ``gross`` amount into ``(net_excl_vat, vat_amount)``.

    vat = gross * rate / (100 + rate);  net = gross - vat.
    A non-positive rate or gross yields ``(gross, 0.00)`` (no VAT line).
    """
    gross = _dec(gross)
    rate = _dec(rate_percent)
    if rate <= 0 or gross <= 0:
        return gross.quantize(_CENT, ROUND_HALF_UP), Decimal("0.00")
    vat = (gross * rate / (Decimal(100) + rate)).quantize(_CENT, ROUND_HALF_UP)
    net = (gross - vat).quantize(_CENT, ROUND_HALF_UP)
    return net, vat


def order_vat_fields(order, rate_percent, label=""):
    """Build the VAT breakdown dict for an order.

    Taxable base = total − delivery_fee − tip_amount (i.e. the VAT-inclusive food
    the customer actually paid, net of any food discount already reflected in the
    total). Delivery and tip are excluded from the VAT breakout. Returns plain
    strings so the values drop straight into JSON responses alongside other money
    fields.
    """
    rate = _dec(rate_percent)
    total = _dec(getattr(order, "total", 0))
    delivery = _dec(getattr(order, "delivery_fee", 0))
    tip = _dec(getattr(order, "tip_amount", 0))
    taxable = total - delivery - tip
    if taxable < 0:
        taxable = Decimal(0)
    net, vat = vat_breakdown(taxable, rate)
    enabled = rate > 0 and vat > 0
    return {
        "vat_rate": str(rate.quantize(_CENT)) if rate > 0 else "0.00",
        "vat_label": (label or "VAT") if enabled else "",
        "vat_taxable_base": str(taxable.quantize(_CENT, ROUND_HALF_UP)),
        "vat_amount": str(vat),
        "vat_net_amount": str(net),
    }
