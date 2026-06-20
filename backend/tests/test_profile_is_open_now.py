"""
Unit tests for ProfileSerializer.get_is_open_now in tenancy/serializers.py.

The method evaluates whether a restaurant is currently open by combining (in order):
  1. The manual is_open boolean toggle
  2. The is_menu_temporarily_disabled toggle (added in the open-state consolidation —
     so the customer menu page agrees with the marketplace listing card)
  3. An optional ClosureDate DB check (mocked; caught by try/except) — serializer-only
  4. The structured business_hours_schedule dict, evaluated in the restaurant's OWN
     timezone (was UTC — that was the bug) via the SHARED rule
     tenancy.openstate.schedule_open_now / tenant_local_now.

Branches:
  - is_open is False → False regardless of schedule
  - is_menu_temporarily_disabled True → False
  - No schedule / non-dict schedule → falls back to bool(is_open)
  - Schedule with no enabled days → falls back to bool(is_open)
  - Today's schedule entry not present → False
  - Today's entry not enabled → False
  - Entry enabled but open/close missing → False
  - Current tenant-local time within [open, close) → True
  - Current tenant-local time outside [open, close) → False

All tests are unit-level (SimpleTestCase — ClosureDate DB call is mocked,
datetime is patched so the tenant-local "now" is deterministic).
"""
import datetime as dt_module
from datetime import timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from tenancy.serializers import ProfileSerializer


# ── helpers ───────────────────────────────────────────────────────────────────

def _ser():
    return ProfileSerializer.__new__(ProfileSerializer)


def _profile(*, is_open=True, schedule=None, timezone="UTC", is_menu_temporarily_disabled=False):
    return SimpleNamespace(
        is_open=is_open,
        business_hours_schedule=schedule,
        timezone=timezone,
        is_menu_temporarily_disabled=is_menu_temporarily_disabled,
    )


def _schedule(weekday_name, *, enabled=True, open_time="09:00", close_time="22:00"):
    return {weekday_name: {"enabled": enabled, "open": open_time, "close": close_time}}


# ClosureDate is lazily imported inside get_is_open_now, so we patch
# it at its source in menu.models rather than at the usage site.
_CLOSURE_DATE_PATH = "menu.models.ClosureDate"


def _no_closure():
    """Return a mock ClosureDate class where .objects.filter().exists() → False."""
    mock_qset = MagicMock()
    mock_qset.exists.return_value = False
    mock_cls = MagicMock()
    mock_cls.objects.filter.return_value = mock_qset
    return mock_cls


