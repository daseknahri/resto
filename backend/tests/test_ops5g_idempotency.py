"""OPS-5g — idempotency-key tenant-namespacing + redemption hardening contract tests.

Closes the last money/IDOR cluster after OPS-5e/5f:

  A. Three customer/staff order-payment wallet calls in menu/views.py derive their
     idempotency_key from TENANT-SCHEMA-LOCAL ids. WalletTransaction is PUBLIC-schema, so
     the key is a GLOBAL namespace; a bare tenant-local id can collide cross-tenant and
     silently replay. Each key must now embed connection.schema_name:
       1. CustomerOrderPayWalletView  -> f"order-pay-{schema}-{order_number}"
       2. StaffOrderPaymentView debit -> f"orderpay:{schema}:{payment.id}"
       3. void-item refund credit     -> f"voiditem:{schema}:{item_id}"

  B. CustomerLoyaltyRedeemView replay lookup is now CUSTOMER-scoped on BOTH paths
     (pre-flight + IntegrityError handler) so a client-supplied GLOBAL idempotency_key
     can't read another customer's redemption (IDOR). The view also wires a
     per-customer throttle.

  C. Wallet-paid rides take no hold at booking; the completion-time cash fallback is now
     EXPLICIT (flag + rider-visible note) instead of a silent payment_method flip, and the
     authoritative balance re-verification happens atomically under the rider lock in
     debit_wallet at settle time.

  D. Throttle wiring: LoyaltyRedeemThrottle (scope loyalty_redeem) + VoucherRedeemThrottle
     (scope voucher_redeem) exist with the exact names/scopes, and both rates are registered.

House style: SimpleTestCase + MagicMock, no real DB.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.db import connection
from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from menu.models import Order
from accounts.models import User


# Live test-DB schema name — the view derives the key from connection.schema_name, so the
# expected key is computed from the same source rather than hard-coded.
SCHEMA = connection.schema_name


# ═════════════════════════════════════════════════════════════════════════════
# A. The three order-payment idempotency keys embed the tenant schema name
# ═════════════════════════════════════════════════════════════════════════════

class _OrderPayWalletHelpers:
    @staticmethod
    def _order(customer_id=42, total="45.00", paid="0.00",
               payment_status="unpaid", order_status="ready"):
        o = MagicMock()
        o.order_number = "ORD-1"
        o.customer_id = customer_id
        o.total = Decimal(total)
        o.wallet_amount_paid = Decimal(paid)
        o.payment_status = payment_status
        o.status = order_status
        return o


class CustomerOrderPayWalletKeyTests(SimpleTestCase, _OrderPayWalletHelpers):
    """(1) CustomerOrderPayWalletView debit key = f"order-pay-{schema}-{order_number}"."""

    def setUp(self):
        from menu.views import CustomerOrderPayWalletView
        self.factory = APIRequestFactory()
        self.view = CustomerOrderPayWalletView.as_view()

    def _post(self, session):
        req = self.factory.post("/api/orders/ORD-1/pay-wallet/")
        req.session = session
        req.tenant = MagicMock(id=7)
        return req

    @patch("accounts.wallet_service.debit_wallet")
    @patch("menu.views.Order.objects")
    def test_key_is_schema_namespaced(self, om, debit):
        order = self._order(total="45.00", paid="0.00")
        om.filter.return_value.first.return_value = order
        debit.return_value = SimpleNamespace(balance_after=Decimal("5.00"))

        resp = self.view(self._post({"customer_id": 42}), order_number="ORD-1")

        self.assertEqual(resp.status_code, 200)
        debit.assert_called_once()
        key = debit.call_args.kwargs.get("idempotency_key")
        self.assertEqual(key, f"order-pay-{SCHEMA}-ORD-1")
        # The schema name must actually appear in the key (the whole point of the fix).
        self.assertIn(SCHEMA, key)

    @patch("accounts.wallet_service.debit_wallet")
    @patch("menu.views.Order.objects")
    def test_already_paid_short_circuit_is_the_durable_backstop(self, om, debit):
        """A repeat on an already-PAID order returns paid WITHOUT touching the wallet —
        the order-status guard, not the idempotency key, is the durable re-payment block."""
        order = self._order(payment_status=Order.PaymentStatus.PAID)
        om.filter.return_value.first.return_value = order
        resp = self.view(self._post({"customer_id": 42}), order_number="ORD-1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "paid")
        debit.assert_not_called()


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


def _make_order(total=Decimal("30.00"), customer_id=42, wallet_amount_paid=Decimal("0"),
                payment_status=Order.PaymentStatus.UNPAID, payments=None):
    order = MagicMock()
    order.id = 10
    order.order_number = "ORD-001"
    order.status = Order.Status.PENDING
    order.payment_status = payment_status
    order.total = total
    order.wallet_amount_paid = wallet_amount_paid
    order.customer_id = customer_id
    order.paid_at = None
    order.save = MagicMock()
    order.mark_paid = MagicMock()
    _payments = payments or []
    payments_qs = MagicMock()
    payments_qs.all.return_value = _payments
    order.payments = payments_qs
    items_qs = MagicMock()
    items_qs.all.return_value = []
    order.items = items_qs
    return order


def _make_payment_row(amount=Decimal("20.00"), method="wallet"):
    p = MagicMock()
    p.amount = amount
    p.method = method
    p.recorded_by_name = "Alice Waiter"
    p.note = ""
    created_at = MagicMock()
    created_at.isoformat.return_value = "2026-06-11T12:00:00+00:00"
    p.created_at = created_at
    return p


def _setup_atomic_and_lock(tx_mock, order_om, order):
    class _FakeAtomic:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    tx_mock.atomic.return_value = _FakeAtomic()
    (
        order_om
        .select_for_update.return_value
        .prefetch_related.return_value
        .filter.return_value
        .first.return_value
    ) = order


class StaffOrderPaymentKeyTests(SimpleTestCase):
    """(2) StaffOrderPaymentView wallet debit key = f"orderpay:{schema}:{payment.id}"."""

    def setUp(self):
        from menu.views import StaffOrderPaymentView
        self.factory = APIRequestFactory()
        self.view = StaffOrderPaymentView.as_view()

    def _post(self, order_id=10, body=None):
        body = body or {"method": "wallet", "amount": "20.00"}
        req = self.factory.post(f"/api/staff/orders/{order_id}/payments/", body, format="json")
        force_authenticate(req, user=_user())
        req.tenant = SimpleNamespace(id=1)
        return self.view(req, order_id=order_id)

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_wallet_debit_key_is_schema_namespaced(self, order_om, tx_mock, _broadcast):
        order = _make_order(total=Decimal("30.00"), customer_id=42,
                            payments=[_make_payment_row(amount=Decimal("10.00"), method="cash")])
        reload_order = _make_order(total=Decimal("30.00"))
        _setup_atomic_and_lock(tx_mock, order_om, order)
        order_om.prefetch_related.return_value.get.return_value = reload_order

        with patch("menu.models.OrderPayment.objects") as op_om, \
                patch("accounts.wallet_service.debit_wallet") as mock_dw:
            created_payment = _make_payment_row(amount=Decimal("20.00"), method="wallet")
            created_payment.id = 99
            op_om.create.return_value = created_payment
            resp = self._post(body={"method": "wallet", "amount": "20.00"})

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        mock_dw.assert_called_once()
        key = mock_dw.call_args[1]["idempotency_key"]
        self.assertEqual(key, f"orderpay:{SCHEMA}:99")
        self.assertIn(SCHEMA, key)

    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_already_paid_guard_blocks_before_any_debit(self, order_om, tx_mock):
        """OrderPayment unique key + order already-PAID guard are the durable backstop:
        an already-PAID order is refused (409) before any wallet movement."""
        order = _make_order(payment_status=Order.PaymentStatus.PAID)
        _setup_atomic_and_lock(tx_mock, order_om, order)
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_paid")


class VoidItemRefundKeyTests(SimpleTestCase):
    """(3) void-item refund credit key = f"voiditem:{schema}:{item_id}"."""

    def setUp(self):
        from menu.views import StaffVoidOrderItemView
        self.factory = APIRequestFactory()
        self.view = StaffVoidOrderItemView.as_view()
        # Patch _can_access_order so the unit test doesn't hit the DB for section lookups.
        _patcher = patch("menu.views._can_access_order", return_value=True)
        _patcher.start()
        self.addCleanup(_patcher.stop)

    def _make_item(self, item_id=901, subtotal=Decimal("20.00"), is_voided=False):
        item = MagicMock()
        item.id = item_id
        item.dish_name = "Burger"
        item.dish_slug = "burger"
        item.qty = 2
        item.unit_price = Decimal("10.00")
        item.subtotal = subtotal
        item.options = []
        item.note = ""
        item.is_ready = False
        item.is_voided = is_voided
        item.save = MagicMock()
        return item

    def _order(self, items, customer_id=42, wallet_paid=Decimal("35.00")):
        from menu.models import Order as _Order
        o = MagicMock()
        o.id = 10
        o.pk = 10
        o.order_number = "ORD-001"
        o.status = _Order.Status.PENDING
        o.fulfillment_type = _Order.FulfillmentType.TABLE
        o.payment_status = _Order.PaymentStatus.PAID
        o.total = Decimal("35.00")
        # Decimal fields read by _recompute_order_totals (avoid Mock→Decimal coercion errors).
        o.delivery_fee = Decimal("0")
        o.tip_amount = Decimal("0")
        o.promotion_discount = Decimal("0")
        o.loyalty_discount = Decimal("0")
        o.wallet_amount_paid = wallet_paid
        o.customer_id = customer_id
        o.points_earned = 0  # loyalty-clawback branch reads this; 0 → skipped cleanly
        o.table_label = "T1"
        o.customer_name = "Bob"
        o.customer_note = ""
        o.owner_note = ""
        o.estimated_ready_minutes = None
        o.currency = "MAD"
        o.scheduled_for = None
        o.save = MagicMock()
        o.mark_paid = MagicMock()
        o.created_at = MagicMock()
        o.created_at.isoformat.return_value = "2026-06-11T10:00:00+00:00"
        o.updated_at = MagicMock()
        o.updated_at.isoformat.return_value = "2026-06-11T10:00:00+00:00"
        items_qs = MagicMock()
        items_qs.all.return_value = items
        items_qs.filter.return_value.first.return_value = items[0]
        o.items = items_qs
        payments_qs = MagicMock()
        payments_qs.all.return_value = []
        o.payments = payments_qs
        return o

    def _post(self, item_id=901):
        req = self.factory.post(f"/api/staff/orders/10/items/{item_id}/void/", {}, format="json")
        force_authenticate(req, user=_user())
        req.tenant = SimpleNamespace(id=1)
        return self.view(req, order_id=10, item_id=item_id)

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_void_refund_key_is_schema_namespaced(self, order_om, tx_mock, dish_om, _broadcast):
        item = self._make_item(item_id=901, subtotal=Decimal("20.00"), is_voided=False)
        remaining = self._make_item(item_id=902, subtotal=Decimal("15.00"))
        first_order = self._order(items=[item, remaining])
        voided_item = self._make_item(item_id=901, is_voided=True, subtotal=Decimal("20.00"))
        second_order = self._order(items=[voided_item, remaining])

        order_om.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        order_om.select_for_update.return_value.prefetch_related.return_value.get.return_value = second_order

        tx_mock.atomic.return_value.__enter__ = MagicMock(return_value=None)
        tx_mock.atomic.return_value.__exit__ = MagicMock(return_value=False)
        dish_om.filter.return_value.select_for_update.return_value = []

        with patch("accounts.wallet_service.credit_wallet") as mock_cw:
            resp = self._post(item_id=901)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_cw.assert_called_once()
        key = mock_cw.call_args[1]["idempotency_key"]
        self.assertEqual(key, f"voiditem:{SCHEMA}:901")
        self.assertIn(SCHEMA, key)


# ═════════════════════════════════════════════════════════════════════════════
# B. Loyalty-redeem replay lookup is CUSTOMER-scoped (a foreign key doesn't leak)
# ═════════════════════════════════════════════════════════════════════════════

class LoyaltyRedeemReplayScopingTests(SimpleTestCase):
    """The client-supplied idempotency_key replay lookup must filter by THIS customer on
    BOTH the pre-flight and the IntegrityError-handler paths, so an attacker replaying
    another customer's key can't read that customer's redemption back out."""

    def setUp(self):
        from menu.views import CustomerLoyaltyRedeemView
        self.factory = APIRequestFactory()
        self.view = CustomerLoyaltyRedeemView.as_view()

    def _post(self, body, customer_id=1):
        req = self.factory.post("/api/customer/loyalty/redeem/", body, format="json")
        req.user = MagicMock(is_authenticated=True)
        req.user.customer_id = customer_id
        req.user.pk = customer_id
        return self.view(req)

    @patch("accounts.models.WalletTransaction.objects")
    @patch("menu.views.LoyaltyConfig.objects")
    @patch("accounts.models.Customer.objects")
    def test_preflight_replay_lookup_is_customer_scoped(self, mock_cust, mock_cfg, mock_wt):
        customer = MagicMock(phone_verified=True, loyalty_points=500,
                             wallet_balance=Decimal("42.00"))
        customer.id = 1
        mock_cust.get.return_value = customer
        mock_cfg.filter.return_value.first.return_value = MagicMock(
            redeem_threshold=100, points_value=Decimal("0.10"))
        prior = MagicMock(amount=Decimal("10.00"), reference="loyalty:100pts")
        mock_wt.filter.return_value.first.return_value = prior

        resp = self._post({"points": 100, "idempotency_key": "victim-key"}, customer_id=1)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["duplicate"])
        # The replay lookup must constrain on the requesting customer's id — without this
        # filter an attacker who guesses a victim's key reads the victim's redemption.
        replay_kwargs = mock_wt.filter.call_args.kwargs
        self.assertEqual(replay_kwargs.get("customer_id"), 1)
        # And it must still be scoped to the LOYALTY type (a foreign tx type can't alias).
        from accounts.models import WalletTransaction
        self.assertEqual(replay_kwargs.get("type"), WalletTransaction.Type.LOYALTY)

    @patch("accounts.models.WalletTransaction.objects")
    @patch("menu.views.LoyaltyConfig.objects")
    @patch("accounts.models.Customer.objects")
    def test_foreign_customer_key_does_not_leak(self, mock_cust, mock_cfg, mock_wt):
        """With the customer_id filter present, a victim's tx is NOT returned to the
        attacker: the customer-scoped queryset yields nothing, so no duplicate replay of
        someone else's amount happens (the attacker proceeds on their own balance instead)."""
        attacker = MagicMock(phone_verified=True, loyalty_points=50,
                             wallet_balance=Decimal("0.00"))
        attacker.id = 2
        mock_cust.get.return_value = attacker
        mock_cfg.filter.return_value.first.return_value = MagicMock(
            redeem_threshold=100, points_value=Decimal("0.10"))
        # The customer-scoped lookup finds NOTHING for the attacker (the victim's row is
        # excluded by customer_id=2), so .first() returns None → no leak.
        mock_wt.filter.return_value.first.return_value = None

        resp = self._post({"points": 100, "idempotency_key": "victim-key"}, customer_id=2)

        # No duplicate replay; the attacker falls through to the threshold guard on THEIR
        # own (insufficient) points → 400, never reading the victim's amount.
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        replay_kwargs = mock_wt.filter.call_args.kwargs
        self.assertEqual(replay_kwargs.get("customer_id"), 2)

    @patch("accounts.models.WalletTransaction.objects")
    @patch("menu.views.LoyaltyConfig.objects")
    @patch("accounts.models.Customer.objects")
    def test_integrity_error_handler_replay_is_customer_scoped(self, mock_cust, mock_cfg, mock_wt):
        """The concurrent-duplicate (IntegrityError) handler must ALSO scope the replay
        lookup to the requesting customer."""
        from django.db import IntegrityError
        customer = MagicMock(phone_verified=True, loyalty_points=500,
                             wallet_balance=Decimal("42.00"))
        customer.id = 1
        customer.refresh_from_db = MagicMock()
        mock_cust.get.return_value = customer
        mock_cfg.filter.return_value.first.return_value = MagicMock(
            redeem_threshold=100, points_value=Decimal("0.10"))
        # Pre-flight lookup returns None (no prior), so we proceed into the atomic block …
        mock_wt.filter.return_value.first.return_value = None

        locked = MagicMock()
        locked.loyalty_points = 500
        locked.wallet_balance = Decimal("42.00")
        mock_cust.select_for_update.return_value.get.return_value = locked
        # … where the create() raises IntegrityError (concurrent winner took the key).
        mock_wt.create.side_effect = IntegrityError("dupe key")

        with patch("django.db.transaction.atomic"):
            resp = self._post({"points": 100, "idempotency_key": "abc"}, customer_id=1)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["duplicate"])
        # The LAST .filter() call (the handler's replay lookup) is customer-scoped.
        replay_kwargs = mock_wt.filter.call_args.kwargs
        self.assertEqual(replay_kwargs.get("customer_id"), 1)


