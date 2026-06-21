"""Pre-order ETA helper.

Computes a customer-facing prep-time ESTIMATE range ("Ready in ~X–Y min") that
the menu header and checkout surface BEFORE the customer commits — so they aren't
ordering blind. This mirrors Uber Eats / Deliveroo / Talabat, which always show a
"XX–YY min" range on the restaurant card and a per-order ETA at checkout.

Source (per KEPOLI_DAILY_USE_BLUEPRINT.md):
  - Rolling average of recent orders' prep time (status_updated_at − created_at),
    bounded to a sane window, falling back to Profile.default_prep_minutes, then to
    DEFAULT_PREP_MINUTES.
  - The point estimate is rounded to the nearest 5 and widened to a range
    [p − 5, p + 10] (floored at MIN_FLOOR) so it sets expectations like the market
    leaders rather than over-promising a single number.

The travel leg for delivery is added on the FRONTEND using the same haversine /
_eta_minutes the delivery-fee preview already computes, so this module only owns
the kitchen prep portion.
"""

from __future__ import annotations

# Platform default when a tenant has neither configured a default nor accrued any
# recent order history. ~20 min is the typical quick-service quote.
DEFAULT_PREP_MINUTES = 20
# Never quote below this — even an empty kitchen needs a few minutes.
MIN_FLOOR = 5
# How many recent completed/ready orders to average over.
_SAMPLE_LIMIT = 30
# Reject implausible durations (clock skew, abandoned tickets) from the average.
_MIN_PLAUSIBLE = 1.0
_MAX_PLAUSIBLE = 180.0


def _round_to_5(value: float) -> int:
    """Round a minute value to the nearest 5 (e.g. 17 → 15, 18 → 20)."""
    return int(round(value / 5.0) * 5)


def rolling_avg_prep_minutes():
    """Mean prep minutes across recent ready/completed orders in the CURRENT schema.

    Returns a float, or ``None`` when there isn't enough signal. Must be called
    inside the tenant's schema_context. Never raises — returns None on any error.
    """
    try:
        from menu.models import Order
        from django.db.models import Avg, DurationField, ExpressionWrapper, F

        # Look at recently-finished orders; both timestamps are set once an order
        # reaches READY/COMPLETED. Average the (finished − created) duration.
        recent_ids = list(
            Order.objects.filter(
                status__in=[Order.Status.READY, Order.Status.COMPLETED],
                status_updated_at__isnull=False,
            )
            .order_by("-status_updated_at")
            .values_list("id", flat=True)[:_SAMPLE_LIMIT]
        )
        if not recent_ids:
            return None
        agg = (
            Order.objects.filter(id__in=recent_ids)
            .annotate(
                _prep=ExpressionWrapper(
                    F("status_updated_at") - F("created_at"),
                    output_field=DurationField(),
                )
            )
            .aggregate(avg=Avg("_prep"))
        )
        raw = agg.get("avg")
        if raw is None:
            return None
        minutes = raw.total_seconds() / 60.0
        if minutes < _MIN_PLAUSIBLE or minutes > _MAX_PLAUSIBLE:
            return None
        return minutes
    except Exception:
        return None


def prep_eta_range(profile, *, use_history: bool = True):
    """Return ``(min_minutes, max_minutes)`` for the pre-order prep ETA.

    Order of preference for the point estimate:
      1. rolling average of recent orders (when ``use_history`` and available),
      2. ``profile.default_prep_minutes`` (when set),
      3. ``DEFAULT_PREP_MINUTES``.

    The point is rounded to the nearest 5, then widened to ``[p − 5, p + 10]`` and
    floored at ``MIN_FLOOR``. ``use_history=False`` skips the DB query (callers that
    already run outside the tenant schema or want the configured value only).
    """
    point = None
    if use_history:
        point = rolling_avg_prep_minutes()
    if point is None:
        configured = getattr(profile, "default_prep_minutes", None)
        if configured:
            try:
                point = float(configured)
            except (TypeError, ValueError):
                point = None
    if point is None:
        point = float(DEFAULT_PREP_MINUTES)

    rounded = _round_to_5(point)
    lo = max(MIN_FLOOR, rounded - 5)
    hi = max(lo + 5, rounded + 10)
    return lo, hi
