"""
Shared revenue helpers used by both the daily-summary digest and the
sales-dashboard period analytics endpoint.

These helpers avoid importing Django ORM at module level so the file can be
imported early without a full database connection.
"""
from __future__ import annotations

from decimal import Decimal


def split_revenue_for_orders(order_qs) -> dict:
    """Return {wallet: Decimal, cash: Decimal} for a given paid-order queryset.

    Uses the two-path ledger-vs-legacy strategy:
      - Orders that have OrderPayment ledger rows → exact per-method SUM.
      - Orders without ledger rows (legacy one-shot settles) → wallet_amount_paid
        field with total-derived cash math.
    Both paths are clamped >= 0.

    Args:
        order_qs: A Django queryset of Order instances (already filtered to the
                  desired date range and statuses by the caller).

    Returns:
        {"wallet": Decimal, "cash": Decimal}
    """
    from django.db.models import Q, Sum

    from menu.models import OrderPayment

    # Use a subquery instead of materialising all order PKs into Python.
    # order_qs.values("id") produces a queryset that the ORM translates to a
    # sub-SELECT, keeping the full list server-side for 90-day windows on busy
    # tenants.  We still need to know WHICH orders have ledger rows (to separate
    # ledger from legacy paths) — we get that from a distinct values_list that
    # the ORM can execute as a single DB round-trip.
    orders_values_qs = order_qs.values("id")

    # Short-circuit: if the source queryset is empty avoid any further DB work.
    # We detect this by checking for an empty result on a cheap EXISTS-equivalent
    # without materialising PKs.  A COUNT(*) would also work but .exists() is
    # cheaper and sufficient here.
    if not order_qs.exists():
        return {"wallet": Decimal("0.00"), "cash": Decimal("0.00")}

    ledger_qs = OrderPayment.objects.filter(order_id__in=orders_values_qs)
    ledger_order_ids = set(ledger_qs.values_list("order_id", flat=True).distinct())

    if ledger_order_ids:
        ledger_agg = ledger_qs.filter(order_id__in=ledger_order_ids).aggregate(
            ledger_wallet=Sum("amount", filter=Q(method=OrderPayment.Method.WALLET)),
            ledger_cash=Sum("amount", filter=Q(method=OrderPayment.Method.CASH)),
        )
        ledger_wallet = Decimal(str(ledger_agg["ledger_wallet"] or 0))
        ledger_cash = Decimal(str(ledger_agg["ledger_cash"] or 0))
    else:
        ledger_wallet = Decimal("0")
        ledger_cash = Decimal("0")

    if ledger_order_ids:
        legacy_agg = order_qs.exclude(id__in=ledger_order_ids).aggregate(
            legacy_wallet=Sum("wallet_amount_paid"),
            legacy_total=Sum("total"),
        )
    else:
        legacy_agg = order_qs.aggregate(
            legacy_wallet=Sum("wallet_amount_paid"),
            legacy_total=Sum("total"),
        )
    legacy_wallet = Decimal(str(legacy_agg["legacy_wallet"] or 0))
    legacy_total = Decimal(str(legacy_agg["legacy_total"] or 0))
    legacy_cash = legacy_total - legacy_wallet

    wallet = max(Decimal("0"), ledger_wallet + legacy_wallet)
    cash = max(Decimal("0"), ledger_cash + legacy_cash)

    return {"wallet": wallet.quantize(Decimal("0.01")), "cash": cash.quantize(Decimal("0.01"))}
