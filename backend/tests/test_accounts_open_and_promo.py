"""
Unit tests for accounts/views.py private helpers:
  - _compute_is_open_now
  - _is_promo_active_now  (accounts.views version — distinct from menu.views)

All tests are unit-level (SimpleTestCase + mocks — no real DB).
datetime.datetime is patched for time-dependent cases.
"""
import datetime as dt_module
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from accounts.views import _compute_is_open_now, _is_promo_active_now


# 2024-06-03 is Monday (weekday 0); 2024-06-04 is Tuesday (weekday 1)
_MON_14H = dt_module.datetime(2024, 6, 3, 14, 30, 0)   # Mon 14:30 UTC
_MON_8H  = dt_module.datetime(2024, 6, 3,  8,  0, 0)   # Mon 08:00 UTC
_MON_22H = dt_module.datetime(2024, 6, 3, 22, 30, 0)   # Mon 22:30 UTC
_TUE_14H = dt_module.datetime(2024, 6, 4, 14, 30, 0)   # Tue 14:30 UTC


def _mock_dt(fixed_now: dt_module.datetime):
    class _M(dt_module.datetime):
        @classmethod
        def utcnow(cls):
            return fixed_now
    return _M


def _profile(
    *,
    is_open=True,
    is_menu_temporarily_disabled=False,
    business_hours_schedule=None,
):
    return SimpleNamespace(
        is_open=is_open,
        is_menu_temporarily_disabled=is_menu_temporarily_disabled,
        business_hours_schedule=business_hours_schedule,
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
        self.assertFalse(_is_promo_active_now(_promo(active_from=date.today() + timedelta(days=1))))

    def test_past_active_from_returns_true(self):
        self.assertTrue(_is_promo_active_now(_promo(active_from=date.today() - timedelta(days=1))))

    def test_today_as_active_from_returns_true(self):
        self.assertTrue(_is_promo_active_now(_promo(active_from=date.today())))

    def test_expired_active_until_returns_false(self):
        self.assertFalse(_is_promo_active_now(_promo(active_until=date.today() - timedelta(days=1))))

    def test_future_active_until_returns_true(self):
        self.assertTrue(_is_promo_active_now(_promo(active_until=date.today() + timedelta(days=1))))

    def test_today_as_active_until_returns_true(self):
        self.assertTrue(_is_promo_active_now(_promo(active_until=date.today())))

    # ── day restriction ───────────────────────────────────────────────────────
    def test_all_days_allowed_returns_true(self):
        all_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        self.assertTrue(_is_promo_active_now(_promo(days=all_days)))

    def test_wrong_day_returns_false(self):
        # Mock Monday, schedule only allows tuesday
        class _M(dt_module.datetime):
            @classmethod
            def utcnow(cls):
                return _MON_14H
        with patch("datetime.datetime", _M):
            self.assertFalse(_is_promo_active_now(_promo(days=["tue", "wed"])))

    def test_matching_day_returns_true(self):
        class _M(dt_module.datetime):
            @classmethod
            def utcnow(cls):
                return _MON_14H
        with patch("datetime.datetime", _M):
            self.assertTrue(_is_promo_active_now(_promo(days=["mon"])))

    def test_empty_days_no_restriction_returns_true(self):
        self.assertTrue(_is_promo_active_now(_promo(days=[])))

    # ── time window check ─────────────────────────────────────────────────────
    def test_within_time_window_returns_true(self):
        class _M(dt_module.datetime):
            @classmethod
            def utcnow(cls):
                return _MON_14H   # 14:30
        with patch("datetime.datetime", _M):
            self.assertTrue(_is_promo_active_now(_promo(time_start="09:00", time_end="22:00")))

    def test_before_time_window_returns_false(self):
        class _M(dt_module.datetime):
            @classmethod
            def utcnow(cls):
                return _MON_8H    # 08:00
        with patch("datetime.datetime", _M):
            self.assertFalse(_is_promo_active_now(_promo(time_start="09:00", time_end="22:00")))

    def test_after_time_window_returns_false(self):
        class _M(dt_module.datetime):
            @classmethod
            def utcnow(cls):
                return _MON_22H   # 22:30
        with patch("datetime.datetime", _M):
            self.assertFalse(_is_promo_active_now(_promo(time_start="09:00", time_end="22:00")))

    def test_no_time_restriction_returns_true(self):
        self.assertTrue(_is_promo_active_now(_promo(time_start="", time_end="")))

    def test_partial_time_restriction_no_effect(self):
        """Only time_start set — both needed → no filter applied."""
        self.assertTrue(_is_promo_active_now(_promo(time_start="09:00", time_end="")))