class LoyaltyRedeemKeySchemaNamespacingTests(SimpleTestCase):
    """OPS-5h: the client-supplied loyalty idempotency_key is server-namespaced with the
    tenant schema — f"loyalty:{schema}:{raw}" — at ALL THREE sites (pre-flight read, create,
    IntegrityError refetch). Without this, the same customer reusing the same client key
    across two tenants gets the first tenant's row back as a bogus "duplicate" and the
    second tenant's legitimate redemption is silently refused."""

    RAW = "client-key-xyz"
    EXPECT = f"loyalty:{SCHEMA}:{RAW}"

    def setUp(self):
        from menu.views import CustomerLoyaltyRedeemView
        self.factory = APIRequestFactory()
        self.view = CustomerLoyaltyRedeemView.as_view()

    def _post(self, customer_id=1):
        req = self.factory.post(
            "/api/customer/loyalty/redeem/",
            {"points": 100, "idempotency_key": self.RAW},
            format="json",
        )
        req.user = MagicMock(is_authenticated=True)
        req.user.customer_id = customer_id
        req.user.pk = customer_id
        return self.view(req)

    @patch("accounts.models.WalletTransaction.objects")
    @patch("menu.views.LoyaltyConfig.objects")
    @patch("accounts.models.Customer.objects")
    def test_preflight_read_uses_namespaced_key(self, mock_cust, mock_cfg, mock_wt):
        customer = MagicMock(phone_verified=True, loyalty_points=500,
                             wallet_balance=Decimal("42.00"))
        customer.id = 1
        mock_cust.get.return_value = customer
        mock_cfg.filter.return_value.first.return_value = MagicMock(
            redeem_threshold=100, points_value=Decimal("0.10"))
        mock_wt.filter.return_value.first.return_value = MagicMock(
            amount=Decimal("10.00"), reference="loyalty:100pts")

        resp = self._post(customer_id=1)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # The pre-flight replay lookup queries the SCHEMA-NAMESPACED key, not the raw one.
        read_kwargs = mock_wt.filter.call_args.kwargs
        self.assertEqual(read_kwargs.get("idempotency_key"), self.EXPECT)
        self.assertIn(SCHEMA, read_kwargs["idempotency_key"])

    @patch("accounts.models.WalletTransaction.objects")
    @patch("menu.views.LoyaltyConfig.objects")
    @patch("accounts.models.Customer.objects")
    def test_create_uses_namespaced_key(self, mock_cust, mock_cfg, mock_wt):
        customer = MagicMock(phone_verified=True, loyalty_points=500,
                             wallet_balance=Decimal("0.00"))
        customer.id = 1
        mock_cust.get.return_value = customer
        mock_cfg.filter.return_value.first.return_value = MagicMock(
            redeem_threshold=100, points_value=Decimal("0.10"))
        mock_wt.filter.return_value.first.return_value = None  # no prior → proceed to create

        locked = MagicMock()
        locked.loyalty_points = 500
        locked.wallet_balance = Decimal("0.00")
        mock_cust.select_for_update.return_value.get.return_value = locked

        with patch("django.db.transaction.atomic"):
            resp = self._post(customer_id=1)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_wt.create.assert_called_once()
        create_kwargs = mock_wt.create.call_args.kwargs
        self.assertEqual(create_kwargs.get("idempotency_key"), self.EXPECT)
        self.assertIn(SCHEMA, create_kwargs["idempotency_key"])
        # The non-idempotency `reference` field is NOT namespaced (left as the points marker).
        self.assertEqual(create_kwargs.get("reference"), "loyalty:100pts")

    @patch("accounts.models.WalletTransaction.objects")
    @patch("menu.views.LoyaltyConfig.objects")
    @patch("accounts.models.Customer.objects")
    def test_integrity_replay_refetch_uses_namespaced_key(self, mock_cust, mock_cfg, mock_wt):
        from django.db import IntegrityError
        customer = MagicMock(phone_verified=True, loyalty_points=500,
                             wallet_balance=Decimal("0.00"))
        customer.id = 1
        customer.refresh_from_db = MagicMock()
        mock_cust.get.return_value = customer
        mock_cfg.filter.return_value.first.return_value = MagicMock(
            redeem_threshold=100, points_value=Decimal("0.10"))
        mock_wt.filter.return_value.first.return_value = None  # pre-flight: no prior

        locked = MagicMock()
        locked.loyalty_points = 500
        locked.wallet_balance = Decimal("0.00")
        mock_cust.select_for_update.return_value.get.return_value = locked
        mock_wt.create.side_effect = IntegrityError("dupe key")  # concurrent winner took it

        with patch("django.db.transaction.atomic"):
            resp = self._post(customer_id=1)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["duplicate"])
        # The IntegrityError-handler refetch (the LAST .filter call) uses the namespaced key.
        refetch_kwargs = mock_wt.filter.call_args.kwargs
        self.assertEqual(refetch_kwargs.get("idempotency_key"), self.EXPECT)
        self.assertIn(SCHEMA, refetch_kwargs["idempotency_key"])