def _tz_aware_mock_dt(fixed_utc: dt_module.datetime):
    """datetime stand-in whose .now(tz) converts a FIXED UTC instant into the asked
    tz — so a test can prove the schedule is read in the tenant's wall-clock, not the
    server's. tenant_local_now() calls datetime.now(ZoneInfo(profile.timezone))."""
    class _M(dt_module.datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_utc.replace(tzinfo=None)
            return fixed_utc.astimezone(tz)
    return _M


# ══════════════════════════════════════════════════════════════════════════════
# is_open=False → always False
# ══════════════════════════════════════════════════════════════════════════════

class IsOpenFalseTests(SimpleTestCase):

    def test_manually_closed_returns_false_no_schedule(self):
        result = _ser().get_is_open_now(_profile(is_open=False))
        self.assertFalse(result)

    def test_manually_closed_returns_false_even_with_open_schedule(self):
        sched = _schedule("mon", enabled=True, open_time="00:00", close_time="23:59")
        result = _ser().get_is_open_now(_profile(is_open=False, schedule=sched))
        self.assertFalse(result)


# ══════════════════════════════════════════════════════════════════════════════
# is_menu_temporarily_disabled → False (parity with the marketplace listing card)
# ══════════════════════════════════════════════════════════════════════════════

class TempDisabledTests(SimpleTestCase):

    def test_temporarily_disabled_returns_false_no_schedule(self):
        with patch(_CLOSURE_DATE_PATH, _no_closure()):
            result = _ser().get_is_open_now(
                _profile(is_open=True, schedule=None, is_menu_temporarily_disabled=True)
            )
        self.assertFalse(result)

    def test_temporarily_disabled_returns_false_even_with_open_schedule(self):
        # Monday 12:00 UTC is inside 09:00–22:00 → would be open, but temp-disabled wins.
        instant = dt_module.datetime(2024, 6, 3, 12, 0, 0, tzinfo=timezone.utc)
        sched = _schedule("mon", open_time="09:00", close_time="22:00")
        with patch(_CLOSURE_DATE_PATH, _no_closure()):
            with patch("datetime.datetime", _tz_aware_mock_dt(instant)):
                result = _ser().get_is_open_now(
                    _profile(is_open=True, schedule=sched, timezone="UTC",
                             is_menu_temporarily_disabled=True)
                )
        self.assertFalse(result)


# ══════════════════════════════════════════════════════════════════════════════
# No schedule / unconfigured schedule
# ══════════════════════════════════════════════════════════════════════════════

class NoScheduleTests(SimpleTestCase):

    def test_no_schedule_open_restaurant_returns_true(self):
        with patch(_CLOSURE_DATE_PATH, _no_closure()):
            result = _ser().get_is_open_now(_profile(is_open=True, schedule=None))
        self.assertTrue(result)

    def test_no_schedule_closed_restaurant_returns_false(self):
        with patch(_CLOSURE_DATE_PATH, _no_closure()):
            result = _ser().get_is_open_now(_profile(is_open=False, schedule=None))
        self.assertFalse(result)

    def test_non_dict_schedule_falls_back_to_is_open(self):
        with patch(_CLOSURE_DATE_PATH, _no_closure()):
            result = _ser().get_is_open_now(_profile(is_open=True, schedule="bad"))
        self.assertTrue(result)

    def test_empty_dict_schedule_falls_back_to_is_open(self):
        with patch(_CLOSURE_DATE_PATH, _no_closure()):
            result = _ser().get_is_open_now(_profile(is_open=True, schedule={}))
        self.assertTrue(result)

    def test_all_disabled_days_falls_back_to_is_open(self):
        """If every day has enabled=False, the schedule is unconfigured → fallback."""
        sched = {"mon": {"enabled": False}, "tue": {"enabled": False}}
        with patch(_CLOSURE_DATE_PATH, _no_closure()):
            result = _ser().get_is_open_now(_profile(is_open=True, schedule=sched))
        self.assertTrue(result)


# ══════════════════════════════════════════════════════════════════════════════
# Schedule-based checks (today's entry) — evaluated in the tenant's local clock
# ══════════════════════════════════════════════════════════════════════════════

class ScheduleBasedTests(SimpleTestCase):

    def _run(self, schedule, *, fixed_utc, tz="UTC"):
        """Call get_is_open_now with a frozen instant so we control day/time. The
        profile timezone defaults to UTC, so for a UTC tenant the local wall-clock
        equals the UTC instant — convenient for the day/time-window cases."""
        with patch(_CLOSURE_DATE_PATH, _no_closure()):
            with patch("datetime.datetime", _tz_aware_mock_dt(fixed_utc)):
                return _ser().get_is_open_now(_profile(is_open=True, schedule=schedule, timezone=tz))

    def test_current_time_within_open_window_returns_true(self):
        sched = _schedule("mon", open_time="09:00", close_time="22:00")
        # 2024-06-03 is Monday; 12:00 UTC.
        instant = dt_module.datetime(2024, 6, 3, 12, 0, 0, tzinfo=timezone.utc)
        self.assertTrue(self._run(sched, fixed_utc=instant))

    def test_current_time_before_opening_returns_false(self):
        sched = _schedule("mon", open_time="09:00", close_time="22:00")
        instant = dt_module.datetime(2024, 6, 3, 8, 0, 0, tzinfo=timezone.utc)
        self.assertFalse(self._run(sched, fixed_utc=instant))

    def test_current_time_at_closing_returns_false(self):
        """close time is exclusive: [open, close)."""
        sched = _schedule("mon", open_time="09:00", close_time="22:00")
        instant = dt_module.datetime(2024, 6, 3, 22, 0, 0, tzinfo=timezone.utc)
        self.assertFalse(self._run(sched, fixed_utc=instant))

    def test_current_time_just_before_closing_returns_true(self):
        sched = _schedule("mon", open_time="09:00", close_time="22:00")
        instant = dt_module.datetime(2024, 6, 3, 21, 59, 0, tzinfo=timezone.utc)
        self.assertTrue(self._run(sched, fixed_utc=instant))

    def test_today_not_in_schedule_returns_false(self):
        """Wednesday (2024-06-05) has no entry in a Mon-only schedule."""
        sched = _schedule("mon", open_time="09:00", close_time="22:00")
        instant = dt_module.datetime(2024, 6, 5, 12, 0, 0, tzinfo=timezone.utc)
        self.assertFalse(self._run(sched, fixed_utc=instant))

    def test_today_disabled_but_other_day_enabled_returns_false(self):
        """Today (Monday) is disabled; Tuesday is enabled. Should return False for today."""
        sched = {
            "mon": {"enabled": False, "open": "09:00", "close": "22:00"},
            "tue": {"enabled": True, "open": "09:00", "close": "22:00"},
        }
        instant = dt_module.datetime(2024, 6, 3, 12, 0, 0, tzinfo=timezone.utc)  # Monday
        self.assertFalse(self._run(sched, fixed_utc=instant))

    def test_missing_open_time_returns_false(self):
        sched = {"mon": {"enabled": True, "open": "", "close": "22:00"}}
        instant = dt_module.datetime(2024, 6, 3, 12, 0, 0, tzinfo=timezone.utc)
        self.assertFalse(self._run(sched, fixed_utc=instant))

    def test_missing_close_time_returns_false(self):
        sched = {"mon": {"enabled": True, "open": "09:00", "close": ""}}
        instant = dt_module.datetime(2024, 6, 3, 12, 0, 0, tzinfo=timezone.utc)
        self.assertFalse(self._run(sched, fixed_utc=instant))


# ══════════════════════════════════════════════════════════════════════════════
# Schedule evaluated in TENANT-LOCAL time (fixes the historic UTC bug)
# ══════════════════════════════════════════════════════════════════════════════

class TenantLocalScheduleTests(SimpleTestCase):
    """A single fixed instant + a fixed schedule yields a DIFFERENT verdict per
    timezone — proving the weekday/HH:MM are derived in the tenant's local clock,
    not in UTC (the bug that made the menu page disagree with the listing card)."""

    # 2024-06-03 23:30 UTC. UTC weekday = Monday 23:30 (past close);
    # America/New_York (EDT, UTC-4) is Monday 19:30 local (inside 09:00–22:00).
    _SCHEDULE = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
    _INSTANT = dt_module.datetime(2024, 6, 3, 23, 30, 0, tzinfo=timezone.utc)

    def test_tenant_local_open_when_utc_would_say_closed(self):
        prof = _profile(is_open=True, schedule=self._SCHEDULE, timezone="America/New_York")
        with patch(_CLOSURE_DATE_PATH, _no_closure()):
            with patch("datetime.datetime", _tz_aware_mock_dt(self._INSTANT)):
                self.assertTrue(_ser().get_is_open_now(prof))

    def test_utc_tenant_closed_at_same_instant(self):
        prof = _profile(is_open=True, schedule=self._SCHEDULE, timezone="UTC")
        with patch(_CLOSURE_DATE_PATH, _no_closure()):
            with patch("datetime.datetime", _tz_aware_mock_dt(self._INSTANT)):
                self.assertFalse(_ser().get_is_open_now(prof))

    def test_invalid_timezone_falls_back_to_utc(self):
        prof = _profile(is_open=True, schedule=self._SCHEDULE, timezone="Not/AZone")
        with patch(_CLOSURE_DATE_PATH, _no_closure()):
            with patch("datetime.datetime", _tz_aware_mock_dt(self._INSTANT)):
                self.assertFalse(_ser().get_is_open_now(prof))


# ══════════════════════════════════════════════════════════════════════════════
# ClosureDate interaction
# ══════════════════════════════════════════════════════════════════════════════

class ClosureDateTests(SimpleTestCase):

    def test_closure_date_match_returns_false(self):
        """When today is a closure date, the restaurant is closed regardless of schedule."""
        mock_qset = MagicMock()
        mock_qset.exists.return_value = True
        mock_cls = MagicMock()
        mock_cls.objects.filter.return_value = mock_qset

        with patch(_CLOSURE_DATE_PATH, mock_cls):
            result = _ser().get_is_open_now(_profile(is_open=True, schedule=None))
        self.assertFalse(result)

    def test_closure_date_exception_is_swallowed(self):
        """If the ClosureDate query raises, it is caught and execution continues."""
        mock_qset = MagicMock()
        mock_qset.exists.side_effect = Exception("DB offline")
        mock_cls = MagicMock()
        mock_cls.objects.filter.return_value = mock_qset

        with patch(_CLOSURE_DATE_PATH, mock_cls):
            # No schedule → falls back to is_open
            result = _ser().get_is_open_now(_profile(is_open=True, schedule=None))
        self.assertTrue(result)
