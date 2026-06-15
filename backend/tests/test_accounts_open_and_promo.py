"""
Unit tests for accounts/views.py private helpers:
  - _compute_is_open_now
  - _is_promo_active_now  (accounts.views version — distinct from menu.views)

All tests are unit-level (SimpleTestCase + mocks — no real DB).
datetime.datetime is patched for time-dependent cases.
"""
import datetime as dt_module
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from accounts.views import _compute_is_open_now, _is_promo_active_now


def _utc_today():
    """Today's date on the SAME clock _is_promo_active_now defaults to.

    The promo window is now evaluated from ONE consistent tz-aware clock (the
    wrapper defaults to datetime.now(UTC); production callers pass a tenant-local
    now) instead of mixing date.today() (server-local) with datetime.utcnow() — the
    historic timezone bug. The date-boundary tests below anchor on UTC so an
    exact-today bound is deterministic regardless of the server's local offset (this
    host runs UTC+1, where local midnight is the previous day in UTC).
    """
    return datetime.now(timezone.utc).date()


# 2024-06-03 is Monday (weekday 0); 2024-06-04 is Tuesday (weekday 1).
# These are now tz-aware and passed as now_local=... — the day/time-window cases used
# to monkeypatch datetime.datetime.utcnow(), but the single windowing rule derives all
# three components (date/weekday/HH:MM) from ONE now_local, so we feed it directly.
_MON_14H = dt_module.datetime(2024, 6, 3, 14, 30, 0, tzinfo=timezone.utc)   # Mon 14:30
_MON_8H  = dt_module.datetime(2024, 6, 3,  8,  0, 0, tzinfo=timezone.utc)   # Mon 08:00
_MON_22H = dt_module.datetime(2024, 6, 3, 22, 30, 0, tzinfo=timezone.utc)   # Mon 22:30
_TUE_14H = dt_module.datetime(2024, 6, 4, 14, 30, 0, tzinfo=timezone.utc)   # Tue 14:30


def _mock_dt(fixed_now: dt_module.datetime):
    class _M(dt_module.datetime):
        @classmethod
        def utcnow(cls):
            return fixed_now

        @classmethod
        def now(cls, tz=None):
            # _compute_is_open_now now reads datetime.now(ZoneInfo(profile.timezone)).
            # The schedule fixtures below are anchored in UTC, and the profiles default
            # to a "UTC" timezone, so return the fixed UTC instant for any tz arg.
            return fixed_now
    return _M


def _profile(
    *,
    is_open=True,
    is_menu_temporarily_disabled=False,
    business_hours_schedule=None,
    timezone="UTC",
):
    return SimpleNamespace(
        is_open=is_open,
        is_menu_temporarily_disabled=is_menu_temporarily_disabled,
        business_hours_schedule=business_hours_schedule,
        timezone=timezone,
    )


# ══════════════════════════════════════════════════════════════════════════════
# _compute_is_open_now
# ══════════════════════════════════════════════════════════════════════════════