# ═════════════════════════════════════════════════════════════════════════════
# C. Ride wallet-pay: explicit, recorded cash fallback (no silent flip)
# ═════════════════════════════════════════════════════════════════════════════

class RideSettleCashFallbackTests(SimpleTestCase):
    """settle_ride takes no hold at booking; the completion-time debit_wallet locks the
    rider row and re-verifies the balance. On a short balance the fallback to cash is now
    RECORDED (flag + rider-visible note) instead of a silent payment_method flip."""

    @patch("accounts.ride_service.debit_wallet")
    @patch("accounts.ride_service.PlatformConfig")
    def test_insufficient_balance_records_explicit_cash_fallback(self, mock_cfg, mock_debit):
        from accounts.ride_service import _do_settle
        from accounts.wallet_service import InsufficientFunds

        mock_cfg.get_solo.return_value = MagicMock(ride_commission_pct=Decimal("0"))
        mock_debit.side_effect = InsufficientFunds("not enough")

        ride = SimpleNamespace(
            id=43, payment_method="wallet", fare=Decimal("20.00"),
            rider_id=10, driver_id=5, paid_with_wallet=True, kind="ride",
        )
        _do_settle(ride)

        # Authoritative re-verification happened via debit_wallet (it locks the rider row).
        mock_debit.assert_called_once()
        # The fallback is EXPLICIT and RECORDED, not a silent flip:
        self.assertEqual(ride.payment_method, "cash")
        self.assertTrue(ride.cash_fallback)
        self.assertTrue(ride.cash_fallback_note)  # rider-visible reason string
        self.assertFalse(ride.paid_with_wallet)

    @patch("accounts.ride_service.credit_wallet")
    @patch("accounts.ride_service.debit_wallet")
    @patch("accounts.ride_service.PlatformConfig")
    def test_successful_wallet_settle_clears_fallback_flag(self, mock_cfg, mock_debit, mock_credit):
        from accounts.ride_service import _do_settle

        mock_cfg.get_solo.return_value = MagicMock(ride_commission_pct=Decimal("0"))
        ride = SimpleNamespace(
            id=44, payment_method="wallet", fare=Decimal("20.00"),
            rider_id=10, driver_id=5, paid_with_wallet=False, kind="ride",
        )
        _do_settle(ride)

        mock_debit.assert_called_once()
        self.assertEqual(mock_debit.call_args[1]["idempotency_key"], "ride:44")
        self.assertEqual(mock_debit.call_args[1]["vertical"], "rides")
        self.assertTrue(ride.paid_with_wallet)
        self.assertFalse(ride.cash_fallback)
        # payment_method unchanged on the happy path.
        self.assertEqual(ride.payment_method, "wallet")

    def test_serializer_exposes_cash_fallback_markers(self):
        """_serialize_ride surfaces the explicit-fallback markers so the rider can see why
        no wallet money moved; defaults are safe (False / "") on rows lacking the attrs."""
        from accounts.ride_views import _serialize_ride
        from accounts.models import RideRequest

        ride = MagicMock()
        ride.id = 50
        ride.kind = RideRequest.Kind.RIDE
        ride.status = "completed"
        ride.fare = Decimal("20.00")
        ride.distance_km = 3.0
        ride.payment_method = "cash"
        ride.paid_with_wallet = False
        ride.cash_fallback = True
        ride.cash_fallback_note = "pay cash"
        ride.driver = None
        ride.driver_id = None
        for attr in ("pickup_address", "dropoff_address", "recipient_name",
                     "package_note", "recipient_phone"):
            setattr(ride, attr, "")
        for attr in ("scheduled_for", "dispatched_at", "created_at", "accepted_at",
                     "arrived_at", "started_at", "completed_at", "cancelled_at"):
            setattr(ride, attr, None)
        ride.rider_driver_rating = None
        ride.driver_rider_rating = None

        data = _serialize_ride(ride)
        self.assertTrue(data["cash_fallback"])
        self.assertEqual(data["cash_fallback_note"], "pay cash")


