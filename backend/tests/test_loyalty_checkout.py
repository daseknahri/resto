"""
Tests for loyalty redemption at checkout (Phase 3.2) — the pure sizing helper
_size_loyalty_redemption. No DB.

The helper decides how big a discount a points redemption yields and how many
points it actually consumes, plus the validation codes the placement view surfaces.
"""
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from menu.views import _loyalty_points_earned, _size_loyalty_redemption


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


class LoyaltyPointsEarnedTests(SimpleTestCase):
    """_loyalty_points_earned: floor(subtotal * rate * tier) in exact Decimal math.

    Regression: the old ``int(float(subtotal) * rate * float(mul))`` dropped a point
    when the exact product was an integer but the float product landed just below it.
    """

    def test_float_trap_029_times_100_earns_29(self):
        # float(0.29) * 100 == 28.999999999999996 -> int() gave 28; exact product is 29.
        self.assertEqual(int(float(Decimal("0.29")) * 100 * float(Decimal("1"))), 28)
        self.assertEqual(_loyalty_points_earned(Decimal("0.29"), 100, Decimal("1")), 29)

    def test_default_config_unchanged(self):
        # points_per_unit=10 and the stock tier multipliers {1, 1.5, 2}.
        self.assertEqual(_loyalty_points_earned(Decimal("12.34"), 10, Decimal("1")), 123)
        self.assertEqual(_loyalty_points_earned(Decimal("12.34"), 10, Decimal("1.50")), 185)
        self.assertEqual(_loyalty_points_earned(Decimal("12.34"), 10, Decimal("2.00")), 246)

    def test_fractional_product_is_floored_not_rounded(self):
        # 9.99 * 10 * 1.5 = 149.85 -> 149 (floor), never 150.
        self.assertEqual(_loyalty_points_earned(Decimal("9.99"), 10, Decimal("1.5")), 149)

    def test_exact_integer_product_is_kept(self):
        self.assertEqual(_loyalty_points_earned(Decimal("20.00"), 10, Decimal("1")), 200)
        self.assertEqual(_loyalty_points_earned(Decimal("4.00"), 5, Decimal("1.50")), 30)

    def test_zero_and_negative_subtotal_earn_nothing(self):
        self.assertEqual(_loyalty_points_earned(Decimal("0"), 10, Decimal("1")), 0)
        self.assertEqual(_loyalty_points_earned(Decimal("-5.00"), 10, Decimal("1")), 0)

    def test_zero_rate_earns_nothing(self):
        self.assertEqual(_loyalty_points_earned(Decimal("50"), 0, Decimal("2")), 0)

    def test_returns_plain_int(self):
        self.assertIsInstance(_loyalty_points_earned(Decimal("1.00"), 10, Decimal("1")), int)

    def test_both_checkout_paths_use_the_shared_helper(self):
        # Guard against the float formula creeping back into either checkout.
        import inspect

        import accounts.views as accounts_views
        import menu.views as menu_views

        for mod in (menu_views, accounts_views):
            src = inspect.getsource(mod)
            self.assertIn("_loyalty_points_earned(", src, mod.__name__)
            self.assertNotIn("* int(_loyalty_cfg.points_per_unit)", src, mod.__name__)
            self.assertNotIn("* int(_earn_cfg.points_per_unit)", src, mod.__name__)