class ComputeIsOpenNowTests(SimpleTestCase):

    # ── manual-toggle short-circuits ─────────────────────────────────────────
    def test_is_open_false_returns_false(self):
        self.assertFalse(_compute_is_open_now(_profile(is_open=False)))

    def test_temporarily_disabled_returns_false(self):
        self.assertFalse(
            _compute_is_open_now(_profile(is_open=True, is_menu_temporarily_disabled=True))
        )

    # ── no schedule falls back to is_open ────────────────────────────────────
    def test_no_schedule_open_returns_true(self):
        self.assertTrue(_compute_is_open_now(_profile(is_open=True, business_hours_schedule=None)))

    def test_non_dict_schedule_falls_back_to_is_open(self):
        self.assertTrue(_compute_is_open_now(_profile(is_open=True, business_hours_schedule="09:00-22:00")))

    def test_empty_schedule_falls_back_to_is_open(self):
        """Empty dict is falsy → same as no schedule."""
        self.assertTrue(_compute_is_open_now(_profile(is_open=True, business_hours_schedule={})))

    def test_schedule_with_no_enabled_days_falls_back_to_is_open(self):
        schedule = {"mon": {"enabled": False, "open": "", "close": ""}}
        self.assertTrue(_compute_is_open_now(_profile(is_open=True, business_hours_schedule=schedule)))

    # ── schedule with enabled days ───────────────────────────────────────────
    def test_today_not_in_schedule_returns_false(self):
        """Monday, but only tuesday is enabled."""
        schedule = {"tue": {"enabled": True, "open": "09:00", "close": "22:00"}}
        with patch("datetime.datetime", _mock_dt(_MON_14H)):
            self.assertFalse(_compute_is_open_now(_profile(business_hours_schedule=schedule)))

    def test_today_in_schedule_not_enabled_returns_false(self):
        # tue is enabled so schedule is "active", but mon is explicitly disabled
        schedule = {
            "mon": {"enabled": False, "open": "09:00", "close": "22:00"},
            "tue": {"enabled": True, "open": "09:00", "close": "22:00"},
        }
        with patch("datetime.datetime", _mock_dt(_MON_14H)):
            self.assertFalse(_compute_is_open_now(_profile(business_hours_schedule=schedule)))

    def test_today_in_schedule_missing_entry_returns_false(self):
        """Schedule has no mon entry at all."""
        schedule = {"tue": {"enabled": True, "open": "09:00", "close": "22:00"}}
        with patch("datetime.datetime", _mock_dt(_MON_14H)):
            self.assertFalse(_compute_is_open_now(_profile(business_hours_schedule=schedule)))

    def test_entry_missing_times_returns_false(self):
        schedule = {"mon": {"enabled": True, "open": "", "close": ""}}
        with patch("datetime.datetime", _mock_dt(_MON_14H)):
            self.assertFalse(_compute_is_open_now(_profile(business_hours_schedule=schedule)))

    def test_within_time_window_returns_true(self):
        schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
        with patch("datetime.datetime", _mock_dt(_MON_14H)):  # 14:30
            self.assertTrue(_compute_is_open_now(_profile(business_hours_schedule=schedule)))

    def test_before_time_window_returns_false(self):
        schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
        with patch("datetime.datetime", _mock_dt(_MON_8H)):   # 08:00
            self.assertFalse(_compute_is_open_now(_profile(business_hours_schedule=schedule)))

    def test_after_time_window_returns_false(self):
        schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
        with patch("datetime.datetime", _mock_dt(_MON_22H)):  # 22:30
            self.assertFalse(_compute_is_open_now(_profile(business_hours_schedule=schedule)))


# ══════════════════════════════════════════════════════════════════════════════
# _compute_is_open_now — schedule is evaluated in TENANT-LOCAL time (CHANGE 3b)
# ══════════════════════════════════════════════════════════════════════════════

def _tz_aware_mock_dt(fixed_utc: dt_module.datetime):
    """datetime stand-in whose .now(tz) converts a FIXED UTC instant into the asked
    tz — so a test can prove the schedule is read in the tenant's wall-clock, not the
    server's. (utcnow() returns the same instant naive, like the old buggy path.)"""
    class _M(dt_module.datetime):
        @classmethod
        def utcnow(cls):
            return fixed_utc.replace(tzinfo=None)

        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_utc.replace(tzinfo=None)
            return fixed_utc.astimezone(tz)
    return _M


class ComputeIsOpenNowTenantLocalTests(SimpleTestCase):
    """A single fixed instant + a fixed schedule yields a DIFFERENT verdict per
    timezone — proving the weekday/HH:MM are derived in the tenant's local clock."""

    # 2024-06-03 23:30 UTC. UTC weekday = Monday; America/New_York (EDT, UTC-4) is
    # Monday 19:30 local. Schedule: Monday open 09:00–22:00.
    _SCHEDULE = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
    _INSTANT = dt_module.datetime(2024, 6, 3, 23, 30, 0, tzinfo=timezone.utc)

    def test_tenant_local_open_when_utc_would_say_closed(self):
        """NY tenant: 19:30 local Monday is inside 09:00–22:00 → open."""
        prof = _profile(business_hours_schedule=self._SCHEDULE, timezone="America/New_York")
        with patch("datetime.datetime", _tz_aware_mock_dt(self._INSTANT)):
            self.assertTrue(_compute_is_open_now(prof))

    def test_utc_tenant_closed_at_same_instant(self):
        """UTC tenant: 23:30 Monday is after 22:00 → closed (the old, server-clock verdict)."""
        prof = _profile(business_hours_schedule=self._SCHEDULE, timezone="UTC")
        with patch("datetime.datetime", _tz_aware_mock_dt(self._INSTANT)):
            self.assertFalse(_compute_is_open_now(prof))

    def test_invalid_timezone_falls_back_to_utc(self):
        """A garbage tz string must not raise — it falls back to UTC (→ closed here)."""
        prof = _profile(business_hours_schedule=self._SCHEDULE, timezone="Not/AZone")
        with patch("datetime.datetime", _tz_aware_mock_dt(self._INSTANT)):
            self.assertFalse(_compute_is_open_now(prof))


