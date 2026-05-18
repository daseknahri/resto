"""Tests for the business-hours schedule helper (_schedule_open / _is_restaurant_currently_open)."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def _profile(is_open=True, schedule=None):
    return SimpleNamespace(is_open=is_open, business_hours_schedule=schedule)


# ── Import helpers ──────────────────────────────────────────────────────────────
from menu.views import _schedule_open, _is_restaurant_currently_open


class TestScheduleOpen:
    def test_no_schedule_returns_none(self):
        assert _schedule_open(_profile(schedule=None)) is None

    def test_empty_schedule_returns_none(self):
        assert _schedule_open(_profile(schedule={})) is None

    def test_schedule_with_no_enabled_days_returns_none(self):
        schedule = {
            "mon": {"enabled": False, "open": "09:00", "close": "22:00"},
            "tue": {"enabled": False, "open": "09:00", "close": "22:00"},
        }
        assert _schedule_open(_profile(schedule=schedule)) is None

    def test_within_hours_returns_true(self):
        # Patch utcnow to a known Monday at 12:00
        from datetime import datetime
        with patch("menu.views.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2025, 5, 5, 12, 0)  # Monday
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            assert _schedule_open(_profile(schedule=schedule)) is True

    def test_before_open_returns_false(self):
        from datetime import datetime
        with patch("menu.views.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2025, 5, 5, 7, 0)  # Monday 07:00
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            assert _schedule_open(_profile(schedule=schedule)) is False

    def test_after_close_returns_false(self):
        from datetime import datetime
        with patch("menu.views.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2025, 5, 5, 23, 0)  # Monday 23:00
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            assert _schedule_open(_profile(schedule=schedule)) is False

    def test_exactly_at_open_time_returns_true(self):
        from datetime import datetime
        with patch("menu.views.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2025, 5, 5, 9, 0)  # Monday 09:00
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            assert _schedule_open(_profile(schedule=schedule)) is True

    def test_exactly_at_close_time_returns_false(self):
        """close time is exclusive (>=open and <close)."""
        from datetime import datetime
        with patch("menu.views.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2025, 5, 5, 22, 0)  # Monday 22:00
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            assert _schedule_open(_profile(schedule=schedule)) is False

    def test_day_not_in_schedule_returns_false(self):
        from datetime import datetime
        with patch("menu.views.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2025, 5, 6, 12, 0)  # Tuesday
            # Only Monday configured
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            assert _schedule_open(_profile(schedule=schedule)) is False

    def test_day_disabled_returns_false(self):
        from datetime import datetime
        with patch("menu.views.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2025, 5, 5, 12, 0)  # Monday
            schedule = {
                "mon": {"enabled": False, "open": "09:00", "close": "22:00"},
                "tue": {"enabled": True, "open": "09:00", "close": "22:00"},
            }
            assert _schedule_open(_profile(schedule=schedule)) is False


class TestIsRestaurantCurrentlyOpen:
    def test_manual_closed_overrides_everything(self):
        from datetime import datetime
        with patch("menu.views.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2025, 5, 5, 12, 0)
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            p = _profile(is_open=False, schedule=schedule)
            assert _is_restaurant_currently_open(p) is False

    def test_open_with_matching_schedule_returns_true(self):
        from datetime import datetime
        with patch("menu.views.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2025, 5, 5, 12, 0)
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            assert _is_restaurant_currently_open(_profile(schedule=schedule)) is True

    def test_open_outside_schedule_returns_false(self):
        from datetime import datetime
        with patch("menu.views.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2025, 5, 5, 23, 0)
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            assert _is_restaurant_currently_open(_profile(schedule=schedule)) is False

    def test_no_schedule_relies_on_is_open_true(self):
        assert _is_restaurant_currently_open(_profile(is_open=True, schedule=None)) is True

    def test_no_schedule_relies_on_is_open_false(self):
        assert _is_restaurant_currently_open(_profile(is_open=False, schedule=None)) is False
