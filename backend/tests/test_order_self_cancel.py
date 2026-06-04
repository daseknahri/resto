"""
Tests for CustomerOrderCancelView — a signed-in customer cancelling their own early
pickup/delivery order (auto wallet-refund + restock).

Unit-level (SimpleTestCase + mocks — no real DB). The refund/restock/broadcast/email
side-effects are patched out; this exercises the gate logic + that the right helpers fire.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from menu.views import CustomerOrderCancelView
from menu.models import Order


def _noop_atomic():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def _order(customer_id=42, status="pending", fulfillment_type="pickup"):
    o = MagicMock()
    o.order_number = "ORD-1"
    o.customer_id = customer_id
    o.status = status
    o.fulfillment_type = fulfillment_type
    o.payment_status = "paid"
    o.wallet_amount_paid = Decimal("45.00")
    return o


class CancelOrderTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerOrderCancelView.as_view()
        self._patchers = {
            "orders": patch("menu.views.Order.objects"),
            "refund": patch("menu.views._refund_wallet_for_cancelled_order"),
            "restock": patch("menu.views._restock_cancelled_order"),
            "broadcast": patch("menu.views._broadcast_order_change"),
            "email": patch("menu.views._send_order_status_email"),
            "atomic": patch("django.db.transaction.atomic", return_value=_noop_atomic()),
        }
        self.m = {k: p.start() for k, p in self._patchers.items()}

    def tearDown(self):
        for p in self._patchers.values():
            p.stop()

    def _post(self, session):
        req = self.factory.post("/api/order-status/ORD-1/cancel/")
        req.session = session
        req.tenant = MagicMock(id=7)
        return req

    def _set(self, order):
        self.m["orders"].filter.return_value.first.return_value = order

    def test_unknown_order_404(self):
        self._set(None)
        resp = self.view(self._post({"customer_id": 42}), order_number="ORD-X")
        self.assertEqual(resp.status_code, 404)

    def test_no_session_403(self):
        self._set(_order())
        resp = self.view(self._post({}), order_number="ORD-1")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data["code"], "not_owner")

    def test_other_customer_403(self):
        self._set(_order(customer_id=42))
        resp = self.view(self._post({"customer_id": 99}), order_number="ORD-1")
        self.assertEqual(resp.status_code, 403)

    def test_already_cancelled_is_noop(self):
        self._set(_order(status=Order.Status.CANCELLED))
        resp = self.view(self._post({"customer_id": 42}), order_number="ORD-1")
        self.assertEqual(resp.status_code, 200)
        self.m["refund"].assert_not_called()

    def test_dine_in_cannot_self_cancel(self):
        self._set(_order(status="confirmed", fulfillment_type="table"))
        resp = self.view(self._post({"customer_id": 42}), order_number="ORD-1")
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data["code"], "not_cancellable")
        self.m["refund"].assert_not_called()

    def test_preparing_too_late_to_cancel(self):
        self._set(_order(status="preparing"))
        resp = self.view(self._post({"customer_id": 42}), order_number="ORD-1")
        self.assertEqual(resp.status_code, 409)

    def test_pending_pickup_cancels_refunds_and_restocks(self):
        order = _order(status="pending", fulfillment_type="pickup")
        self._set(order)
        resp = self.view(self._post({"customer_id": 42}), order_number="ORD-1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(order.status, Order.Status.CANCELLED)
        order.save.assert_called_once()
        self.m["refund"].assert_called_once_with(order)
        self.m["restock"].assert_called_once_with(order)
        self.m["broadcast"].assert_called_once_with(order)
        self.m["email"].assert_called_once()

    def test_confirmed_delivery_can_cancel(self):
        order = _order(status="confirmed", fulfillment_type="delivery")
        self._set(order)
        resp = self.view(self._post({"customer_id": 42}), order_number="ORD-1")
        self.assertEqual(resp.status_code, 200)
        self.m["refund"].assert_called_once_with(order)
