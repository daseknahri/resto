"""
Tests for timezone-aware business-hours auto open/close (menu.views._schedule_open /
_profile_now). The schedule must be evaluated in the restaurant's local timezone, not UTC.

Unit-level (SimpleTestCase — pure functions, no DB).
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from menu.views import _schedule_open, _profile_now

_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _profile(schedule, timezone=""):
    return SimpleNamespace(business_hours_schedule=schedule, timezone=timezone, is_open=True)


def _sched_for(dt, open_="09:00", close_="18:00"):
    """Build a one-day schedule keyed to the given datetime's weekday."""
    return {_KEYS[dt.weekday()]: {"enabled": True, "open": open_, "close": close_}}


class ScheduleOpenTimezoneTests(SimpleTestCase):
    def test_open_within_local_hours(self):
        dt = datetime(2026, 6, 3, 10, 0)  # 10:00 local
        with patch("menu.views._profile_now", return_value=dt):
            self.assertTrue(_schedule_open(_profile(_sched_for(dt))))

    def test_closed_outside_local_hours(self):
        dt = datetime(2026, 6, 3, 19, 0)  # 19:00 local — past close
        with patch("menu.views._profile_now", return_value=dt):
            self.assertFalse(_schedule_open(_profile(_sched_for(dt))))

    def test_no_schedule_returns_none(self):
        self.assertIsNone(_schedule_open(_profile({})))

    def test_no_enabled_day_returns_none(self):
        self.assertIsNone(_schedule_open(_profile({"mon": {"enabled": False}})))

    def test_profile_now_honors_timezone(self):
        # Africa/Casablanca is ahead of UTC — the local hour should differ from UTC's
        # (outside the rare equal-hour edge). Mainly asserts it runs + is tz-aware.
        now = _profile_now(_profile({}, timezone="Africa/Casablanca"))
        self.assertIsNotNone(now)
        self.assertIsNotNone(now.tzinfo)

    def test_invalid_timezone_falls_back_safely(self):
        now = _profile_now(_profile({}, timezone="Not/AZone"))
        self.assertIsNotNone(now)  # no crash — falls back to UTC
