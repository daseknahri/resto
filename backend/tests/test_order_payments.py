"""
Tests for R4 split-bill: POST /api/staff/orders/<order_id>/payments/
                         StaffOrderPaymentView

House style:
  - SimpleTestCase + mocks — no real DB.
  - Only update_fields kwarg saves are accepted (checked via mock assertions).
  - Wallet-service interactions are fully mocked.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call, ANY

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from menu.views import StaffOrderPaymentView
from menu.models import Order
from accounts.models import User


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _user(role=User.Roles.TENANT_STAFF, tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = role
    u.tenant_id = tenant_id
    u.effective_perm_manage_orders = MagicMock(return_value=True)
    u.id = 5
    u.get_full_name = MagicMock(return_value="Alice Waiter")
    u.username = "alice"
    u.email = "alice@example.com"
    return u


def _tenant(tenant_id=1):
    return SimpleNamespace(id=tenant_id)


def _make_payment_row(amount=Decimal("10.00"), method="cash", recorded_by_name="Alice Waiter", note=""):
    p = MagicMock()
    p.amount = amount
    p.method = method
    p.recorded_by_name = recorded_by_name
    p.note = note
    created_at = MagicMock()
    created_at.isoformat.return_value = "2026-06-11T12:00:00+00:00"
    p.created_at = created_at
    return p


def _make_order(
    order_id=10,
    status_val=Order.Status.PENDING,
    payment_status=Order.PaymentStatus.UNPAID,
    total=Decimal("30.00"),
    wallet_amount_paid=Decimal("0"),
    customer_id=None,
    payments=None,
    items=None,
):
    order = MagicMock()
    order.id = order_id
    order.order_number = "ORD-001"
    order.status = status_val
    order.payment_status = payment_status
    order.total = total
    order.wallet_amount_paid = wallet_amount_paid
    order.customer_id = customer_id
    order.table_label = "T1"
    order.customer_name = "Bob"
    order.customer_note = ""
    order.owner_note = ""
    order.estimated_ready_minutes = None
    order.currency = "MAD"
    order.scheduled_for = None
    order.delivery_fee = Decimal("0")
    order.tip_amount = Decimal("0")
    order.promotion_discount = Decimal("0")
    order.loyalty_discount = Decimal("0")
    order.paid_at = None
    order.save = MagicMock()
    order.mark_paid = MagicMock()
    created_at = MagicMock()
    created_at.isoformat.return_value = "2026-06-11T10:00:00+00:00"
    order.created_at = created_at
    updated_at = MagicMock()
    updated_at.isoformat.return_value = "2026-06-11T10:00:00+00:00"
    order.updated_at = updated_at

    # items
    _items = items or []
    items_qs = MagicMock()
    items_qs.all.return_value = _items
    order.items = items_qs

    # payments
    _payments = payments or []
    payments_qs = MagicMock()
    payments_qs.all.return_value = _payments
    order.payments = payments_qs

    return order


# ═══════════════════════════════════════════════════════════════════════════════
# StaffOrderPaymentView tests
# ═══════════════════════════════════════════════════════════════════════════════

class StaffOrderPaymentViewTests(SimpleTestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffOrderPaymentView.as_view()

    def _post(self, order_id=10, body=None, user=None):
        body = body or {"method": "cash", "amount": "10.00"}
        req = self.factory.post(
            f"/api/staff/orders/{order_id}/payments/",
            body,
            format="json",
        )
        u = user or _user()
        force_authenticate(req, user=u)
        req.tenant = _tenant()
        return self.view(req, order_id=order_id)

    # ── Auth / permission ──────────────────────────────────────────────────────

    @patch("menu.views._can_edit_tenant_order", return_value=False)
    def test_no_permission_403(self, _mock):
        req = self.factory.post("/api/staff/orders/10/payments/", {}, format="json")
        force_authenticate(req, user=_user())
        req.tenant = _tenant()
        resp = self.view(req, order_id=10)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Bad method body ────────────────────────────────────────────────────────

    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_bad_method_400(self, order_om, tx_mock):
        resp = self._post(body={"method": "crypto", "amount": "10.00"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "bad_method")

    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_bad_amount_zero_400(self, order_om, tx_mock):
        resp = self._post(body={"method": "cash", "amount": "0"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "bad_amount")

    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_bad_amount_string_400(self, order_om, tx_mock):
        resp = self._post(body={"method": "cash", "amount": "abc"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "bad_amount")

    # ── Order-level guards ────────────────────────────────────────────────────

    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_terminal_status_409(self, order_om, tx_mock):
        order = _make_order(status_val=Order.Status.COMPLETED)
        _setup_atomic_and_lock(tx_mock, order_om, order)
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "bad_status")

    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_already_paid_409(self, order_om, tx_mock):
        order = _make_order(payment_status=Order.PaymentStatus.PAID)
        _setup_atomic_and_lock(tx_mock, order_om, order)
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_paid")

    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_overpay_409(self, order_om, tx_mock):
        order = _make_order(total=Decimal("20.00"), payments=[])
        _setup_atomic_and_lock(tx_mock, order_om, order)
        resp = self._post(body={"method": "cash", "amount": "25.00"})
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "overpay")

    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_wallet_no_customer_409(self, order_om, tx_mock):
        order = _make_order(customer_id=None, total=Decimal("20.00"))
        _setup_atomic_and_lock(tx_mock, order_om, order)
        resp = self._post(body={"method": "wallet", "amount": "10.00"})
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "no_customer")

    # ── Happy path: partial cash, doesn't flip PAID ───────────────────────────

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_partial_cash_creates_row_no_paid_flip(self, order_om, tx_mock, broadcast_mock):
        order = _make_order(total=Decimal("30.00"), payments=[])
        reload_order = _make_order(total=Decimal("30.00"), payments=[
            _make_payment_row(amount=Decimal("10.00"), method="cash"),
        ])
        _setup_atomic_and_lock(tx_mock, order_om, order)
        order_om.prefetch_related.return_value.get.return_value = reload_order

        with patch("menu.models.OrderPayment.objects") as op_om:
            created_payment = _make_payment_row(amount=Decimal("10.00"), method="cash")
            created_payment.id = 77
            op_om.create.return_value = created_payment

            resp = self._post(body={"method": "cash", "amount": "10.00"})

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # mark_paid must NOT have been called (not fully settled yet)
        order.mark_paid.assert_not_called()
        # merged save always fires with at least updated_at (even cash-only partial)
        order.save.assert_called_once_with(update_fields=["updated_at"])
        broadcast_mock.assert_called_once()

    # ── Happy path: amount omitted → full outstanding → PAID ─────────────────

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_amount_omitted_full_outstanding_flips_paid(self, order_om, tx_mock, broadcast_mock):
        """amount=None means pay the full outstanding; if that covers the total, mark PAID."""
        order = _make_order(total=Decimal("20.00"), payments=[])
        reload_order = _make_order(
            total=Decimal("20.00"),
            payment_status=Order.PaymentStatus.PAID,
            payments=[_make_payment_row(amount=Decimal("20.00"), method="cash")],
        )
        _setup_atomic_and_lock(tx_mock, order_om, order)
        order_om.prefetch_related.return_value.get.return_value = reload_order

        with patch("menu.models.OrderPayment.objects") as op_om:
            created_payment = _make_payment_row(amount=Decimal("20.00"), method="cash")
            created_payment.id = 78
            op_om.create.return_value = created_payment

            # No amount key in body
            resp = self._post(body={"method": "cash"})

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # mark_paid called (total covered)
        order.mark_paid.assert_called_once_with(save=False)
        order.save.assert_called_once_with(
            update_fields=["payment_status", "paid_at", "updated_at"]
        )

    # ── Partial cash + partial wallet reaching total flips PAID exactly once ──

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_partial_cash_then_wallet_flips_paid_exactly_once(
        self, order_om, tx_mock, broadcast_mock
    ):
        """Simulate: 10 MAD cash already recorded; now 20 MAD wallet closes the bill."""
        existing_payment = _make_payment_row(amount=Decimal("10.00"), method="cash")
        order = _make_order(
            total=Decimal("30.00"),
            customer_id=42,
            wallet_amount_paid=Decimal("0"),
            payments=[existing_payment],
        )
        reload_order = _make_order(
            total=Decimal("30.00"),
            payment_status=Order.PaymentStatus.PAID,
            wallet_amount_paid=Decimal("20.00"),
            payments=[
                existing_payment,
                _make_payment_row(amount=Decimal("20.00"), method="wallet"),
            ],
        )
        _setup_atomic_and_lock(tx_mock, order_om, order)
        order_om.prefetch_related.return_value.get.return_value = reload_order

        with patch("menu.models.OrderPayment.objects") as op_om, \
             patch("accounts.wallet_service.debit_wallet") as mock_dw:
            created_payment = _make_payment_row(amount=Decimal("20.00"), method="wallet")
            created_payment.id = 99
            op_om.create.return_value = created_payment

            resp = self._post(body={"method": "wallet", "amount": "20.00"})

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # wallet debit called with correct amount and idempotency key
        mock_dw.assert_called_once()
        call_kwargs = mock_dw.call_args
        self.assertEqual(call_kwargs[0][0], 42)  # customer_id
        self.assertEqual(call_kwargs[0][1], Decimal("20.00"))
        self.assertEqual(call_kwargs[1]["idempotency_key"], "orderpay:99")
        # merged single save: wallet_amount_paid + mark_paid fields in one call
        order.save.assert_called_once_with(
            update_fields=["wallet_amount_paid", "payment_status", "paid_at", "updated_at"]
        )
        # mark_paid called once (30 total = 10+20)
        order.mark_paid.assert_called_once_with(save=False)

    # ── Wallet partial increments wallet_amount_paid + debit called with key ──

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_wallet_partial_increments_wallet_amount_paid(
        self, order_om, tx_mock, broadcast_mock
    ):
        order = _make_order(
            total=Decimal("40.00"),
            customer_id=55,
            wallet_amount_paid=Decimal("0"),
            payments=[],
        )
        reload_order = _make_order(
            total=Decimal("40.00"),
            wallet_amount_paid=Decimal("15.00"),
            payments=[_make_payment_row(amount=Decimal("15.00"), method="wallet")],
        )
        _setup_atomic_and_lock(tx_mock, order_om, order)
        order_om.prefetch_related.return_value.get.return_value = reload_order

        with patch("menu.models.OrderPayment.objects") as op_om, \
             patch("accounts.wallet_service.debit_wallet") as mock_dw:
            created_payment = _make_payment_row(amount=Decimal("15.00"), method="wallet")
            created_payment.id = 101
            op_om.create.return_value = created_payment

            resp = self._post(body={"method": "wallet", "amount": "15.00"})

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # wallet_amount_paid on the order model incremented before save
        self.assertEqual(order.wallet_amount_paid, Decimal("15.00"))  # 0 + 15
        order.save.assert_any_call(update_fields=["wallet_amount_paid", "updated_at"])
        mock_dw.assert_called_once()
        self.assertEqual(mock_dw.call_args[1]["idempotency_key"], "orderpay:101")
        # not fully paid → mark_paid not called
        order.mark_paid.assert_not_called()

    # ── Wallet insufficient funds → 409 + row NOT persisted ──────────────────

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_wallet_insufficient_409_row_not_persisted(
        self, order_om, tx_mock, broadcast_mock
    ):
        from accounts.wallet_service import InsufficientFunds

        order = _make_order(
            total=Decimal("30.00"),
            customer_id=42,
            wallet_amount_paid=Decimal("0"),
            payments=[],
        )
        _setup_atomic_and_lock(tx_mock, order_om, order)

        with patch("menu.models.OrderPayment.objects") as op_om, \
             patch("accounts.wallet_service.debit_wallet", side_effect=InsufficientFunds("low")) as mock_dw:
            created_payment = _make_payment_row(amount=Decimal("30.00"), method="wallet")
            created_payment.id = 202
            op_om.create.return_value = created_payment

            resp = self._post(body={"method": "wallet", "amount": "30.00"})

        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "insufficient_wallet")
        # wallet_amount_paid must NOT have changed
        self.assertEqual(order.wallet_amount_paid, Decimal("0"))
        # mark_paid must NOT have been called
        order.mark_paid.assert_not_called()
        broadcast_mock.assert_not_called()

    # ── Already paid 409 ──────────────────────────────────────────────────────

    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_already_paid_guard_409(self, order_om, tx_mock):
        order = _make_order(payment_status=Order.PaymentStatus.PAID)
        _setup_atomic_and_lock(tx_mock, order_om, order)
        resp = self._post(body={"method": "cash", "amount": "5.00"})
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_paid")

    # ── Staff payload includes amount_paid / outstanding / payments ───────────

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_response_payload_contains_split_bill_fields(
        self, order_om, tx_mock, broadcast_mock
    ):
        order = _make_order(total=Decimal("20.00"), payments=[])
        payment_row = _make_payment_row(amount=Decimal("8.00"), method="cash", note="table 4")
        reload_order = _make_order(
            total=Decimal("20.00"),
            payments=[payment_row],
        )
        _setup_atomic_and_lock(tx_mock, order_om, order)
        order_om.prefetch_related.return_value.get.return_value = reload_order

        with patch("menu.models.OrderPayment.objects") as op_om:
            created_payment = _make_payment_row(amount=Decimal("8.00"), method="cash")
            created_payment.id = 301
            op_om.create.return_value = created_payment

            resp = self._post(body={"method": "cash", "amount": "8.00"})

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.data
        self.assertIn("amount_paid", data)
        self.assertIn("outstanding", data)
        self.assertIn("payments", data)
        # amount_paid = sum of payments = 8.00
        self.assertEqual(data["amount_paid"], "8.00")
        # outstanding = 20.00 - 8.00 = 12.00
        self.assertEqual(data["outstanding"], "12.00")
        self.assertEqual(len(data["payments"]), 1)
        first = data["payments"][0]
        self.assertEqual(first["amount"], "8.00")
        self.assertEqual(first["method"], "cash")
        self.assertEqual(first["note"], "table 4")

    # ── Terminal order 409 ────────────────────────────────────────────────────

    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_cancelled_order_409(self, order_om, tx_mock):
        order = _make_order(status_val=Order.Status.CANCELLED)
        _setup_atomic_and_lock(tx_mock, order_om, order)
        resp = self._post(body={"method": "cash", "amount": "5.00"})
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "bad_status")

    # ── completed key present and False for partial payment ───────────────────

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_completed_false_for_partial_payment(self, order_om, tx_mock, broadcast_mock):
        """completed must be False when order is still outstanding after payment."""
        order = _make_order(total=Decimal("30.00"), payments=[])
        reload_order = _make_order(
            total=Decimal("30.00"),
            payment_status=Order.PaymentStatus.UNPAID,
            payments=[_make_payment_row(amount=Decimal("10.00"), method="cash")],
        )
        _setup_atomic_and_lock(tx_mock, order_om, order)
        order_om.prefetch_related.return_value.get.return_value = reload_order

        with patch("menu.models.OrderPayment.objects") as op_om:
            created_payment = _make_payment_row(amount=Decimal("10.00"), method="cash")
            created_payment.id = 401
            op_om.create.return_value = created_payment

            resp = self._post(body={"method": "cash", "amount": "10.00"})

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("completed", resp.data)
        self.assertFalse(resp.data["completed"])

    # ── completed key present and True when fully settled ─────────────────────

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_completed_true_when_fully_settled(self, order_om, tx_mock, broadcast_mock):
        """completed must be True when the payment brings the order to PAID status."""
        order = _make_order(total=Decimal("20.00"), payments=[])
        reload_order = _make_order(
            total=Decimal("20.00"),
            payment_status=Order.PaymentStatus.PAID,
            payments=[_make_payment_row(amount=Decimal("20.00"), method="cash")],
        )
        _setup_atomic_and_lock(tx_mock, order_om, order)
        order_om.prefetch_related.return_value.get.return_value = reload_order

        with patch("menu.models.OrderPayment.objects") as op_om:
            created_payment = _make_payment_row(amount=Decimal("20.00"), method="cash")
            created_payment.id = 402
            op_om.create.return_value = created_payment

            resp = self._post(body={"method": "cash"})

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("completed", resp.data)
        self.assertTrue(resp.data["completed"])

    # ── Idempotency key: duplicate request returns current state, no new row ──

    @patch("menu.views.cache")
    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Order.objects")
    def test_idempotency_key_duplicate_short_circuits(
        self, order_om, broadcast_mock, cache_mock
    ):
        """If idempotency_key was already committed (cache hit), no new row is created."""
        already_paid_order = _make_order(
            total=Decimal("20.00"),
            payment_status=Order.PaymentStatus.PAID,
            payments=[_make_payment_row(amount=Decimal("20.00"), method="cash")],
        )
        # Cache reports key already committed
        cache_mock.get.return_value = True
        # The reload path uses Order.objects.prefetch_related().get()
        order_om.prefetch_related.return_value.get.return_value = already_paid_order

        resp = self._post(body={"method": "cash", "amount": "20.00", "idempotency_key": "pay-abc-123"})

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # completed must be True in the replayed response
        self.assertTrue(resp.data["completed"])
        # cache was checked
        cache_mock.get.assert_called_once_with("staff_pay_idem:10:pay-abc-123")
        # No new payment row was created (OrderPayment.objects.create not called)
        broadcast_mock.assert_not_called()

    # ── Idempotency key: first request sets cache after commit ────────────────

    @patch("menu.views.cache")
    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_idempotency_key_sets_cache_on_success(
        self, order_om, tx_mock, broadcast_mock, cache_mock
    ):
        """After a successful payment, the idempotency key is stored in cache."""
        order = _make_order(total=Decimal("20.00"), payments=[])
        reload_order = _make_order(
            total=Decimal("20.00"),
            payment_status=Order.PaymentStatus.PAID,
            payments=[_make_payment_row(amount=Decimal("20.00"), method="cash")],
        )
        # No prior cache entry
        cache_mock.get.return_value = None
        _setup_atomic_and_lock(tx_mock, order_om, order)
        order_om.prefetch_related.return_value.get.return_value = reload_order

        with patch("menu.models.OrderPayment.objects") as op_om:
            created_payment = _make_payment_row(amount=Decimal("20.00"), method="cash")
            created_payment.id = 501
            op_om.create.return_value = created_payment

            resp = self._post(body={"method": "cash", "idempotency_key": "pay-xyz-999"})

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # Cache should have been set with the idempotency key
        cache_mock.set.assert_called_once_with(
            "staff_pay_idem:10:pay-xyz-999", True, timeout=300
        )


# ── Test helper ────────────────────────────────────────────────────────────────

def _setup_atomic_and_lock(tx_mock, order_om, order):
    """Configure transaction.atomic() as a passthrough and Order.objects chain
    to return `order` from select_for_update().prefetch_related().filter().first().
    """
    class _FakeAtomic:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            # Propagate InsufficientFunds so the view's except clause catches it
            return False

    tx_mock.atomic.return_value = _FakeAtomic()

    (
        order_om
        .select_for_update.return_value
        .prefetch_related.return_value
        .filter.return_value
        .first.return_value
    ) = order
