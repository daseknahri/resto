"""
Unit tests for the shared open-state helper tenancy.openstate — the SINGLE source of
truth for the "is the restaurant open right now?" schedule-window rule.

Covers:
  - schedule_open_now: window True / False / None semantics (half-open [open, close)).
  - tenant_local_now: timezone fallback chain
        (profile.timezone → settings.TIME_ZONE → UTC) incl. blank tz and invalid tz.
  - A PARITY test proving the WINDOW verdict is identical across the three callers
    (menu.views._schedule_open / accounts.views._compute_is_open_now /
    tenancy.serializers.ProfileSerializer.get_is_open_now) for the same profile +
    schedule + instant, modulo each caller's documented extra guards.

Unit-level (SimpleTestCase — pure functions + mocks, no DB).
"""
import datetime as dt_module
from datetime import timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from tenancy.openstate import schedule_open_now, tenant_local_now


_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _sched_for(dt, *, open_="09:00", close_="18:00", enabled=True):
    """One-day schedule keyed to the given datetime's weekday."""
    return {_KEYS[dt.weekday()]: {"enabled": enabled, "open": open_, "close": close_}}


# ══════════════════════════════════════════════════════════════════════════════
# schedule_open_now — the window rule
# ══════════════════════════════════════════════════════════════════════════════

class ScheduleOpenNowTests(SimpleTestCase):

    # 2024-06-03 is a Monday.
    _MON_12H = dt_module.datetime(2024, 6, 3, 12, 0, tzinfo=timezone.utc)

    # ── None: unconfigured ───────────────────────────────────────────────────
    def test_none_schedule_returns_none(self):
        self.assertIsNone(schedule_open_now(None, self._MON_12H))

    def test_empty_dict_returns_none(self):
        self.assertIsNone(schedule_open_now({}, self._MON_12H))

    def test_non_dict_returns_none(self):
        self.assertIsNone(schedule_open_now("09:00-22:00", self._MON_12H))

    def test_no_enabled_day_returns_none(self):
        self.assertIsNone(schedule_open_now({"mon": {"enabled": False}}, self._MON_12H))

    # ── True / False: open window ─────────────────────────────────────────────
    def test_within_window_returns_true(self):
        self.assertTrue(schedule_open_now(_sched_for(self._MON_12H, open_="09:00", close_="18:00"), self._MON_12H))

    def test_before_open_returns_false(self):
        early = self._MON_12H.replace(hour=8)
        self.assertFalse(schedule_open_now(_sched_for(early, open_="09:00", close_="18:00"), early))

    def test_at_close_is_exclusive_returns_false(self):
        at_close = self._MON_12H.replace(hour=18, minute=0)
        self.assertFalse(schedule_open_now(_sched_for(at_close, open_="09:00", close_="18:00"), at_close))

    def test_just_before_close_returns_true(self):
        almost = self._MON_12H.replace(hour=17, minute=59)
        self.assertTrue(schedule_open_now(_sched_for(almost, open_="09:00", close_="18:00"), almost))

    def test_today_missing_from_schedule_returns_false(self):
        # Schedule only has Tuesday enabled; "now" is Monday → False (not None).
        tue = self._MON_12H.replace(day=4)  # 2024-06-04 is Tuesday
        sched = _sched_for(tue, open_="09:00", close_="18:00")
        self.assertFalse(schedule_open_now(sched, self._MON_12H))

    def test_today_disabled_returns_false(self):
        sched = {"mon": {"enabled": False, "open": "09:00", "close": "18:00"},
                 "tue": {"enabled": True, "open": "09:00", "close": "18:00"}}
        self.assertFalse(schedule_open_now(sched, self._MON_12H))

    def test_blank_open_returns_false(self):
        sched = {"mon": {"enabled": True, "open": "", "close": "18:00"}}
        self.assertFalse(schedule_open_now(sched, self._MON_12H))

    def test_blank_close_returns_false(self):
        sched = {"mon": {"enabled": True, "open": "09:00", "close": ""}}
        self.assertFalse(schedule_open_now(sched, self._MON_12H))


# ══════════════════════════════════════════════════════════════════════════════
# tenant_local_now — timezone resolution / fallback chain
# ══════════════════════════════════════════════════════════════════════════════

