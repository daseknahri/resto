"""
Tests for CustomerOrderCancelView — a signed-in customer cancelling their own early
pickup/delivery order (auto wallet-refund + restock).

Unit-level (SimpleTestCase + mocks — no real DB). The refund/restock/broadcast/email
side-effects are patched out; this exercises the gate logic + that the right helpers fire.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer
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
            # PERF: the cancel email now goes through the async queue, not an inline send.
            "enqueue": patch("accounts.tasks.enqueue"),
            "atomic": patch("django.db.transaction.atomic", return_value=_noop_atomic()),
        }
        self.m = {k: p.start() for k, p in self._patchers.items()}

    def tearDown(self):
        for p in self._patchers.values():
            p.stop()

    def _post(self, session):
        """`session` keeps its {"customer_id": N} / {} shape — it now drives BOTH the
        request session (mirroring production, where login populates it) and the
        Customer principal the auth stack hydrates onto request.user.

        RISK IDENTITY-1: ownership is resolved by the shared IsOrderOwner predicate off
        request.user. The view stays AllowAny — order-existence (404) is checked before
        ownership, and the non-owner 403 IS the sign-in prompt for an anonymous caller.
        """
        req = self.factory.post("/api/order-status/ORD-1/cancel/")
        req.session = session
        cid = session.get("customer_id")
        if cid is not None:
            principal = Customer(id=cid)
            principal.save = MagicMock()
            force_authenticate(req, user=principal)
        req.tenant = MagicMock(id=7)
        return req

    def _set(self, order, locked=None):
        """`order` is the UNLOCKED read at the top of post(); `locked` is the row re-read
        under select_for_update (defaults to the same row, as in production when nothing
        raced). The view re-checks cancellability on the LOCKED row, so it must be a real
        row-shaped object here, not an auto-MagicMock."""
        self.m["orders"].filter.return_value.first.return_value = order
        self.m["orders"].select_for_update.return_value.filter.return_value.first.return_value = (
            order if locked is None else locked
        )

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

    def test_order_advanced_to_preparing_under_the_lock_is_not_cancellable(self):
        """Regression (TOCTOU, same class as the void/comp fix #442): the unlocked read says
        PENDING (cancellable) but the owner advanced the order to PREPARING in the window
        before the select_for_update lock. The cancellability gate must be re-checked on the
        LOCKED row — refuse with 409 not_cancellable and touch nothing (no status flip, no
        refund, no restock, no loyalty reversal, no broadcast/email)."""
        for locked_status in (
            Order.Status.PREPARING,
            Order.Status.READY,
            Order.Status.OUT_FOR_DELIVERY,
        ):
            with self.subTest(locked_status=locked_status):
                for key in ("refund", "restock", "broadcast", "enqueue"):
                    self.m[key].reset_mock()
                order = _order(status="pending", fulfillment_type="pickup")
                self._set(order, locked=_order(status=locked_status, fulfillment_type="pickup"))
                with patch("django.db.transaction.set_rollback") as rollback, \
                     patch("menu.views._reverse_loyalty_for_cancelled_order") as revloy:
                    resp = self.view(self._post({"customer_id": 42}), order_number="ORD-1")
                self.assertEqual(resp.status_code, 409)
                self.assertEqual(resp.data["code"], "not_cancellable")
                rollback.assert_called_once_with(True)
                order.save.assert_not_called()
                self.assertEqual(order.status, "pending")  # untouched
                self.m["refund"].assert_not_called()
                self.m["restock"].assert_not_called()
                revloy.assert_not_called()
                self.m["broadcast"].assert_not_called()
                self.m["enqueue"].assert_not_called()

    def test_peer_cancelled_under_the_lock_still_replays_idempotently(self):
        """The new locked re-check must NOT turn the existing peer-cancel replay (double
        tap / sweep racing the customer) into a 409: a row already CANCELLED under the lock
        is the idempotent 200 path (keyed wallet credit replays; restock does not re-run)."""
        order = _order(status="pending", fulfillment_type="pickup")
        self._set(order, locked=_order(status=Order.Status.CANCELLED, fulfillment_type="pickup"))
        with patch("django.db.transaction.set_rollback") as rollback:
            resp = self.view(self._post({"customer_id": 42}), order_number="ORD-1")
        self.assertEqual(resp.status_code, 200)
        rollback.assert_not_called()
        self.m["refund"].assert_called_once()
        self.m["restock"].assert_not_called()

    def test_pending_pickup_cancels_refunds_and_restocks(self):
        order = _order(status="pending", fulfillment_type="pickup")
        self._set(order)
        resp = self.view(self._post({"customer_id": 42}), order_number="ORD-1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(order.status, Order.Status.CANCELLED)
        order.save.assert_called_once()
        # tenant_id=7 is the mock tenant id set in _post; verifying it is forwarded
        # ensures the cancel-refund WalletTransaction row is tagged to this tenant.
        self.m["refund"].assert_called_once_with(order, tenant_id=7)
        self.m["restock"].assert_called_once_with(order)
        self.m["broadcast"].assert_called_once_with(order)
        # PERF: the cancel email is enqueued (off the request thread), not sent inline.
        from accounts.tasks import order_status_email
        self.m["enqueue"].assert_called_once_with(
            order_status_email, "ORD-1", 7, Order.Status.CANCELLED
        )

    def test_refunds_locked_wallet_amount_not_stale_snapshot(self):
        """Regression: refund the amount on the freshly-LOCKED row, not the pre-lock snapshot.

        A concurrent void/comp decrements wallet_amount_paid under its own row lock in the
        window between this view's unlocked read (top of post) and its select_for_update lock.
        The cancelrefund idempotency key guards a DOUBLE refund but not a wrong AMOUNT, so
        refunding the stale (higher) value over-refunds. The view must sync from _locked."""
        order = _order(status="pending", fulfillment_type="pickup")
        order.wallet_amount_paid = Decimal("100.00")  # stale snapshot read before the lock
        self._set(order)
        # The locked row reflects a concurrent void that already refunded 30 → 70 remains.
        locked = _order(status="pending", fulfillment_type="pickup")
        locked.wallet_amount_paid = Decimal("70.00")
        self.m["orders"].select_for_update.return_value.filter.return_value.first.return_value = locked
        resp = self.view(self._post({"customer_id": 42}), order_number="ORD-1")
        self.assertEqual(resp.status_code, 200)
        self.m["refund"].assert_called_once()
        refunded_order = self.m["refund"].call_args.args[0]
        # Synced to the LOCKED 70, not the stale 100 — no over-refund.
        self.assertEqual(refunded_order.wallet_amount_paid, Decimal("70.00"))

    def test_confirmed_delivery_can_cancel(self):
        order = _order(status="confirmed", fulfillment_type="delivery")
        self._set(order)
        resp = self.view(self._post({"customer_id": 42}), order_number="ORD-1")
        self.assertEqual(resp.status_code, 200)
        self.m["refund"].assert_called_once_with(order, tenant_id=7)
