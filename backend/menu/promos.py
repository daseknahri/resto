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
verdict is internally consistent and tenant-local.

It imports ONLY stdlib (datetime) plus the stdlib-only menu.schedule_window helper, and
NO Django models / no menu.views / no accounts at module load, so accounts.views can
import it at top level with no import cycle. It reads a promo field off EITHER a Promotion
model instance OR a denormalized dict (Profile.marketplace_promos entries) so there is one
rule, no forked logic.
"""
from datetime import date as _date

from .schedule_window import day_time_window_open


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


def promo_is_active(promo, *, now_local) -> bool:
    """Return True if a promo is live at the tenant-local instant ``now_local``.

    ``now_local`` MUST be a single tz-aware datetime in the tenant's local time.
    ALL window components derive from it so the evaluation is internally consistent
    and tenant-local (this is the fix for the today()/utcnow() mismatch): the date
    bounds from ``now_local.date()`` and the day/time window from the SAME instant
    (see ``schedule_window.day_time_window_open``).

    Rules (unchanged from the historic behavior, just on one clock):
      - active_from / active_until are INCLUSIVE date bounds (blank/None = unbounded)
      - the day-of-week + time-of-day (incl. overnight) window is delegated to
        ``schedule_window.day_time_window_open`` — the single rule shared with the dish
        availability_schedule check, so the two can never drift apart.
    """
    today = now_local.date()

    active_from = coerce_date(promo_field(promo, "active_from"))
    active_until = coerce_date(promo_field(promo, "active_until"))
    if active_from and today < active_from:
        return False
    if active_until and today > active_until:
        return False

    # Day-of-week + HH:MM window (incl. overnight) via the single shared rule, so the
    # promo window and a dish's availability_schedule can never fork the overnight logic.
    return day_time_window_open(
        promo_field(promo, "days"),
        promo_field(promo, "time_start"),
        promo_field(promo, "time_end"),
        now_local=now_local,
    )
