"""Tests for the business-hours schedule helper (_schedule_open / _is_restaurant_currently_open).

The "current local time" is provided by _profile_now (timezone-aware); these tests patch it
to a fixed instant so the schedule logic is deterministic regardless of the real clock/tz.
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def _profile(is_open=True, schedule=None):
    return SimpleNamespace(is_open=is_open, business_hours_schedule=schedule, timezone="")


from menu.views import _schedule_open, _is_restaurant_currently_open


@pytest.fixture(autouse=True)
def closure_lookup():
    """Hold the ClosureDate lookup neutral (no DB) — default "not a closure date"."""
    with patch("menu.views.is_closure_date", return_value=False) as m:
        yield m

_MON_NOON = datetime(2025, 5, 5, 12, 0)   # Monday 12:00
_MON_0700 = datetime(2025, 5, 5, 7, 0)    # Monday 07:00
_MON_2300 = datetime(2025, 5, 5, 23, 0)   # Monday 23:00
_MON_0900 = datetime(2025, 5, 5, 9, 0)    # Monday 09:00 (open edge)
_MON_2200 = datetime(2025, 5, 5, 22, 0)   # Monday 22:00 (close edge)
_TUE_NOON = datetime(2025, 5, 6, 12, 0)   # Tuesday 12:00


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
        with patch("menu.views._profile_now", return_value=_MON_NOON):
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            assert _schedule_open(_profile(schedule=schedule)) is True

    def test_before_open_returns_false(self):
        with patch("menu.views._profile_now", return_value=_MON_0700):
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            assert _schedule_open(_profile(schedule=schedule)) is False

    def test_after_close_returns_false(self):
        with patch("menu.views._profile_now", return_value=_MON_2300):
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            assert _schedule_open(_profile(schedule=schedule)) is False

    def test_exactly_at_open_time_returns_true(self):
        with patch("menu.views._profile_now", return_value=_MON_0900):
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            assert _schedule_open(_profile(schedule=schedule)) is True

    def test_exactly_at_close_time_returns_false(self):
        """close time is exclusive (>=open and <close)."""
        with patch("menu.views._profile_now", return_value=_MON_2200):
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            assert _schedule_open(_profile(schedule=schedule)) is False

    def test_day_not_in_schedule_returns_false(self):
        with patch("menu.views._profile_now", return_value=_TUE_NOON):
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            assert _schedule_open(_profile(schedule=schedule)) is False

    def test_day_disabled_returns_false(self):
        with patch("menu.views._profile_now", return_value=_MON_NOON):
            schedule = {
                "mon": {"enabled": False, "open": "09:00", "close": "22:00"},
                "tue": {"enabled": True, "open": "09:00", "close": "22:00"},
            }
            assert _schedule_open(_profile(schedule=schedule)) is False


class TestIsRestaurantCurrentlyOpen:
    def test_manual_closed_overrides_everything(self):
        with patch("menu.views._profile_now", return_value=_MON_NOON):
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            assert _is_restaurant_currently_open(_profile(is_open=False, schedule=schedule)) is False

    def test_open_with_matching_schedule_returns_true(self):
        with patch("menu.views._profile_now", return_value=_MON_NOON):
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            assert _is_restaurant_currently_open(_profile(schedule=schedule)) is True

    def test_open_outside_schedule_returns_false(self):
        with patch("menu.views._profile_now", return_value=_MON_2300):
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            assert _is_restaurant_currently_open(_profile(schedule=schedule)) is False

    def test_no_schedule_relies_on_is_open_true(self):
        assert _is_restaurant_currently_open(_profile(is_open=True, schedule=None)) is True

    def test_no_schedule_relies_on_is_open_false(self):
        assert _is_restaurant_currently_open(_profile(is_open=False, schedule=None)) is False

    # ── Holiday / closure dates ────────────────────────────────────────────────
    # The ASAP order gate must refuse on an owner-declared closure date, exactly like the
    # customer UI (ProfileSerializer.is_open_now) already shows "closed" — otherwise a stale
    # tab or direct API call could place an ASAP order on a holiday.

    def test_closure_date_closes_even_inside_the_schedule_window(self, closure_lookup):
        closure_lookup.return_value = True
        with patch("menu.views._profile_now", return_value=_MON_NOON):
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            assert _is_restaurant_currently_open(_profile(schedule=schedule)) is False

    def test_closure_date_closes_even_with_no_schedule(self, closure_lookup):
        closure_lookup.return_value = True
        assert _is_restaurant_currently_open(_profile(is_open=True, schedule=None)) is False

    def test_closure_lookup_receives_the_tenant_local_date(self, closure_lookup):
        with patch("menu.views._profile_now", return_value=_MON_NOON):
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            _is_restaurant_currently_open(_profile(schedule=schedule))
        closure_lookup.assert_called_once_with(_MON_NOON.date())

    def test_not_a_closure_date_leaves_the_schedule_verdict_unchanged(self, closure_lookup):
        closure_lookup.return_value = False
        with patch("menu.views._profile_now", return_value=_MON_NOON):
            schedule = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
            assert _is_restaurant_currently_open(_profile(schedule=schedule)) is True

    def test_manual_closed_short_circuits_before_the_closure_lookup(self, closure_lookup):
        assert _is_restaurant_currently_open(_profile(is_open=False)) is False
        closure_lookup.assert_not_called()
