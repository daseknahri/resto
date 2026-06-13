"""
Tests for the order payment-state model + the staff settle endpoint.

Covers:
  - Order.requires_prepayment (pickup/delivery = pay-now, table = open tab)
  - Order.mark_paid() sets payment_status + paid_at, idempotent
  - OwnerOrderMarkPaidView — permission gate, marks paid, optional complete

All unit-level (SimpleTestCase + mocks — no real DB).
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.models import Order
from menu.views import OwnerOrderMarkPaidView


class OrderPaymentStateModelTests(SimpleTestCase):
    def test_requires_prepayment_true_for_pickup_and_delivery(self):
        self.assertTrue(Order(fulfillment_type=Order.FulfillmentType.PICKUP).requires_prepayment)
        self.assertTrue(Order(fulfillment_type=Order.FulfillmentType.DELIVERY).requires_prepayment)

    def test_requires_prepayment_false_for_dine_in(self):
        self.assertFalse(Order(fulfillment_type=Order.FulfillmentType.TABLE).requires_prepayment)

    def test_new_order_is_unpaid_by_default(self):
        self.assertFalse(Order().is_paid)
        self.assertEqual(Order().payment_status, Order.PaymentStatus.UNPAID)

    def test_mark_paid_sets_state(self):
        o = Order(fulfillment_type=Order.FulfillmentType.PICKUP)
        o.mark_paid(save=False)
        self.assertTrue(o.is_paid)
        self.assertEqual(o.payment_status, Order.PaymentStatus.PAID)
        self.assertIsNotNone(o.paid_at)

    def test_mark_paid_is_idempotent(self):
        o = Order(fulfillment_type=Order.FulfillmentType.TABLE)
        o.mark_paid(save=False)
        first_ts = o.paid_at
        o.mark_paid(save=False)  # second call must not error or change state
        self.assertEqual(o.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(o.paid_at, first_ts)


class OwnerOrderMarkPaidViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerOrderMarkPaidView.as_view()

        # OPS-3 contract C: OwnerOrderMarkPaidView now wraps the mutate path in
        # transaction.atomic() + select_for_update().  Patch menu.views.transaction
        # with a passthrough _Atomic so SimpleTestCase (no DB) continues to work.
        from unittest.mock import patch as _patch

        class _Atomic:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        _tx_patcher = _patch("menu.views.transaction")
        self._tx_mock = _tx_patcher.start()
        self.addCleanup(_tx_patcher.stop)
        self._tx_mock.atomic.return_value = _Atomic()

    def _order(self, **kw):
        defaults = dict(
            id=5, order_number="ORD5",
            status=Order.Status.READY,
            fulfillment_type=Order.FulfillmentType.TABLE,
        )
        defaults.update(kw)
        order = Order(**defaults)
        order.save = MagicMock()  # stub DB write (SimpleTestCase has no DB)
        return order

    @patch("menu.views._can_edit_tenant_order", return_value=False)
    @patch("menu.views.Order.objects")
    def test_denied_for_non_editor(self, objects_mock, _gate):
        objects_mock.select_for_update.return_value.filter.return_value.first.return_value =self._order()
        req = self.factory.post("/api/owner/orders/5/mark-paid/")
        req.user = MagicMock(id=9)
        resp = self.view(req, order_id=5)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("menu.views._can_edit_tenant_order", return_value=True)
    @patch("menu.views.Order.objects")
    def test_marks_paid(self, objects_mock, _gate):
        order = self._order()
        objects_mock.select_for_update.return_value.filter.return_value.first.return_value =order
        req = self.factory.post("/api/owner/orders/5/mark-paid/")
        req.user = MagicMock(id=9)
        resp = self.view(req, order_id=5)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["payment_status"], Order.PaymentStatus.PAID)
        self.assertFalse(resp.data["already_paid"])
        self.assertFalse(resp.data["completed"])  # no complete flag → status untouched
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)

    @patch("menu.views._can_edit_tenant_order", return_value=True)
    @patch("menu.views.Order.objects")
    def test_settle_and_complete(self, objects_mock, _gate):
        order = self._order(status=Order.Status.READY)
        objects_mock.select_for_update.return_value.filter.return_value.first.return_value =order
        req = self.factory.post("/api/owner/orders/5/mark-paid/", {"complete": True}, format="json")
        req.user = MagicMock(id=9)
        resp = self.view(req, order_id=5)
        self.assertTrue(resp.data["completed"])
        self.assertEqual(resp.data["status"], Order.Status.COMPLETED)

    @patch("menu.views._can_edit_tenant_order", return_value=True)
    @patch("menu.views.Order.objects")
    def test_complete_flag_ignored_when_not_ready(self, objects_mock, _gate):
        order = self._order(status=Order.Status.PREPARING)
        objects_mock.select_for_update.return_value.filter.return_value.first.return_value =order
        req = self.factory.post("/api/owner/orders/5/mark-paid/", {"complete": True}, format="json")
        req.user = MagicMock(id=9)
        resp = self.view(req, order_id=5)
        self.assertFalse(resp.data["completed"])
        self.assertEqual(resp.data["status"], Order.Status.PREPARING)  # unchanged

    @patch("menu.views._can_edit_tenant_order", return_value=True)
    @patch("menu.views.Order.objects")
    def test_unknown_order_404(self, objects_mock, _gate):
        objects_mock.select_for_update.return_value.filter.return_value.first.return_value =None
        req = self.factory.post("/api/owner/orders/999/mark-paid/")
        req.user = MagicMock(id=9)
        resp = self.view(req, order_id=999)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
