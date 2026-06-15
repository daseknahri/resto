"""Single source of truth for the "is the restaurant open right now?" schedule-window
rule (the manual ``is_open`` toggle + the weekly ``business_hours_schedule``).

This module is the ONE place the open-window logic lives. It previously had three
drifted inline copies (menu.views._schedule_open, accounts.views._compute_is_open_now,
tenancy.serializers.ProfileSerializer.get_is_open_now) — one of which still evaluated
the window in UTC instead of the tenant's local wall-clock, so a non-UTC restaurant
reported a different open/closed verdict on its menu page than on its marketplace card.

``tenancy`` is a SHARED app importable everywhere, so menu, accounts, and tenancy can
all import this with no cross-app cycle. By design this module uses ONLY the stdlib and
``django.conf.settings`` — NO model / view / serializer imports at module load.

The three callers intentionally differ ONLY in their extra guards layered around this
shared window rule:
  - listing card (accounts._compute_is_open_now): is_open + is_menu_temporarily_disabled
  - menu/meta page (tenancy.serializers.get_is_open_now): is_open + is_menu_temporarily_disabled
                                                          + ClosureDate (serializer-only —
                                                          the public listing runs in the
                                                          public schema and skips it)
  - order-acceptance gate (menu.views._is_restaurant_currently_open): neither, because a
                                                                      separate 503 blocks ordering
The WINDOW rule itself is now identical across all three.
"""

# Weekday index (datetime.weekday(): Mon=0 .. Sun=6) → schedule dict key.
_WEEKDAY_TO_KEY = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}


def tenant_local_now(profile):
    """Current local datetime for a restaurant, honoring its IANA ``timezone``.

    Resolves the timezone via the same fallback chain used by menu.views._profile_now
    and _within_business_hours: ``profile.timezone`` → ``settings.TIME_ZONE`` → ``"UTC"``.
    On an invalid/unknown tz (or any resolution error) it falls back to UTC.

    Returns an aware ``datetime`` so callers can compare its tenant-local wall-clock
    (``%H:%M`` / ``.weekday()``) against the schedule strings.
    """
    from datetime import datetime as _dt, timezone as _tz
    try:
        from zoneinfo import ZoneInfo
        from django.conf import settings
        tz_name = (getattr(profile, "timezone", "") or "").strip() or getattr(settings, "TIME_ZONE", "") or "UTC"
        return _dt.now(ZoneInfo(tz_name))
    except Exception:
        return _dt.now(_tz.utc)  # invalid/unknown tz → safe UTC fallback


def schedule_open_now(schedule, now_local):
    """The SINGLE window rule shared by every "is open now?" derivation.

    Args:
        schedule:   ``profile.business_hours_schedule`` (a dict keyed by mon..sun, or
                    anything falsy / non-dict when unconfigured).
        now_local:  An aware datetime in the tenant's local timezone (typically from
                    ``tenant_local_now(profile)`` or ``_profile_now(profile)``).

    Returns:
      True  — the schedule says the restaurant is open right now.
      False — the schedule says the restaurant is currently closed.
      None  — no schedule configured (falsy / not a dict / no enabled day) — the caller
              then falls back to the manual ``is_open`` boolean.

    The day lookup, the blank/closed handling, and the half-open ``[open, close)``
    comparison mirror the semantics of the original menu.views._schedule_open exactly.
    """
    if not schedule or not isinstance(schedule, dict):
        return None

    # If no day is enabled, treat the schedule as unconfigured.
    if not any(
        isinstance(v, dict) and v.get("enabled", False)
        for v in schedule.values()
    ):
        return None

    day_key = _WEEKDAY_TO_KEY.get(now_local.weekday())
    entry = schedule.get(day_key)

    if not entry or not isinstance(entry, dict):
        return False  # today not represented → closed today

    if not entry.get("enabled", False):
        return False

    open_str = (entry.get("open") or "").strip()
    close_str = (entry.get("close") or "").strip()
    if not open_str or not close_str:
        return False

    current_hhmm = now_local.strftime("%H:%M")
    return open_str <= current_hhmm < close_str