class TenantLocalNowTests(SimpleTestCase):

    def test_uses_profile_timezone(self):
        now = tenant_local_now(SimpleNamespace(timezone="America/New_York"))
        self.assertIsNotNone(now.tzinfo)
        self.assertEqual(str(now.tzinfo), "America/New_York")

    @override_settings(TIME_ZONE="Africa/Casablanca")
    def test_blank_timezone_falls_back_to_settings_time_zone(self):
        now = tenant_local_now(SimpleNamespace(timezone=""))
        self.assertEqual(str(now.tzinfo), "Africa/Casablanca")

    @override_settings(TIME_ZONE="Africa/Casablanca")
    def test_missing_timezone_attr_falls_back_to_settings(self):
        now = tenant_local_now(SimpleNamespace())  # no .timezone attribute
        self.assertEqual(str(now.tzinfo), "Africa/Casablanca")

    def test_invalid_timezone_falls_back_to_utc(self):
        now = tenant_local_now(SimpleNamespace(timezone="Not/AZone"))
        self.assertIsNotNone(now.tzinfo)
        self.assertEqual(now.utcoffset().total_seconds(), 0)  # UTC

    @override_settings(TIME_ZONE="")
    def test_blank_settings_and_blank_profile_falls_back_to_utc(self):
        now = tenant_local_now(SimpleNamespace(timezone=""))
        self.assertEqual(now.utcoffset().total_seconds(), 0)  # UTC


# ══════════════════════════════════════════════════════════════════════════════
# PARITY: the WINDOW verdict is identical across all three callers
# ══════════════════════════════════════════════════════════════════════════════

def _tz_aware_mock_dt(fixed_utc: dt_module.datetime):
    """datetime stand-in whose .now(tz) projects a FIXED UTC instant into the asked tz
    (and utcnow() returns it naive). Lets the same instant drive all three callers."""
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


def _no_closure():
    mock_qset = MagicMock()
    mock_qset.exists.return_value = False
    mock_cls = MagicMock()
    mock_cls.objects.filter.return_value = mock_qset
    return mock_cls


class WindowParityTests(SimpleTestCase):
    """For the same profile + business_hours_schedule + instant, the WINDOW verdict
    must be identical across _schedule_open, _compute_is_open_now, and get_is_open_now —
    the whole point of consolidating to one shared rule. Each caller layers its own
    extra guards (temp-disable, ClosureDate) which we hold neutral here so only the
    window rule is exercised."""

    _SCHEDULE = {
        "mon": {"enabled": True, "open": "09:00", "close": "22:00"},
        "tue": {"enabled": True, "open": "09:00", "close": "22:00"},
    }

    def _verdicts(self, instant, tz):
        """Return (schedule_open, compute_is_open_now, get_is_open_now) for an instant."""
        from menu.views import _schedule_open
        from accounts.views import _compute_is_open_now
        from tenancy.serializers import ProfileSerializer

        prof = SimpleNamespace(
            is_open=True,
            is_menu_temporarily_disabled=False,
            business_hours_schedule=self._SCHEDULE,
            timezone=tz,
        )
        with patch(_CLOSURE_PATH := "menu.models.ClosureDate", _no_closure()):
            with patch("datetime.datetime", _tz_aware_mock_dt(instant)):
                a = _schedule_open(prof)                 # tri-state True/False/None
                b = _compute_is_open_now(prof)           # bool (is_open + temp-disable guards neutral)
                c = ProfileSerializer.__new__(ProfileSerializer).get_is_open_now(prof)
        # _schedule_open returns the tri-state; for a configured schedule it is bool.
        return bool(a), b, c

    def test_open_instant_all_three_agree_open(self):
        # Monday 14:00 UTC, UTC tenant → inside 09:00–22:00 → open everywhere.
        instant = dt_module.datetime(2024, 6, 3, 14, 0, tzinfo=timezone.utc)
        a, b, c = self._verdicts(instant, tz="UTC")
        self.assertTrue(a and b and c, f"expected all-open, got {(a, b, c)}")

    def test_closed_instant_all_three_agree_closed(self):
        # Monday 23:00 UTC, UTC tenant → after 22:00 → closed everywhere.
        instant = dt_module.datetime(2024, 6, 3, 23, 0, tzinfo=timezone.utc)
        a, b, c = self._verdicts(instant, tz="UTC")
        self.assertFalse(a or b or c, f"expected all-closed, got {(a, b, c)}")

    def test_tenant_local_instant_all_three_agree(self):
        # 23:30 UTC Monday. NY (UTC-4) = 19:30 Monday local → inside window → all open.
        # Proves get_is_open_now is now on the tenant clock (was UTC) and matches the
        # other two callers that were already tenant-local.
        instant = dt_module.datetime(2024, 6, 3, 23, 30, tzinfo=timezone.utc)
        a, b, c = self._verdicts(instant, tz="America/New_York")
        self.assertTrue(a and b and c, f"expected all-open (tenant-local), got {(a, b, c)}")
