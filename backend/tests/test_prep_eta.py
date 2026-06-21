"""Unit tests for the pre-order ETA helper (menu/prep_eta.py).

Covers the prep-time range derivation used by the menu header + checkout ETA:
rolling-avg → configured default → platform default, rounding-to-5, and the
[p-5, p+10] widening with the MIN_FLOOR floor. The rolling-avg DB path is
exercised via use_history=False (no schema needed) plus a monkeypatched
rolling_avg in the history-preferred case.
"""

from types import SimpleNamespace

from django.test import SimpleTestCase

from menu import prep_eta
from menu.prep_eta import DEFAULT_PREP_MINUTES, MIN_FLOOR, prep_eta_range, _round_to_5


class RoundTo5Tests(SimpleTestCase):
    def test_rounds_to_nearest_five(self):
        self.assertEqual(_round_to_5(17), 15)
        self.assertEqual(_round_to_5(18), 20)
        self.assertEqual(_round_to_5(23), 25)
        self.assertEqual(_round_to_5(20), 20)


class PrepEtaRangeTests(SimpleTestCase):
    def test_platform_default_when_no_history_and_no_config(self):
        profile = SimpleNamespace(default_prep_minutes=None)
        lo, hi = prep_eta_range(profile, use_history=False)
        # point = DEFAULT_PREP_MINUTES (20) -> [15, 30]
        self.assertEqual((lo, hi), (DEFAULT_PREP_MINUTES - 5, DEFAULT_PREP_MINUTES + 10))

    def test_uses_configured_default_when_set(self):
        profile = SimpleNamespace(default_prep_minutes=30)
        lo, hi = prep_eta_range(profile, use_history=False)
        # 30 -> round5=30 -> [25, 40]
        self.assertEqual((lo, hi), (25, 40))

    def test_configured_default_rounds_to_five(self):
        profile = SimpleNamespace(default_prep_minutes=18)
        lo, hi = prep_eta_range(profile, use_history=False)
        # 18 -> round5=20 -> [15, 30]
        self.assertEqual((lo, hi), (15, 30))

    def test_min_floor_applies_for_tiny_prep(self):
        profile = SimpleNamespace(default_prep_minutes=3)
        lo, hi = prep_eta_range(profile, use_history=False)
        # 3 -> round5=5 -> lo=max(5, 0)=5, hi=max(10, 15)=15
        self.assertEqual(lo, MIN_FLOOR)
        self.assertGreaterEqual(hi, lo + 5)

    def test_range_is_ordered_and_lo_never_below_floor(self):
        for minutes in (None, 1, 5, 12, 20, 45, 90):
            profile = SimpleNamespace(default_prep_minutes=minutes)
            lo, hi = prep_eta_range(profile, use_history=False)
            self.assertGreaterEqual(lo, MIN_FLOOR)
            self.assertGreater(hi, lo)

    def test_garbage_configured_value_falls_back_to_platform_default(self):
        profile = SimpleNamespace(default_prep_minutes="not-a-number")
        lo, hi = prep_eta_range(profile, use_history=False)
        self.assertEqual((lo, hi), (DEFAULT_PREP_MINUTES - 5, DEFAULT_PREP_MINUTES + 10))

    def test_rolling_average_is_preferred_over_config(self):
        # When history yields a value, it wins over the configured default.
        self.addCleanup(setattr, prep_eta, "rolling_avg_prep_minutes",
                        prep_eta.rolling_avg_prep_minutes)
        prep_eta.rolling_avg_prep_minutes = lambda: 38.0
        profile = SimpleNamespace(default_prep_minutes=10)
        lo, hi = prep_eta_range(profile, use_history=True)
        # 38 -> round5=40 -> [35, 50]
        self.assertEqual((lo, hi), (35, 50))

    def test_falls_through_to_config_when_history_none(self):
        self.addCleanup(setattr, prep_eta, "rolling_avg_prep_minutes",
                        prep_eta.rolling_avg_prep_minutes)
        prep_eta.rolling_avg_prep_minutes = lambda: None
        profile = SimpleNamespace(default_prep_minutes=25)
        lo, hi = prep_eta_range(profile, use_history=True)
        # 25 -> [20, 35]
        self.assertEqual((lo, hi), (20, 35))
