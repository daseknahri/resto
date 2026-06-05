"""
Tests for loyalty redemption at checkout (Phase 3.2) — the pure sizing helper
_size_loyalty_redemption. No DB.

The helper decides how big a discount a points redemption yields and how many
points it actually consumes, plus the validation codes the placement view surfaces.
"""
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from menu.views import _size_loyalty_redemption


def _cfg(enabled=True, points_value="0.01", redeem_threshold=100):
    return SimpleNamespace(
        enabled=enabled,
        points_value=points_value,
        redeem_threshold=redeem_threshold,
    )


class SizeLoyaltyRedemptionTests(SimpleTestCase):
    def test_zero_request_is_noop(self):
        self.assertEqual(
            _size_loyalty_redemption(_cfg(), 500, 0, Decimal("50")),
            (Decimal("0"), 0, None),
        )

    def test_disabled_program_errors(self):
        d, p, err = _size_loyalty_redemption(_cfg(enabled=False), 500, 200, Decimal("50"))
        self.assertEqual((d, p), (Decimal("0"), 0))
        self.assertEqual(err, "loyalty_disabled")

    def test_none_config_errors(self):
        d, p, err = _size_loyalty_redemption(None, 500, 200, Decimal("50"))
        self.assertEqual(err, "loyalty_disabled")

    def test_more_than_balance_errors(self):
        d, p, err = _size_loyalty_redemption(_cfg(), 100, 200, Decimal("50"))
        self.assertEqual(err, "loyalty_insufficient_points")

    def test_below_threshold_errors(self):
        d, p, err = _size_loyalty_redemption(_cfg(redeem_threshold=100), 500, 50, Decimal("50"))
        self.assertEqual(err, "loyalty_below_threshold")

    def test_zero_points_value_errors(self):
        d, p, err = _size_loyalty_redemption(_cfg(points_value="0"), 500, 200, Decimal("50"))
        self.assertEqual(err, "loyalty_disabled")

    def test_happy_path_full_value(self):
        # 200 points * 0.01 = 2.00 discount, well under the 50.00 charge → spends all 200.
        d, p, err = _size_loyalty_redemption(_cfg(), 500, 200, Decimal("50"))
        self.assertIsNone(err)
        self.assertEqual(d, Decimal("2.00"))
        self.assertEqual(p, 200)

    def test_discount_capped_to_order_spends_only_needed_points(self):
        # 5000 points * 0.01 = 50.00 raw, but the order is only 3.00 → discount capped at
        # 3.00, spending ceil(3.00 / 0.01) = 300 points (not all 5000).
        d, p, err = _size_loyalty_redemption(_cfg(), 5000, 5000, Decimal("3.00"))
        self.assertIsNone(err)
        self.assertEqual(d, Decimal("3.00"))
        self.assertEqual(p, 300)

    def test_zero_total_yields_no_discount(self):
        d, p, err = _size_loyalty_redemption(_cfg(), 500, 200, Decimal("0"))
        self.assertIsNone(err)
        self.assertEqual((d, p), (Decimal("0"), 0))
