"""
Tests for the fulfillment-type-aware order status machine
(OwnerOrderStatusUpdateView._allowed_transitions).

Unit-level (SimpleTestCase + mocks).
"""
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from menu.views import OwnerOrderStatusUpdateView
from menu.models import Order

_allowed = OwnerOrderStatusUpdateView._allowed_transitions


def _o(ft, status):
    o = MagicMock()
    o.fulfillment_type = ft
    o.status = status
    return o


class AllowedTransitionsTests(SimpleTestCase):
    # ── Shared early flow ──────────────────────────────────────────────────────
    def test_pending_confirms(self):
        for ft in ("pickup", "table", "delivery"):
            self.assertIn(Order.Status.CONFIRMED, _allowed(_o(ft, Order.Status.PENDING)))

    def test_preparing_goes_ready(self):
        for ft in ("pickup", "table", "delivery"):
            self.assertIn(Order.Status.READY, _allowed(_o(ft, Order.Status.PREPARING)))

    # ── Delivery: extra out-for-delivery step ──────────────────────────────────
    def test_delivery_ready_goes_out_for_delivery_not_completed(self):
        allowed = _allowed(_o("delivery", Order.Status.READY))
        self.assertIn(Order.Status.OUT_FOR_DELIVERY, allowed)
        self.assertNotIn(Order.Status.COMPLETED, allowed)

    def test_delivery_out_for_delivery_completes(self):
        allowed = _allowed(_o("delivery", Order.Status.OUT_FOR_DELIVERY))
        self.assertIn(Order.Status.COMPLETED, allowed)

    # ── Pickup / dine-in: ready → completed (no out-for-delivery) ───────────────
    def test_pickup_ready_completes(self):
        allowed = _allowed(_o("pickup", Order.Status.READY))
        self.assertIn(Order.Status.COMPLETED, allowed)
        self.assertNotIn(Order.Status.OUT_FOR_DELIVERY, allowed)

    def test_table_ready_completes(self):
        allowed = _allowed(_o("table", Order.Status.READY))
        self.assertIn(Order.Status.COMPLETED, allowed)
        self.assertNotIn(Order.Status.OUT_FOR_DELIVERY, allowed)

    # ── Terminal states ────────────────────────────────────────────────────────
    def test_completed_and_cancelled_are_terminal(self):
        self.assertEqual(_allowed(_o("pickup", Order.Status.COMPLETED)), set())
        self.assertEqual(_allowed(_o("delivery", Order.Status.CANCELLED)), set())

    def test_cancellable_while_active(self):
        for s in (Order.Status.PENDING, Order.Status.CONFIRMED, Order.Status.PREPARING, Order.Status.READY):
            self.assertIn(Order.Status.CANCELLED, _allowed(_o("pickup", s)))
        self.assertIn(Order.Status.CANCELLED, _allowed(_o("delivery", Order.Status.OUT_FOR_DELIVERY)))
