"""
Unit tests for distance-based delivery pricing (tenancy/delivery_pricing.py):
the per-restaurant base + per-km model, the flat fallback, the free-over
threshold, and the out-of-range guard. Pure functions → SimpleTestCase.
"""
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from tenancy.delivery_pricing import (
    compute_delivery_fee,
    haversine_km,
    split_delivery_fee,
    valid_coord,
)


def _profile(**kw):
    base = dict(
        delivery_fee=0,
        delivery_base_fee=0,
        delivery_per_km=0,
        delivery_free_over=0,
        delivery_radius_km=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


class HaversineTests(SimpleTestCase):
    def test_zero_distance(self):
        self.assertEqual(haversine_km(33.59, -7.62, 33.59, -7.62), 0.0)

    def test_known_distance_casablanca_rabat(self):
        # Casablanca → Rabat is ~86 km as the crow flies.
        km = haversine_km(33.5731, -7.5898, 34.0209, -6.8416)
        self.assertTrue(80 < km < 95, f"expected ~86 km, got {km}")

    def test_missing_coord_returns_zero(self):
        self.assertEqual(haversine_km(None, 1, 2, 3), 0.0)


class FlatFallbackTests(SimpleTestCase):
    def test_flat_when_per_km_zero(self):
        r = compute_delivery_fee(_profile(delivery_fee=Decimal("10")), distance_km=5, food_subtotal=Decimal("50"))
        self.assertEqual(r["fee"], Decimal("10.00"))
        self.assertEqual(r["mode"], "flat")
        self.assertFalse(r["out_of_range"])

    def test_flat_when_no_distance(self):
        # per-km set, but no coordinates → falls back to flat fee.
        r = compute_delivery_fee(
            _profile(delivery_fee=Decimal("8"), delivery_per_km=Decimal("2")),
            distance_km=None,
            food_subtotal=Decimal("50"),
        )
        self.assertEqual(r["fee"], Decimal("8.00"))
        self.assertEqual(r["mode"], "flat")


class DistancePricingTests(SimpleTestCase):
    def test_base_plus_per_km(self):
        r = compute_delivery_fee(
            _profile(delivery_base_fee=Decimal("5"), delivery_per_km=Decimal("2")),
            distance_km=3,
            food_subtotal=Decimal("40"),
        )
        # 5 + 2*3 = 11
        self.assertEqual(r["fee"], Decimal("11.00"))
        self.assertEqual(r["mode"], "distance")
        self.assertEqual(r["distance_km"], 3.0)

    def test_rounds_to_cents(self):
        r = compute_delivery_fee(
            _profile(delivery_base_fee=Decimal("0"), delivery_per_km=Decimal("1.5")),
            distance_km=2.3,
            food_subtotal=Decimal("40"),
        )
        # 1.5 * 2.3 = 3.45
        self.assertEqual(r["fee"], Decimal("3.45"))


class FreeOverTests(SimpleTestCase):
    def test_free_over_threshold_distance(self):
        r = compute_delivery_fee(
            _profile(delivery_base_fee=Decimal("5"), delivery_per_km=Decimal("2"), delivery_free_over=Decimal("100")),
            distance_km=4,
            food_subtotal=Decimal("120"),
        )
        self.assertEqual(r["fee"], Decimal("0.00"))
        self.assertTrue(r["free"])

    def test_free_over_threshold_flat(self):
        r = compute_delivery_fee(
            _profile(delivery_fee=Decimal("10"), delivery_free_over=Decimal("100")),
            distance_km=None,
            food_subtotal=Decimal("100"),
        )
        self.assertEqual(r["fee"], Decimal("0.00"))
        self.assertTrue(r["free"])

    def test_below_threshold_charges(self):
        r = compute_delivery_fee(
            _profile(delivery_fee=Decimal("10"), delivery_free_over=Decimal("100")),
            distance_km=None,
            food_subtotal=Decimal("99.99"),
        )
        self.assertEqual(r["fee"], Decimal("10.00"))
        self.assertFalse(r["free"])


class OutOfRangeTests(SimpleTestCase):
    def test_beyond_radius_is_out_of_range(self):
        r = compute_delivery_fee(
            _profile(delivery_base_fee=Decimal("5"), delivery_per_km=Decimal("2"), delivery_radius_km=5),
            distance_km=8,
            food_subtotal=Decimal("40"),
        )
        self.assertTrue(r["out_of_range"])
        self.assertEqual(r["fee"], Decimal("0.00"))

    def test_within_radius_ok(self):
        r = compute_delivery_fee(
            _profile(delivery_base_fee=Decimal("5"), delivery_per_km=Decimal("2"), delivery_radius_km=10),
            distance_km=8,
            food_subtotal=Decimal("40"),
        )
        self.assertFalse(r["out_of_range"])
        self.assertEqual(r["fee"], Decimal("21.00"))  # 5 + 2*8

    def test_radius_not_enforced_without_distance(self):
        # No coordinates → cannot be out of range; falls back to flat.
        r = compute_delivery_fee(
            _profile(delivery_fee=Decimal("10"), delivery_radius_km=5),
            distance_km=None,
            food_subtotal=Decimal("40"),
        )
        self.assertFalse(r["out_of_range"])
        self.assertEqual(r["fee"], Decimal("10.00"))

    def test_free_over_does_not_apply_when_out_of_range(self):
        # Out-of-range takes precedence over the free-over threshold.
        r = compute_delivery_fee(
            _profile(delivery_per_km=Decimal("2"), delivery_free_over=Decimal("50"), delivery_radius_km=5),
            distance_km=9,
            food_subtotal=Decimal("80"),
        )
        self.assertTrue(r["out_of_range"])
        self.assertFalse(r["free"])


class FallbackGuardTests(SimpleTestCase):
    def test_distance_pricing_no_coords_falls_back_to_base_not_free(self):
        # per_km configured but no distance (no coords) + flat 0 → must NOT be free.
        r = compute_delivery_fee(
            _profile(delivery_per_km=Decimal("2"), delivery_base_fee=Decimal("7"), delivery_fee=Decimal("0")),
            distance_km=None, food_subtotal=Decimal("40"),
        )
        self.assertEqual(r["fee"], Decimal("7.00"))
        self.assertEqual(r["mode"], "flat")
        self.assertFalse(r["free"])

    def test_flat_pricing_no_coords_uses_flat(self):
        r = compute_delivery_fee(
            _profile(delivery_fee=Decimal("9")), distance_km=None, food_subtotal=Decimal("40"),
        )
        self.assertEqual(r["fee"], Decimal("9.00"))

    def test_absurd_distance_is_out_of_range_without_a_radius(self):
        # A bogus far-away coordinate must be refused even when no radius is configured.
        r = compute_delivery_fee(
            _profile(delivery_per_km=Decimal("2")), distance_km=250, food_subtotal=Decimal("40"),
        )
        self.assertTrue(r["out_of_range"])


class ValidCoordTests(SimpleTestCase):
    """Guard that stops a bad restaurant/delivery coordinate from computing a bogus
    far distance and falsely rejecting the order as 'outside delivery area'."""

    def test_real_point_is_valid(self):
        self.assertTrue(valid_coord(33.5731, -7.5898))  # Casablanca

    def test_null_island_is_invalid(self):
        # (0,0) is what a failed geolocation / map-picker leaves behind — the bug.
        self.assertFalse(valid_coord(0, 0))
        self.assertFalse(valid_coord(0.0, 0.0))

    def test_missing_is_invalid(self):
        self.assertFalse(valid_coord(None, -7.5))
        self.assertFalse(valid_coord(33.5, None))
        self.assertFalse(valid_coord("", ""))

    def test_out_of_range_is_invalid(self):
        self.assertFalse(valid_coord(91, 10))    # lat > 90
        self.assertFalse(valid_coord(10, 200))   # lng > 180

    def test_single_axis_zero_is_valid(self):
        # 0 on ONE axis is a real place (equator / prime meridian); only the exact
        # (0,0) pair is treated as 'unset'.
        self.assertTrue(valid_coord(0, -7.6))
        self.assertTrue(valid_coord(33.6, 0))


class SplitDeliveryFeeTests(SimpleTestCase):
    """Platform commission split: driver_payout + platform_commission == fee."""

    def test_default_zero_commission_driver_keeps_all(self):
        # No commission configured → driver keeps 100%, platform takes nothing.
        r = split_delivery_fee(SimpleNamespace(), Decimal("12.00"))
        self.assertEqual(r["driver_payout"], Decimal("12.00"))
        self.assertEqual(r["platform_commission"], Decimal("0.00"))
        self.assertEqual(r["commission_pct"], Decimal("0"))

    def test_fifteen_percent(self):
        r = split_delivery_fee(_profile(delivery_commission_pct=Decimal("15")), Decimal("10.00"))
        self.assertEqual(r["platform_commission"], Decimal("1.50"))
        self.assertEqual(r["driver_payout"], Decimal("8.50"))

    def test_hundred_percent_driver_gets_nothing(self):
        r = split_delivery_fee(_profile(delivery_commission_pct=Decimal("100")), Decimal("9.00"))
        self.assertEqual(r["platform_commission"], Decimal("9.00"))
        self.assertEqual(r["driver_payout"], Decimal("0.00"))

    def test_over_hundred_is_clamped(self):
        r = split_delivery_fee(_profile(delivery_commission_pct=Decimal("250")), Decimal("9.00"))
        self.assertEqual(r["commission_pct"], Decimal("100"))
        self.assertEqual(r["platform_commission"], Decimal("9.00"))
        self.assertEqual(r["driver_payout"], Decimal("0.00"))

    def test_negative_is_clamped_to_zero(self):
        r = split_delivery_fee(_profile(delivery_commission_pct=Decimal("-10")), Decimal("9.00"))
        self.assertEqual(r["commission_pct"], Decimal("0"))
        self.assertEqual(r["driver_payout"], Decimal("9.00"))

    def test_rounds_to_cents_and_sums_to_fee(self):
        # 33% of 10.00 = 3.30 → payout 6.70; split must reconstruct the fee exactly.
        r = split_delivery_fee(_profile(delivery_commission_pct=Decimal("33")), Decimal("10.00"))
        self.assertEqual(r["platform_commission"], Decimal("3.30"))
        self.assertEqual(r["driver_payout"], Decimal("6.70"))
        self.assertEqual(r["platform_commission"] + r["driver_payout"], Decimal("10.00"))

    def test_zero_fee(self):
        r = split_delivery_fee(_profile(delivery_commission_pct=Decimal("20")), Decimal("0"))
        self.assertEqual(r["driver_payout"], Decimal("0.00"))
        self.assertEqual(r["platform_commission"], Decimal("0.00"))
