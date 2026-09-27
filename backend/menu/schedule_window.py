"""Single source of truth for the "is this day-of-week + time-of-day window open now?" rule.

This is the pure, date-bound-free core of the windowing rule. It used to live only inside
``menu.promos.promo_is_active`` (which layers ``active_from``/``active_until`` date bounds on
top). The SAME day/time/overnight rule is also needed by a dish's ``availability_schedule``
(a dish is only orderable within its window) — and the display + order-time evaluations of THAT
must not fork into a third copy of the overnight logic. So the shared core is extracted here and
both ``promo_is_active`` and the dish-schedule checks delegate to it.

It imports ONLY stdlib (``datetime`` is used solely for the type hint) and NO Django models / no
``menu.views`` / no ``accounts`` at module load, so ``menu.promos`` — and, transitively,
``accounts.views`` which imports ``promo_is_active`` at top level — can import it without an import
cycle.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


_WDAY = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}


def day_time_window_open(days, time_start, time_end, *, now_local) -> bool:
    """Return True when the day-of-week + HH:MM window is OPEN at ``now_local``.

    ``now_local`` MUST be a datetime in the tenant's LOCAL (wall-clock) time — every
    component of the verdict derives from it (weekday token + ``%H:%M``), so the result
    is internally consistent and tenant-local. Callers that also enforce inclusive date
    bounds (promos) apply those separately before delegating here.

    Rules (identical to the historic ``promo_is_active`` day+time core):
      - ``days`` is an allow-list of ``mon``..``sun`` tokens; empty / non-list = every day.
      - ``time_start`` / ``time_end`` are ``"HH:MM"`` strings; either blank = all-day
        (only the day allow-list applies).
      - ``time_start < time_end`` → normal same-day window: open when today's weekday is
        allowed AND ``time_start <= now < time_end``.
      - ``time_start > time_end`` → overnight window (e.g. ``"22:00"``–``"02:00"``): the
        evening part (``now >= time_start``) belongs to TODAY's weekday, the after-midnight
        tail (``now < time_end``) to YESTERDAY's weekday — mirrors the HappyHour rule in
        ``menu/pricing.py``.
    """
    # Non-list (or empty) day lists mean "no day restriction" (matches both the promo
    # source and the dish serializer's historic ``isinstance(days, list)`` guard).
    allowed_days = days if isinstance(days, list) else []
    today_token = _WDAY[now_local.weekday()]
    yesterday_token = _WDAY[(now_local.weekday() - 1) % 7]

    ts = (time_start or "").strip()
    te = (time_end or "").strip()

    # No (or partial) time window → all-day: only the day allow-list applies.
    if not ts or not te:
        return not allowed_days or today_token in allowed_days

    now_hhmm = now_local.strftime("%H:%M")
    if ts < te:
        # Normal same-day window: today's day allowed AND now in [ts, te).
        if allowed_days and today_token not in allowed_days:
            return False
        return ts <= now_hhmm < te

    # Overnight window (ts > te): evening part → today's weekday, after-midnight tail →
    # yesterday's weekday. A naive ``ts <= now < te`` would be empty here, so an overnight
    # window would otherwise never open.
    if now_hhmm >= ts:
        return not allowed_days or today_token in allowed_days
    if now_hhmm < te:
        return not allowed_days or yesterday_token in allowed_days
    return False