# ══════════════════════════════════════════════════════════════════════════════
# _is_promo_active_now  (accounts.views version)
# ══════════════════════════════════════════════════════════════════════════════

def _promo(
    *,
    active_from=None,
    active_until=None,
    days=None,
    time_start="",
    time_end="",
):
    today = date.today()
    return SimpleNamespace(
        active_from=active_from,
        active_until=active_until,
        days=days or [],
        time_start=time_start,
        time_end=time_end,
    )


class AccountsViewIsPromoActiveNowTests(SimpleTestCase):

    # ── date-range checks ─────────────────────────────────────────────────────
    def test_no_restrictions_returns_true(self):
        self.assertTrue(_is_promo_active_now(_promo()))

    def test_future_active_from_returns_false(self):
        self.assertFalse(_is_promo_active_now(_promo(active_from=_utc_today() + timedelta(days=1))))

    def test_past_active_from_returns_true(self):
        self.assertTrue(_is_promo_active_now(_promo(active_from=_utc_today() - timedelta(days=1))))

    def test_today_as_active_from_returns_true(self):
        self.assertTrue(_is_promo_active_now(_promo(active_from=_utc_today())))

    def test_expired_active_until_returns_false(self):
        self.assertFalse(_is_promo_active_now(_promo(active_until=_utc_today() - timedelta(days=1))))

    def test_future_active_until_returns_true(self):
        self.assertTrue(_is_promo_active_now(_promo(active_until=_utc_today() + timedelta(days=1))))

    def test_today_as_active_until_returns_true(self):
        self.assertTrue(_is_promo_active_now(_promo(active_until=_utc_today())))

    # ── day restriction ───────────────────────────────────────────────────────
    def test_all_days_allowed_returns_true(self):
        all_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        self.assertTrue(_is_promo_active_now(_promo(days=all_days)))

    def test_wrong_day_returns_false(self):
        # now_local is a Monday; schedule only allows tuesday → inactive.
        self.assertFalse(_is_promo_active_now(_promo(days=["tue", "wed"]), now_local=_MON_14H))

    def test_matching_day_returns_true(self):
        self.assertTrue(_is_promo_active_now(_promo(days=["mon"]), now_local=_MON_14H))

    def test_empty_days_no_restriction_returns_true(self):
        self.assertTrue(_is_promo_active_now(_promo(days=[])))

    # ── time window check ─────────────────────────────────────────────────────
    def test_within_time_window_returns_true(self):
        self.assertTrue(_is_promo_active_now(
            _promo(time_start="09:00", time_end="22:00"), now_local=_MON_14H   # 14:30
        ))

    def test_before_time_window_returns_false(self):
        self.assertFalse(_is_promo_active_now(
            _promo(time_start="09:00", time_end="22:00"), now_local=_MON_8H    # 08:00
        ))

    def test_after_time_window_returns_false(self):
        self.assertFalse(_is_promo_active_now(
            _promo(time_start="09:00", time_end="22:00"), now_local=_MON_22H   # 22:30
        ))

    def test_no_time_restriction_returns_true(self):
        self.assertTrue(_is_promo_active_now(_promo(time_start="", time_end="")))

    def test_partial_time_restriction_no_effect(self):
        """Only time_start set — both needed → no filter applied."""
        self.assertTrue(_is_promo_active_now(_promo(time_start="09:00", time_end="")))
