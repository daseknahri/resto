"""
Unit tests for ProfileSerializer.get_is_open_now in tenancy/serializers.py.

The method evaluates whether a restaurant is currently open by combining:
  1. The manual is_open boolean toggle
  2. An optional ClosureDate DB check (mocked; caught by try/except)
  3. The structured business_hours_schedule dict

Branches:
  - is_open is False → False regardless of schedule
  - No schedule / non-dict schedule → falls back to bool(is_open)
  - Schedule with no enabled days → falls back to bool(is_open)
  - Today's schedule entry not present → False
  - Today's entry not enabled → False
  - Entry enabled but open/close missing → False
  - Current time within [open, close) → True
  - Current time outside [open, close) → False

All tests are unit-level (SimpleTestCase — ClosureDate DB call is mocked,
datetime.utcnow() is frozen via patch).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from tenancy.serializers import ProfileSerializer


# ── helpers ───────────────────────────────────────────────────────────────────

def _ser():
    return ProfileSerializer.__new__(ProfileSerializer)


def _profile(*, is_open=True, schedule=None):
    return SimpleNamespace(is_open=is_open, business_hours_schedule=schedule)


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
# Schedule-based checks (today's entry)
# ══════════════════════════════════════════════════════════════════════════════

class ScheduleBasedTests(SimpleTestCase):

    def _run(self, schedule, fake_now_hhmm, fake_weekday):
        """
        Call get_is_open_now with a frozen datetime so we control which
        day/time is evaluated.
        fake_now_hhmm: "HH:MM" string
        fake_weekday:  int 0=Monday ... 6=Sunday
        """
        from datetime import datetime
        fake_dt = MagicMock(spec=datetime)
        fake_dt.weekday.return_value = fake_weekday
        fake_dt.strftime.return_value = fake_now_hhmm

        # datetime is lazily imported as `from datetime import datetime as _dt`
        # inside the method; patch at the source.
        with patch(_CLOSURE_DATE_PATH, _no_closure()):
            with patch("datetime.datetime") as mock_dt:
                mock_dt.utcnow.return_value = fake_dt
                return _ser().get_is_open_now(_profile(is_open=True, schedule=schedule))

    def test_current_time_within_open_window_returns_true(self):
        sched = _schedule("mon", open_time="09:00", close_time="22:00")
        self.assertTrue(self._run(sched, fake_now_hhmm="12:00", fake_weekday=0))  # Monday noon

    def test_current_time_before_opening_returns_false(self):
        sched = _schedule("mon", open_time="09:00", close_time="22:00")
        self.assertFalse(self._run(sched, fake_now_hhmm="08:00", fake_weekday=0))

    def test_current_time_at_closing_returns_false(self):
        """close time is exclusive: [open, close)."""
        sched = _schedule("mon", open_time="09:00", close_time="22:00")
        self.assertFalse(self._run(sched, fake_now_hhmm="22:00", fake_weekday=0))

    def test_current_time_just_before_closing_returns_true(self):
        sched = _schedule("mon", open_time="09:00", close_time="22:00")
        self.assertTrue(self._run(sched, fake_now_hhmm="21:59", fake_weekday=0))

    def test_today_not_in_schedule_returns_false(self):
        """Wednesday (2) has no entry in a Mon-only schedule."""
        sched = _schedule("mon", open_time="09:00", close_time="22:00")
        self.assertFalse(self._run(sched, fake_now_hhmm="12:00", fake_weekday=2))

    def test_today_disabled_but_other_day_enabled_returns_false(self):
        """Today (Monday) is disabled; Tuesday is enabled. Should return False for today."""
        sched = {
            "mon": {"enabled": False, "open": "09:00", "close": "22:00"},
            "tue": {"enabled": True, "open": "09:00", "close": "22:00"},
        }
        # Monday (0): entry exists but enabled=False → entry.get("enabled") is False → False
        self.assertFalse(self._run(sched, fake_now_hhmm="12:00", fake_weekday=0))

    def test_missing_open_time_returns_false(self):
        sched = {"mon": {"enabled": True, "open": "", "close": "22:00"}}
        self.assertFalse(self._run(sched, fake_now_hhmm="12:00", fake_weekday=0))

    def test_missing_close_time_returns_false(self):
        sched = {"mon": {"enabled": True, "open": "09:00", "close": ""}}
        self.assertFalse(self._run(sched, fake_now_hhmm="12:00", fake_weekday=0))


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
