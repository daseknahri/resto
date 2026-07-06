"""
Tests for the order payment-state model + the staff settle endpoint.

Covers:
  - Order.requires_prepayment (pickup/delivery = pay-now, table = open tab)
  - Order.mark_paid() sets payment_status + paid_at, idempotent
  - OwnerOrderMarkPaidView — permission gate, marks paid, optional complete
  - S1: the reconciliation guard — an order can't be marked PAID/COMPLETED
    for less than its total once there is a tracked payment to check against.

All unit-level (SimpleTestCase + mocks — no real DB).
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.models import Order, OrderPayment
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

        # S1: the reconciliation guard queries OrderPayment.objects.filter(order_id=...)
        # directly (not order.payments.all()) so it works against a real, unsaved
        # Order() instance without fighting the reverse-FK related-manager descriptor.
        # Default: no ledger rows — matches every pre-existing test in this class
        # (plain cash "Mark paid", nothing tracked, guard is a no-op).
        _op_patcher = _patch("menu.views.OrderPayment.objects")
        self._op_objects_mock = _op_patcher.start()
        self.addCleanup(_op_patcher.stop)
        self._op_objects_mock.filter.return_value = []

    def _set_payment_rows(self, rows):
        """Configure OrderPayment.objects.filter(order_id=...) to return `rows`."""
        self._op_objects_mock.filter.return_value = rows

    def _payment_row(self, amount, method=OrderPayment.Method.WALLET):
        row = MagicMock()
        row.amount = amount
        row.method = method
        return row

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

    # ── S1: reconciliation guard ─────────────────────────────────────────────

    @patch("menu.views._can_edit_tenant_order", return_value=True)
    @patch("menu.views.Order.objects")
    def test_correct_full_wallet_settle_still_succeeds(self, objects_mock, _gate):
        """Wallet-charge-sheet settle for EXACTLY the outstanding amount (now tied
        to the order as an OrderPayment row by OwnerWalletChargeView) must still
        flip the order to PAID — the guard must not reject a correct settle."""
        order = self._order(total=Decimal("35.00"), wallet_amount_paid=Decimal("35.00"))
        self._set_payment_rows([self._payment_row(Decimal("35.00"))])
        objects_mock.select_for_update.return_value.filter.return_value.first.return_value = order
        req = self.factory.post("/api/owner/orders/5/mark-paid/")
        req.user = MagicMock(id=9)
        resp = self.view(req, order_id=5)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["payment_status"], Order.PaymentStatus.PAID)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)

    @patch("menu.views._can_edit_tenant_order", return_value=True)
    @patch("menu.views.Order.objects")
    def test_short_wallet_settle_rejected_400_payment_short(self, objects_mock, _gate):
        """A wallet-charge-sheet settle for LESS than the outstanding total must be
        rejected — this is the exact hole S1 closes (editable-amount charge sheet
        followed by an unconditional mark-paid call)."""
        order = self._order(total=Decimal("35.00"), wallet_amount_paid=Decimal("20.00"))
        self._set_payment_rows([self._payment_row(Decimal("20.00"))])
        objects_mock.select_for_update.return_value.filter.return_value.first.return_value = order
        req = self.factory.post("/api/owner/orders/5/mark-paid/")
        req.user = MagicMock(id=9)
        resp = self.view(req, order_id=5)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "payment_short")
        self.assertEqual(resp.data["collected"], "20.00")
        self.assertEqual(resp.data["total"], "35.00")
        # Order must NOT have been flipped to PAID.
        self.assertEqual(order.payment_status, Order.PaymentStatus.UNPAID)

    @patch("menu.views._can_edit_tenant_order", return_value=True)
    @patch("menu.views.Order.objects")
    def test_ledger_partial_payments_fully_settle_correctly(self, objects_mock, _gate):
        """Two split-bill OrderPayment rows (cash + wallet) that together cover the
        total must let mark-paid succeed — the ledger partial-payment path
        (StaffOrderPaymentView) must keep working exactly as before."""
        order = self._order(total=Decimal("35.00"), wallet_amount_paid=Decimal("15.00"))
        self._set_payment_rows([
            self._payment_row(Decimal("20.00"), method=OrderPayment.Method.CASH),
            self._payment_row(Decimal("15.00"), method=OrderPayment.Method.WALLET),
        ])
        objects_mock.select_for_update.return_value.filter.return_value.first.return_value = order
        req = self.factory.post("/api/owner/orders/5/mark-paid/")
        req.user = MagicMock(id=9)
        resp = self.view(req, order_id=5)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["payment_status"], Order.PaymentStatus.PAID)

    @patch("menu.views._can_edit_tenant_order", return_value=True)
    @patch("menu.views.Order.objects")
    def test_plain_cash_mark_paid_with_no_tracked_payment_still_works(self, objects_mock, _gate):
        """No ledger rows and wallet_amount_paid == 0 (the everyday cash 'Mark
        paid' click) has nothing to reconcile against — the guard must not block
        it. This preserves the existing no-ledger cash-settle flow untouched."""
        order = self._order(total=Decimal("35.00"), wallet_amount_paid=Decimal("0"))
        self._set_payment_rows([])
        objects_mock.select_for_update.return_value.filter.return_value.first.return_value = order
        req = self.factory.post("/api/owner/orders/5/mark-paid/")
        req.user = MagicMock(id=9)
        resp = self.view(req, order_id=5)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["payment_status"], Order.PaymentStatus.PAID)

    @patch("menu.views._can_edit_tenant_order", return_value=True)
    @patch("menu.views.Order.objects")
    def test_short_settle_does_not_complete_ready_order(self, objects_mock, _gate):
        """A rejected settle must not flip a READY order to COMPLETED either,
        even when complete=true is passed."""
        order = self._order(
            status=Order.Status.READY,
            total=Decimal("35.00"),
            wallet_amount_paid=Decimal("10.00"),
        )
        self._set_payment_rows([self._payment_row(Decimal("10.00"))])
        objects_mock.select_for_update.return_value.filter.return_value.first.return_value = order
        req = self.factory.post("/api/owner/orders/5/mark-paid/", {"complete": True}, format="json")
        req.user = MagicMock(id=9)
        resp = self.view(req, order_id=5)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(order.status, Order.Status.READY)  # unchanged
