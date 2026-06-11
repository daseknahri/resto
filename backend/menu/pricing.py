"""
menu/pricing.py — Happy-hour / time-based pricing helpers.

Public API
----------
get_active_happy_hours(now_local)
    Return all HappyHour rules whose window is active at *now_local*
    (a timezone-aware datetime in the tenant's local timezone).
    Issues ONE query for is_active rules + ONE prefetch for the M2M
    categories relation.  The caller should cache this list for the
    lifetime of a single request to avoid per-dish re-queries.

effective_unit_price(dish, active_rules)
    Given the list returned by get_active_happy_hours(), find the best
    (largest percent_off) applicable rule for *dish*, apply it to
    dish.price, quantize to 0.01 ROUND_HALF_UP, and return
    (effective_price: Decimal, winning_rule: HappyHour | None).

    NOTE: option price_delta is never discounted — it is added on top of
    the effective base price by the caller (PlaceOrderView et al.).

happy_hour_payload(rule)
    Serialize a HappyHour rule for the customer-facing "happy_hour"
    JSON field: {"name", "percent_off", "ends_at"}.  Returns None when
    *rule* is None.

Overnight windows
-----------------
    If start_time > end_time the window wraps midnight.  A rule is
    active when:
      (today's weekday is in days AND t >= start_time)
      OR
      (yesterday's weekday is in days AND t < end_time)

Advance / scheduled orders
--------------------------
    Pricing is LOCKED at placement time (the moment the customer submits
    the order), not at scheduled_for.  Customers are prepaid at placement,
    so this is the defensible choice — the discount was offered and accepted
    at submission time.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING

from .models import HappyHour

if TYPE_CHECKING:
    from datetime import datetime
    from .models import Dish


def get_active_happy_hours(now_local: "datetime") -> list:
    """Return all HappyHour rules active at *now_local* (tenant-local aware dt).

    Performs ONE query (is_active filter) plus ONE prefetch (categories M2M).
    """

    rules = list(
        HappyHour.objects.filter(is_active=True).prefetch_related("categories")
    )

    t = now_local.time()
    weekday = now_local.weekday()                 # 0=Mon … 6=Sun
    yesterday = (weekday - 1) % 7

    active = []
    for rule in rules:
        days = rule.days or []
        if not days:
            continue  # mis-configured rule — skip

        start = rule.start_time
        end = rule.end_time

        if start == end:
            continue  # zero-length window — skip (also caught by serializer)

        if start < end:
            # Normal (non-overnight) window: active when today's day is in days
            # AND start <= t < end.
            if weekday in days and start <= t < end:
                active.append(rule)
        else:
            # Overnight window (e.g. 22:00 – 02:00).
            # Part 1: today after start (and today's day is in days).
            if weekday in days and t >= start:
                active.append(rule)
            # Part 2: early morning before end (and yesterday's day is in days).
            elif yesterday in days and t < end:
                active.append(rule)

    return active


def effective_unit_price(dish, active_rules: list) -> tuple:
    """Return (effective_price: Decimal, winning_rule: HappyHour | None).

    Selects the rule with the LARGEST percent_off that applies to *dish*
    (considering category scoping — empty categories set = all categories).
    Quantizes to 0.01 ROUND_HALF_UP.  Returns (dish.price, None) when no
    rule applies.

    NOTE: option price_delta is never discounted and must be added on top
    of the effective base by the caller.
    """
    base = Decimal(str(dish.price))
    best_rule = None
    best_pct = 0

    dish_category_id = getattr(dish, "category_id", None)

    for rule in active_rules:
        # Category scoping: if the M2M set is non-empty, dish must be in it.
        try:
            cat_qs = rule.categories.all()
            # Use cached prefetch when available; fall back to DB call.
            cat_ids = {c.id for c in cat_qs}
        except Exception:
            cat_ids = set()

        if cat_ids and dish_category_id not in cat_ids:
            continue  # rule does not cover this dish's category

        if rule.percent_off > best_pct:
            best_pct = rule.percent_off
            best_rule = rule

    if best_rule is None:
        return base, None

    discount = (base * Decimal(str(best_pct)) / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    effective = max(Decimal("0.00"), base - discount).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return effective, best_rule


def happy_hour_payload(rule) -> dict | None:
    """Return the customer-facing happy_hour JSON fragment, or None."""
    if rule is None:
        return None
    return {
        "name": rule.name,
        "percent_off": rule.percent_off,
        "ends_at": rule.end_time.strftime("%H:%M"),
        "starts_at": rule.start_time.strftime("%H:%M"),
    }
