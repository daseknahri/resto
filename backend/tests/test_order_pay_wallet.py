"""
Tests for CustomerOrderPayWalletView — a signed-in customer settling their own
order from their wallet (e.g. paying a dine-in tab at the end).

Unit-level (SimpleTestCase + mocks — no real DB / no real wallet ledger).

RISK IDENTITY-1: the view resolves ownership through the shared IsOrderOwner predicate
off request.user. It deliberately stays AllowAny — order-existence (404) is checked
before ownership, and the non-owner 403 IS the sign-in prompt an anonymous caller is
meant to get, so IsCustomer would 401 ahead of both.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer
from menu.views import CustomerOrderPayWalletView
from menu.models import Order
from accounts.wallet_service import InsufficientFunds


def _order(customer_id=42, total="45.00", paid="0.00", payment_status="unpaid", order_status="ready"):
    o = MagicMock()
    o.order_number = "ORD-1"
    o.customer_id = customer_id
    o.total = Decimal(total)
    o.wallet_amount_paid = Decimal(paid)
    o.payment_status = payment_status
    o.status = order_status
    return o


class PayWalletTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerOrderPayWalletView.as_view()
        # The settle now runs in transaction.atomic() + select_for_update and reconciles the
        # OrderPayment ledger via _order_collected. Neutralise both for these no-DB unit tests:
        # atomic → passthrough; ledger → empty by default (a test overrides self.MockOP for rows).
        import contextlib
        _atomic = patch("django.db.transaction.atomic", lambda *a, **k: contextlib.nullcontext())
        _atomic.start()
        self.addCleanup(_atomic.stop)
        _op = patch("menu.models.OrderPayment")
        self.MockOP = _op.start()
        self.addCleanup(_op.stop)
        self.MockOP.objects.filter.return_value = []
        self.MockOP.Method.WALLET = "wallet"

    def _post(self, session):
        """`session` keeps its {"customer_id": N} / {} shape — it now drives BOTH the
        request session (mirroring production, where login populates it) and the
        Customer principal the auth stack hydrates onto request.user."""
        req = self.factory.post("/api/orders/ORD-1/pay-wallet/")
        req.session = session
        cid = session.get("customer_id")
        if cid is not None:
            principal = Customer(id=cid)
            principal.save = MagicMock()
            force_authenticate(req, user=principal)
        req.tenant = MagicMock(id=7)
        return req

    @patch("menu.views.Order.objects")
    def test_unknown_order_404(self, om):
        om.filter.return_value.first.return_value = None
        resp = self.view(self._post({"customer_id": 42}), order_number="ORD-X")
        self.assertEqual(resp.status_code, 404)

    @patch("menu.views.Order.objects")
    def test_no_session_403(self, om):
        om.filter.return_value.first.return_value = _order()
        resp = self.view(self._post({}), order_number="ORD-1")
        self.assertEqual(resp.status_code, 403)

    @patch("menu.views.Order.objects")
    def test_other_customer_403(self, om):
        om.filter.return_value.first.return_value = _order(customer_id=42)
        resp = self.view(self._post({"customer_id": 99}), order_number="ORD-1")
        self.assertEqual(resp.status_code, 403)

    @patch("menu.views.Order.objects")
    def test_already_paid_is_noop(self, om):
        om.filter.return_value.first.return_value = _order(payment_status=Order.PaymentStatus.PAID)
        resp = self.view(self._post({"customer_id": 42}), order_number="ORD-1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "paid")

    @patch("accounts.wallet_service.debit_wallet")
    @patch("menu.views.Order.objects")
    def test_pays_outstanding_and_marks_paid(self, om, debit):
        order = _order(total="45.00", paid="0.00")
        om.filter.return_value.first.return_value = order
        om.select_for_update.return_value = om  # the locked re-read resolves to the same order
        tx = MagicMock()
        tx.balance_after = Decimal("5.00")
        debit.return_value = tx
        resp = self.view(self._post({"customer_id": 42}), order_number="ORD-1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "paid")
        self.assertEqual(resp.data["amount_paid"], "45.00")
        self.assertEqual(resp.data["new_balance"], "5.00")
        debit.assert_called_once()
        # OPS-5g: idempotency key tied to the order AND tenant-schema-namespaced (the
        # shared-schema ledger makes the key a GLOBAL namespace, so a bare order_number
        # could collide cross-tenant). A double-tap still never double-charges.
        from django.db import connection as _c
        _key = debit.call_args.kwargs.get("idempotency_key")
        self.assertEqual(_key, f"order-pay-{_c.schema_name}-ORD-1")
        # Bill bumped and the order settled.
        self.assertEqual(order.wallet_amount_paid, Decimal("45.00"))
        order.mark_paid.assert_called_once()

    @patch("accounts.models.Customer")
    @patch("accounts.wallet_service.debit_wallet")
    @patch("menu.views.Order.objects")
    def test_insufficient_balance_402(self, om, debit, Cust):
        om.filter.return_value.first.return_value = _order(total="45.00")
        om.select_for_update.return_value = om
        debit.side_effect = InsufficientFunds()
        Cust.objects.filter.return_value.first.return_value = MagicMock(wallet_balance=Decimal("10.00"))
        resp = self.view(self._post({"customer_id": 42}), order_number="ORD-1")
        self.assertEqual(resp.status_code, 402)
        self.assertEqual(resp.data["code"], "insufficient")
        self.assertEqual(resp.data["balance"], "10.00")

    @patch("accounts.wallet_service.debit_wallet")
    @patch("menu.views.Order.objects")
    def test_cash_partial_in_ledger_is_not_overcharged(self, om, debit):
        """Regression: a staff cash split-bill (an OrderPayment row) that never touched
        wallet_amount_paid must count as already collected. A 100 tab with a 60 cash row debits
        only the remaining 40 from the wallet — before this fix it charged the full 100
        (over-collecting the 60 already taken in cash)."""
        order = _order(total="100.00", paid="0.00")
        om.filter.return_value.first.return_value = order
        om.select_for_update.return_value = om
        cash_row = MagicMock(amount=Decimal("60.00"), method="cash")   # method != 'wallet'
        self.MockOP.objects.filter.return_value = [cash_row]
        tx = MagicMock()
        tx.balance_after = Decimal("10.00")
        debit.return_value = tx

        resp = self.view(self._post({"customer_id": 42}), order_number="ORD-1")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["amount_paid"], "40.00")            # NOT 100
        self.assertEqual(debit.call_args.args[1], Decimal("40.00"))    # only the reconciled remainder
        self.assertEqual(order.wallet_amount_paid, Decimal("40.00"))
