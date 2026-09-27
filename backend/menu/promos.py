"""Single source of truth for the promo-window "is this promo live now?" rule.

Backend correctness batch: there used to be TWO copies of this windowing rule —
menu.views._is_promo_active_now (checkout discount, real money) and
accounts.views._is_promo_active_now (marketplace badge). They had drifted and
SHARED a timezone bug: the date bound was compared against date.today() (server
local) while the weekday + HH:MM window were compared against datetime.utcnow()
(UTC) — three components evaluated against TWO different clocks. A promo
"Tuesday 14:00–16:00" means TENANT-LOCAL wall-clock, so the whole window must be
evaluated from ONE tz-aware tenant-local instant.

This module is the single rule both copies now delegate to. It evaluates the FULL
window (date bounds + day-of-week + HH:MM) from a SINGLE ``now_local`` so the
verdict is internally consistent and tenant-local. The day-of-week + HH:MM part is
factored out as ``day_time_window_open`` so dish ``availability_schedule`` enforcement
(menu.order_service) reuses the SAME overnight-aware rule rather than a third copy.

It imports ONLY stdlib (datetime, zoneinfo) and NO Django models / no menu.views
/ no accounts at module load, so accounts.views can import it at top level with no
import cycle. It reads a promo field off EITHER a Promotion model instance OR a
denormalized dict (Profile.marketplace_promos entries) so there is one rule, no
forked logic.
"""
from datetime import date as _date


_WDAY = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}


def promo_field(promo, name):
    """Read ``name`` off a Promotion whether it's a model instance OR a denorm dict.

    The marketplace promo badge is denormalized onto the public Profile as a list
    of plain dicts (Profile.marketplace_promos); the windowing rule must read those
    identically to a real Promotion object so there is ONE source of truth for
    "is this promo live now". Supports a mapping (dict) or an attribute object.
    """
    if isinstance(promo, dict):
        return promo.get(name)
    return getattr(promo, name, None)


def coerce_date(value):
    """Normalize active_from/active_until: pass through date objects, parse ISO strings.

    Denormalized entries store dates as ISO strings (or null); model instances hold
    real date objects. Returns a date or None.
    """
    if value is None or value == "":
        return None
    if isinstance(value, _date):
        return value
    try:
        return _date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def day_time_window_open(days, time_start, time_end, *, now_local) -> bool:
    """Return True when ``now_local`` falls inside a recurring day-of-week + HH:MM window.

    This is the SINGLE day/time windowing rule, shared so the overnight semantics live in
    exactly one place: ``promo_is_active`` layers active_from/active_until DATE bounds on top
    of it, and dish ``availability_schedule`` enforcement (menu.order_service) calls it raw.

    ``now_local`` MUST be a tz-aware tenant-local datetime — both derived components (the
    weekday token and the current HH:MM) come from it, so the verdict is internally
    consistent and tenant-local (this is the today()/utcnow() mismatch fix).

    Rules:
      - ``days``: allow-list of mon..sun tokens; empty/falsy = every day.
      - ``time_start`` / ``time_end``: both blank = all day (only the day allow-list applies);
        otherwise open when ``time_start <= now_hhmm < time_end``.
      - Overnight window (``time_start > time_end``, e.g. "22:00"–"02:00"): the evening part
        belongs to TODAY's weekday, the after-midnight tail to YESTERDAY's weekday (mirrors the
        HappyHour rule in menu/pricing.py). A naive same-day compare would never match it.
    """
    allowed_days = days or []
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

    # Overnight window (ts > te): evening belongs to today, after-midnight tail to yesterday.
    if now_hhmm >= ts:
        return not allowed_days or today_token in allowed_days
    if now_hhmm < te:
        return not allowed_days or yesterday_token in allowed_days
    return False


def promo_is_active(promo, *, now_local) -> bool:
    """Return True if a promo is live at the tenant-local instant ``now_local``.

    ``now_local`` MUST be a single tz-aware datetime in the tenant's local time.
    ALL window components derive from it so the evaluation is internally consistent
    and tenant-local (this is the fix for the today()/utcnow() mismatch):

      - today        = now_local.date()
      - weekday token = _WDAY[now_local.weekday()]
      - current HH:MM = now_local.strftime("%H:%M")

    Rules (unchanged from the historic behavior, just on one clock):
      - active_from / active_until are INCLUSIVE date bounds (blank/None = unbounded)
      - days is an allow-list of mon..sun tokens; empty list = every day
      - time_start/time_end: both blank = all day; otherwise live when
        time_start <= now_hhmm < time_end

    The day-of-week + HH:MM window is delegated to ``day_time_window_open`` — the shared
    rule (also used by dish availability_schedule enforcement); this function only adds the
    promo-specific date bounds on top.
    """
    today = now_local.date()

    active_from = coerce_date(promo_field(promo, "active_from"))
    active_until = coerce_date(promo_field(promo, "active_until"))
    if active_from and today < active_from:
        return False
    if active_until and today > active_until:
        return False

    return day_time_window_open(
        promo_field(promo, "days"),
        promo_field(promo, "time_start"),
        promo_field(promo, "time_end"),
        now_local=now_local,
    )