# ═════════════════════════════════════════════════════════════════════════════
# D. Throttle wiring — loyalty_redeem + voucher_redeem scopes registered/exported
# ═════════════════════════════════════════════════════════════════════════════

class ThrottleWiringTests(SimpleTestCase):
    def test_loyalty_redeem_throttle_exists_with_scope(self):
        from accounts.throttles import LoyaltyRedeemThrottle
        self.assertEqual(LoyaltyRedeemThrottle.scope, "loyalty_redeem")

    def test_voucher_redeem_throttle_exists_with_exact_name_and_scope(self):
        # Imported by the other agent's accounts/views.py — name + scope must be exact.
        from accounts.throttles import VoucherRedeemThrottle
        self.assertEqual(VoucherRedeemThrottle.scope, "voucher_redeem")

    def test_loyalty_view_wires_the_throttle(self):
        from menu.views import CustomerLoyaltyRedeemView
        from accounts.throttles import LoyaltyRedeemThrottle
        self.assertIn(LoyaltyRedeemThrottle, CustomerLoyaltyRedeemView.throttle_classes)

    def test_both_rates_registered(self):
        from config.rest_framework import REST_FRAMEWORK
        rates = REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
        self.assertIn("loyalty_redeem", rates)
        self.assertIn("voucher_redeem", rates)
