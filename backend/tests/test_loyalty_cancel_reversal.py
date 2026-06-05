"""
Tests for _reverse_loyalty_for_cancelled_order — on cancellation, claw back points
EARNED at placement and restore points SPENT as a checkout discount.

Unit-level (SimpleTestCase + mocks — no real DB). The customer-row lock + atomic block
are patched out; this verifies the net delta + zero-clamp arithmetic and the no-op paths.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from menu.views import _reverse_loyalty_for_cancelled_order


def _noop_atomic():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def _order(customer_id=7, earned=0, redeemed=0):
    return SimpleNamespace(
        customer_id=customer_id,
        points_earned=earned,
        redeemed_loyalty_points=redeemed,
        order_number="ORD-1",
    )


class ReverseLoyaltyTests(SimpleTestCase):
    def setUp(self):
        self._patchers = {
            "cust": patch("accounts.models.Customer"),
            "atomic": patch("django.db.transaction.atomic", return_value=_noop_atomic()),
        }
        self.m = {k: p.start() for k, p in self._patchers.items()}
        self.cust = MagicMock()
        self.cust.loyalty_points = 0
        self.cust.save = MagicMock()
        self.m["cust"].objects.select_for_update.return_value.get.return_value = self.cust

    def tearDown(self):
        for p in self._patchers.values():
            p.stop()

    def _run(self, order):
        _reverse_loyalty_for_cancelled_order(order)

    def test_no_customer_is_noop(self):
        self._run(_order(customer_id=None, earned=100))
        self.m["cust"].objects.select_for_update.assert_not_called()

    def test_zero_delta_is_noop(self):
        # earned == restored → no net change → no lock/save
        self._run(_order(earned=50, redeemed=50))
        self.m["cust"].objects.select_for_update.assert_not_called()

    def test_clawback_earned_points(self):
        self.cust.loyalty_points = 300
        self._run(_order(earned=100, redeemed=0))
        self.assertEqual(self.cust.loyalty_points, 200)
        self.cust.save.assert_called_once()

    def test_restore_redeemed_points(self):
        self.cust.loyalty_points = 40
        self._run(_order(earned=0, redeemed=50))
        self.assertEqual(self.cust.loyalty_points, 90)

    def test_net_of_earned_and_redeemed(self):
        self.cust.loyalty_points = 500
        self._run(_order(earned=100, redeemed=30))  # delta = -70
        self.assertEqual(self.cust.loyalty_points, 430)

    def test_clamped_at_zero(self):
        self.cust.loyalty_points = 20
        self._run(_order(earned=100, redeemed=0))  # would be -80 → clamp 0
        self.assertEqual(self.cust.loyalty_points, 0)
