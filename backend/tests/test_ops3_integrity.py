"""
OPS-3 backend tests — "integrity on flaky wifi".

Contracts covered:
  A — Order-placement idempotency
      - Same idempotency_key → same order returned, no stock decrement twice
      - Race path: IntegrityError on create → re-fetch winner, return 201
  B — Status-advance idempotency + lock
      - Replay "confirm" on CONFIRMED order → 200 + code=already_at_target
      - Advance to already-passed target → no regression, code=already_advanced
      - select_for_update called on the order queryset
      - Genuine invalid_transition still 400
  C — Wallet mark-paid idempotency
      - Already-PAID order → success, no second debit
      - Cache hit short-circuit (idempotency_key already in cache)
  D — OrderPayment DB backstop
      - IntegrityError on duplicate idempotency_key → existing row returned
  G — Throttle scoping
      - StaffOrderListThrottle keys on user.pk for authenticated staff
      - StaffOrderListThrottle falls back to IP for anonymous requests
      - WaiterCallThrottle keys on (schema, table_slug) when both present
      - WaiterCallThrottle falls back to IP when table_slug absent

House style: SimpleTestCase + MagicMock, no real DB.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, RequestFactory
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from menu.views import PlaceOrderView, OwnerOrderStatusUpdateView, OwnerOrderMarkPaidView, StaffOrderPaymentView
from menu.models import Order
from menu.throttles import StaffOrderListThrottle, WaiterCallThrottle
from accounts.models import User


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _owner(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.pk = 42
    u.id = 42
    u.effective_perm_manage_orders = MagicMock(return_value=True)
    u.get_full_name = lambda: "Owner"
    u.username = "owner"
    u.email = "owner@test.com"
    return u


def _staff(tenant_id=1, pk=99):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_STAFF
    u.tenant_id = tenant_id
    u.pk = pk
    u.id = pk
    u.effective_perm_manage_orders = MagicMock(return_value=True)
    u.get_full_name = lambda: "Staff"
    u.username = "staff"
    u.email = "staff@test.com"
    return u


def _tenant(tenant_id=1, schema="resto1"):
    t = SimpleNamespace(id=tenant_id, schema_name=schema)
    plan = SimpleNamespace(can_whatsapp_order=True, can_checkout=True)
    t.plan = plan
    return t


def _make_order(
    order_id=10,
    status_val=Order.Status.PENDING,
    fulfillment_type=Order.FulfillmentType.TABLE,
    payment_status=Order.PaymentStatus.UNPAID,
    total=Decimal("30.00"),
    wallet_amount_paid=Decimal("0"),
    customer_id=None,
    order_number="ORD-AAA",
    idempotency_key=None,
    is_paid=False,
    paid_at=None,
):
    order = MagicMock()
    order.id = order_id
    order.order_number = order_number
    order.status = status_val
    order.fulfillment_type = fulfillment_type
    order.payment_status = payment_status
    order.total = total
    order.delivery_fee = Decimal("0")
    order.tip_amount = Decimal("0")
    order.promotion_discount = Decimal("0")
    order.loyalty_discount = Decimal("0")
    order.wallet_amount_paid = wallet_amount_paid
    order.customer_id = customer_id
    order.table_label = "T1"
    order.table_slug = "t1"
    order.customer_name = "Alice"
    order.customer_note = ""
    order.owner_note = ""
    order.estimated_ready_minutes = None
    order.currency = "MAD"
    order.scheduled_for = None
    order.fired_course = 1
    order.idempotency_key = idempotency_key
    order.is_paid = is_paid
    order.paid_at = paid_at
    order.handled_by_user_id = None
    order.save = MagicMock()
    order.mark_paid = MagicMock()
    order.refresh_from_db = MagicMock()
    order.created_at = MagicMock()
    order.created_at.isoformat.return_value = "2026-06-13T10:00:00+00:00"
    order.updated_at = MagicMock()
    order.updated_at.isoformat.return_value = "2026-06-13T10:00:00+00:00"
    order.status_updated_at = MagicMock()
    order.status_updated_at.isoformat.return_value = "2026-06-13T10:00:00+00:00"
    order.points_earned = None
    order.redeemed_loyalty_points = None

    items_qs = MagicMock()
    items_qs.all.return_value = []
    order.items = items_qs

    payments_qs = MagicMock()
    payments_qs.all.return_value = []
    order.payments = payments_qs

    return order


# ═══════════════════════════════════════════════════════════════════════════════
# Contract A — Order-placement idempotency
# ═══════════════════════════════════════════════════════════════════════════════

class PlaceOrderIdempotencyTests(SimpleTestCase):
    """
    The view does a pre-check lookup and, if the key is new, creates the order
    and persists the key on it.  A race produces IntegrityError → re-fetch winner.
    """

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = PlaceOrderView.as_view()

    def _post(self, body, user=None, tenant=None):
        req = self.factory.post("/api/place-order/", body, format="json")
        if user:
            force_authenticate(req, user=user)
        req.tenant = tenant or _tenant()
        req.session = {}
        return req

    def _setup_profile_mock(self, mock_profile_qs):
        """Set up a valid profile mock on the profile queryset."""
        profile = MagicMock()
        profile.is_menu_temporarily_disabled = False
        profile.is_menu_published = True
        profile.capabilities = {}
        profile.lat = None
        profile.lng = None
        mock_profile_qs.filter.return_value.first.return_value = profile
        return profile

    # ── Replay returns same order, no stock decrement ─────────────────────────

    @patch("menu.views.Order.objects")
    @patch("menu.views.Profile.objects")
    def test_replay_same_key_returns_existing_order(self, mock_profile_qs, mock_order_qs):
        """If an Order with the given idempotency_key already exists, return it (201)."""
        self._setup_profile_mock(mock_profile_qs)

        existing = _make_order(
            order_id=77,
            order_number="ORD-XYZ",
            idempotency_key="test-key-1234",
            status_val=Order.Status.PENDING,
        )
        # Pre-check lookup: Order.objects.filter(idempotency_key=...).first() returns existing
        mock_order_qs.filter.return_value.first.return_value = existing

        req = self._post(
            {"idempotency_key": "test-key-1234", "items": [{"slug": "burger", "qty": 1}]},
        )
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["order_number"], "ORD-XYZ")
        self.assertTrue(resp.data.get("idempotent_replay"))

    @patch("menu.views.Order.objects")
    @patch("menu.views.Profile.objects")
    def test_replay_does_not_decrement_stock(self, mock_profile_qs, mock_order_qs):
        """Replay path returns early — the stock decrement code is never reached."""
        self._setup_profile_mock(mock_profile_qs)

        existing = _make_order(
            order_id=77,
            order_number="ORD-XYZ",
            idempotency_key="key-abc",
        )
        mock_order_qs.filter.return_value.first.return_value = existing

        req = self._post({"idempotency_key": "key-abc", "items": [{"slug": "pizza", "qty": 2}]})
        with patch("menu.views.Dish.objects") as mock_dish:
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["order_number"], "ORD-XYZ")
        # Stock was never touched: select_for_update not called on Dish
        mock_dish.select_for_update.assert_not_called()

    # ── Race path: IntegrityError on create → re-fetch ────────────────────────

    @patch("menu.views.transaction")
    @patch("menu.views.Profile.objects")
    @patch("menu.views.Order.objects")
    @patch("menu.views.OrderItem.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.DishOption.objects")
    @patch("menu.views.TableLink.objects")
    @patch("menu.views.Promotion.objects")
    @patch("menu.views.LoyaltyConfig.objects")
    @patch("menu.views._validate_scheduled_for", return_value=(None, None))
    @patch("menu.views._is_restaurant_currently_open", return_value=True)
    @patch("menu.views.OrderHandoffSerializer")
    @patch("menu.views.get_all_active_hh_rules", return_value=[])
    @patch("menu.views.effective_unit_price", return_value=(Decimal("10.00"), None))
    @patch("menu.views._generate_order_number", return_value="ORD-RACE")
    def test_integrity_error_race_refetches_winner(
        self, mock_gen, mock_eup, mock_hh, mock_ser, mock_open, mock_sched,
        mock_loyalty, mock_promo, mock_tablelink, mock_dish_opt, mock_dish,
        mock_oi, mock_order_qs, mock_profile_qs, mock_tx
    ):
        """IntegrityError on create (race) → re-fetch via idempotency_key → 201."""
        from django.db import IntegrityError

        class _Atomic:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        mock_tx.atomic.return_value = _Atomic()

        # Profile
        profile = MagicMock()
        profile.is_menu_temporarily_disabled = False
        profile.is_menu_published = True
        profile.capabilities = {}
        profile.lat = None
        profile.lng = None
        mock_profile_qs.filter.return_value.first.return_value = profile

        # Serializer validation
        mock_ser.return_value.is_valid.return_value = True
        mock_ser.return_value.validated_data = {
            "items": [{"slug": "burger", "qty": 1, "option_ids": []}],
            "fulfillment_type": "table",
            "table_slug": "",
            "table_label": "T1",
            "customer_name": "Test",
            "customer_phone": "",
            "customer_note": "",
        }

        # Dish lookup
        dish = MagicMock()
        dish.slug = "burger"
        dish.name = "Burger"
        dish.currency = "MAD"
        dish.stock_qty = None
        dish.combo_components.all.return_value = []
        dish.category = MagicMock()
        dish.category.course = 0
        mock_dish.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]
        mock_dish_opt.filter.return_value.select_related.return_value = []

        # No promos, no loyalty
        mock_promo.filter.return_value = []
        mock_loyalty.filter.return_value.first.return_value = None

        # Build the winner order
        winner = _make_order(order_id=55, order_number="ORD-RACE", idempotency_key="race-key")

        # Order.objects.filter calls:
        #  Call 1 (pre-check): Order.objects.filter(idempotency_key="race-key").first() → None
        #  Call 2 (race re-fetch): Order.objects.filter(idempotency_key="race-key").first() → winner
        _filter_none = MagicMock()
        _filter_none.first.return_value = None
        _filter_winner = MagicMock()
        _filter_winner.first.return_value = winner
        mock_order_qs.filter.side_effect = [_filter_none, _filter_winner]

        # Order.objects.create raises IntegrityError inside atomic block
        mock_order_qs.create.side_effect = IntegrityError("duplicate key")

        req = self._post({"idempotency_key": "race-key", "items": [{"slug": "burger", "qty": 1}]})
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["order_number"], "ORD-RACE")
        self.assertTrue(resp.data.get("idempotent_replay"))


# ═══════════════════════════════════════════════════════════════════════════════
# Contract B — Status-advance idempotency + lock
# ═══════════════════════════════════════════════════════════════════════════════

class StatusAdvanceIdempotencyTests(SimpleTestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerOrderStatusUpdateView.as_view()

        # Make transaction.atomic a passthrough (SimpleTestCase has no DB)
        class _Atomic:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        _tx_patcher = patch("menu.views.transaction")
        self._tx_mock = _tx_patcher.start()
        self.addCleanup(_tx_patcher.stop)
        self._tx_mock.atomic.return_value = _Atomic()

        # Default: _can_edit_tenant_order returns True
        _edit_patcher = patch("menu.views._can_edit_tenant_order", return_value=True)
        self._edit_mock = _edit_patcher.start()
        self.addCleanup(_edit_patcher.stop)

    def _patch(self, order_id=10, body=None, user=None):
        body = body or {}
        req = self.factory.patch(
            f"/api/owner/orders/{order_id}/status/",
            body,
            format="json",
        )
        force_authenticate(req, user=user or _owner())
        req.tenant = _tenant()
        return req

    # ── Already at target → 200 no-op ────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_already_at_target_returns_200_no_op(self, mock_order_qs):
        order = _make_order(status_val=Order.Status.CONFIRMED)
        om = MagicMock()
        om.select_for_update.return_value = om
        om.select_related.return_value = om
        om.filter.return_value = om
        om.first.return_value = order
        mock_order_qs.select_for_update.return_value = om
        mock_order_qs.select_related.return_value = om
        mock_order_qs.filter.return_value = om
        mock_order_qs.first.return_value = order

        req = self._patch(body={"status": "confirmed"})
        resp = self.view(req, order_id=10)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "confirmed")
        self.assertEqual(resp.data.get("code"), "already_at_target")
        # No save called — pure no-op
        order.save.assert_not_called()

    # ── Advance to already-past target → no regression ────────────────────────

    @patch("menu.views.Order.objects")
    def test_past_target_returns_already_advanced_code(self, mock_order_qs):
        """Order is PREPARING; trying to set it back to PENDING → already_advanced."""
        order = _make_order(status_val=Order.Status.PREPARING)
        om = MagicMock()
        om.select_for_update.return_value = om
        om.select_related.return_value = om
        om.filter.return_value = om
        om.first.return_value = order
        mock_order_qs.select_for_update.return_value = om
        mock_order_qs.select_related.return_value = om
        mock_order_qs.filter.return_value = om
        mock_order_qs.first.return_value = order

        req = self._patch(body={"status": "pending"})
        resp = self.view(req, order_id=10)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data.get("code"), "already_advanced")
        # Status must NOT regress
        self.assertEqual(resp.data["status"], "preparing")
        order.save.assert_not_called()

    # ── select_for_update is used ─────────────────────────────────────────────

    @patch("menu.views.timezone")
    @patch("menu.views._broadcast_order_change", return_value=None)
    @patch("menu.views._send_order_status_email", return_value=None)
    @patch("menu.views.Order.objects")
    def test_select_for_update_is_called(self, mock_order_qs, mock_email, mock_broadcast, mock_tz):
        """select_for_update() must be called on the Order queryset."""
        order = _make_order(status_val=Order.Status.PENDING)

        # Build the mock chain: select_for_update → select_related → filter → first
        om = MagicMock()
        om.select_for_update.return_value = om
        om.select_related.return_value = om
        om.filter.return_value = om
        om.first.return_value = order
        mock_order_qs.select_for_update.return_value = om
        mock_order_qs.select_related.return_value = om
        mock_order_qs.filter.return_value = om
        mock_order_qs.first.return_value = order

        mock_tz.now.return_value = MagicMock()

        req = self._patch(body={"status": "confirmed"})
        resp = self.view(req, order_id=10)

        # select_for_update must have been invoked somewhere in the chain
        # (either on mock_order_qs directly or on the om that mock_order_qs returned)
        self.assertTrue(
            mock_order_qs.select_for_update.called or om.select_for_update.called,
            "select_for_update was not called on the order queryset",
        )

    # ── Genuinely invalid transition still 400 ────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_invalid_transition_returns_400(self, mock_order_qs):
        """Transitioning to an unknown status value → 400 invalid_transition."""
        order = _make_order(status_val=Order.Status.PENDING)
        om = MagicMock()
        om.select_for_update.return_value = om
        om.select_related.return_value = om
        om.filter.return_value = om
        om.first.return_value = order
        mock_order_qs.select_for_update.return_value = om
        mock_order_qs.select_related.return_value = om
        mock_order_qs.filter.return_value = om
        mock_order_qs.first.return_value = order

        # "ready" is not reachable from PENDING → it's not reachable forward
        # through the transition graph from PENDING either, so it's a genuine
        # invalid_transition rather than "already_advanced".
        # PENDING allowed: {confirmed, cancelled}. BFS from "ready": ready→completed,
        # none of which is PENDING. So correctly returns 400.
        req = self._patch(body={"status": "ready"})
        resp = self.view(req, order_id=10)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data.get("code"), "invalid_transition")


# ═══════════════════════════════════════════════════════════════════════════════
# Contract C — Wallet mark-paid idempotency
# ═══════════════════════════════════════════════════════════════════════════════

class MarkPaidIdempotencyTests(SimpleTestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerOrderMarkPaidView.as_view()

        # Make transaction.atomic a passthrough
        class _Atomic:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        _tx_patcher = patch("menu.views.transaction")
        self._tx_mock = _tx_patcher.start()
        self.addCleanup(_tx_patcher.stop)
        self._tx_mock.atomic.return_value = _Atomic()

        # Default: access allowed
        _edit_patcher = patch("menu.views._can_edit_tenant_order", return_value=True)
        self._edit_mock = _edit_patcher.start()
        self.addCleanup(_edit_patcher.stop)

    def _post(self, order_id=10, body=None, user=None):
        body = body or {}
        req = self.factory.post(
            f"/api/owner/orders/{order_id}/mark-paid/",
            body,
            format="json",
        )
        force_authenticate(req, user=user or _owner())
        req.tenant = _tenant()
        return req

    # ── Already PAID → success, no second debit ───────────────────────────────

    @patch("menu.views.cache")
    @patch("menu.views._broadcast_order_change", return_value=None)
    @patch("menu.views.Order.objects")
    def test_already_paid_returns_success_no_debit(self, mock_order_qs, mock_broadcast, mock_cache):
        """An already-PAID order returns 200 success without calling mark_paid again."""
        paid_order = _make_order(
            payment_status=Order.PaymentStatus.PAID,
            is_paid=True,
        )
        paid_order.is_paid = True

        om = MagicMock()
        om.select_for_update.return_value = om
        om.filter.return_value = om
        om.first.return_value = paid_order
        mock_order_qs.select_for_update.return_value = om
        mock_order_qs.filter.return_value = om
        mock_order_qs.first.return_value = paid_order

        mock_cache.get.return_value = None  # no cache hit

        req = self._post(body={"idempotency_key": "settle-key-1"})
        resp = self.view(req, order_id=10)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get("already_paid"))
        paid_order.mark_paid.assert_not_called()

    # ── Cache-hit short-circuit ───────────────────────────────────────────────

    @patch("menu.views.cache")
    @patch("menu.views.Order.objects")
    def test_cache_hit_short_circuits(self, mock_order_qs, mock_cache):
        """If the cache already has this idempotency_key, return success without locking."""
        order = _make_order(
            payment_status=Order.PaymentStatus.PAID,
            is_paid=True,
        )
        mock_order_qs.filter.return_value.first.return_value = order
        mock_cache.get.return_value = True  # cache hit

        req = self._post(body={"idempotency_key": "cached-key"})
        resp = self.view(req, order_id=10)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get("idempotent_replay"))
        # select_for_update was NOT called (cache hit returned early)
        mock_order_qs.select_for_update.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# Contract D — OrderPayment DB backstop (IntegrityError on duplicate key)
# ═══════════════════════════════════════════════════════════════════════════════

class OrderPaymentDbBackstopTests(SimpleTestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffOrderPaymentView.as_view()

        # Make transaction.atomic a passthrough
        class _Atomic:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        _tx_patcher = patch("menu.views.transaction")
        self._tx_mock = _tx_patcher.start()
        self.addCleanup(_tx_patcher.stop)
        self._tx_mock.atomic.return_value = _Atomic()

        _edit_patcher = patch("menu.views._can_edit_tenant_order", return_value=True)
        self._edit_mock = _edit_patcher.start()
        self.addCleanup(_edit_patcher.stop)

        _access_patcher = patch("menu.views._can_access_order", return_value=True)
        self._access_mock = _access_patcher.start()
        self.addCleanup(_access_patcher.stop)

    def _post(self, order_id=10, body=None, user=None):
        body = body or {}
        req = self.factory.post(
            f"/api/staff/orders/{order_id}/payments/",
            body,
            format="json",
        )
        force_authenticate(req, user=user or _staff())
        req.tenant = _tenant()
        return req

    @patch("menu.views.cache")
    @patch("menu.views._broadcast_order_change", return_value=None)
    @patch("menu.views.OrderPayment.objects")
    @patch("menu.views.Order.objects")
    def test_integrity_error_returns_existing_row_payload(
        self, mock_order_qs, mock_op_qs, mock_broadcast, mock_cache
    ):
        """IntegrityError on OrderPayment.create → re-fetch via idempotency_key → 201."""
        from django.db import IntegrityError

        order = _make_order(
            payment_status=Order.PaymentStatus.UNPAID,
            total=Decimal("30.00"),
        )
        order.payments.all.return_value = []

        om = MagicMock()
        om.select_for_update.return_value = om
        om.prefetch_related.return_value = om
        om.filter.return_value = om
        om.first.return_value = order
        # For the reload after atomic block
        om.get.return_value = order
        mock_order_qs.select_for_update.return_value = om
        mock_order_qs.prefetch_related.return_value = om
        mock_order_qs.filter.return_value = om
        mock_order_qs.first.return_value = order
        mock_order_qs.get.return_value = order

        mock_cache.get.return_value = None  # no cache hit

        # OrderPayment.create raises IntegrityError (duplicate idempotency_key)
        from menu.models import OrderPayment
        existing_payment = MagicMock(spec=OrderPayment)
        existing_payment.order_id = order.id
        existing_payment.idempotency_key = "pay-key-dup"

        mock_op_qs.create.side_effect = IntegrityError("unique constraint")
        # Re-fetch the existing payment by idempotency_key
        mock_op_qs.filter.return_value.first.return_value = existing_payment

        req = self._post(
            body={"method": "cash", "amount": "30.00", "idempotency_key": "pay-key-dup"}
        )
        resp = self.view(req, order_id=10)

        # Should return 201 with the replayed order payload (not 503)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    @patch("menu.views.cache")
    @patch("menu.views._broadcast_order_change", return_value=None)
    @patch("menu.views.OrderPayment.objects")
    @patch("menu.views.Order.objects")
    def test_idempotency_key_persisted_on_payment_row(
        self, mock_order_qs, mock_op_qs, mock_broadcast, mock_cache
    ):
        """OrderPayment.create is called with the idempotency_key field."""
        order = _make_order(
            payment_status=Order.PaymentStatus.UNPAID,
            total=Decimal("20.00"),
        )
        order.payments.all.return_value = []
        order.mark_paid = MagicMock()

        om = MagicMock()
        om.select_for_update.return_value = om
        om.prefetch_related.return_value = om
        om.filter.return_value = om
        om.first.return_value = order
        om.get.return_value = order
        mock_order_qs.select_for_update.return_value = om
        mock_order_qs.prefetch_related.return_value = om
        mock_order_qs.filter.return_value = om
        mock_order_qs.first.return_value = order
        mock_order_qs.get.return_value = order

        mock_cache.get.return_value = None

        payment_mock = MagicMock()
        payment_mock.id = 55
        mock_op_qs.create.return_value = payment_mock

        req = self._post(
            body={"method": "cash", "amount": "20.00", "idempotency_key": "cash-idem-key"}
        )
        resp = self.view(req, order_id=10)

        # Verify that create was called with idempotency_key
        create_kwargs = mock_op_qs.create.call_args[1]
        self.assertEqual(create_kwargs.get("idempotency_key"), "cash-idem-key")


# ═══════════════════════════════════════════════════════════════════════════════
# Contract G — Throttle scoping
# ═══════════════════════════════════════════════════════════════════════════════

class ThrottleScopingTests(SimpleTestCase):

    def _make_request(self, user=None, body=None):
        factory = RequestFactory()
        req = factory.post("/", body or {}, content_type="application/json")
        if user:
            req.user = user
        return req

    # ── StaffOrderListThrottle ─────────────────────────────────────────────────

    def test_staff_throttle_keys_on_user_pk(self):
        """Authenticated staff → cache key contains user pk, not IP."""
        throttle = StaffOrderListThrottle()
        throttle.cache_format = "throttle_%(scope)s_%(ident)s"
        user = _staff(pk=77)
        req = self._make_request(user=user)
        req.META["REMOTE_ADDR"] = "1.2.3.4"

        key = throttle.get_cache_key(req, view=None)

        self.assertIn("user:77", key)
        self.assertNotIn("1.2.3.4", key)

    def test_staff_throttle_falls_back_to_ip_for_anon(self):
        """Anonymous request → cache key is IP-based (standard fallback)."""
        throttle = StaffOrderListThrottle()
        throttle.cache_format = "throttle_%(scope)s_%(ident)s"

        anon = MagicMock()
        anon.is_authenticated = False
        req = self._make_request(user=anon)
        req.META["REMOTE_ADDR"] = "10.0.0.1"

        key = throttle.get_cache_key(req, view=None)

        self.assertNotIn("user:", key)

    def test_different_users_get_different_keys(self):
        """Two different staff users must get different throttle keys."""
        throttle = StaffOrderListThrottle()
        throttle.cache_format = "throttle_%(scope)s_%(ident)s"

        user_a = _staff(pk=10)
        user_b = _staff(pk=20)

        req_a = self._make_request(user=user_a)
        req_a.META["REMOTE_ADDR"] = "192.168.1.1"
        req_b = self._make_request(user=user_b)
        req_b.META["REMOTE_ADDR"] = "192.168.1.1"  # same IP, different users

        key_a = throttle.get_cache_key(req_a, view=None)
        key_b = throttle.get_cache_key(req_b, view=None)

        self.assertNotEqual(key_a, key_b)

    # ── WaiterCallThrottle ─────────────────────────────────────────────────────

    def test_waitercall_throttle_keys_on_tenant_and_table(self):
        """table_slug + tenant schema → key contains both."""
        throttle = WaiterCallThrottle()
        throttle.cache_format = "throttle_%(scope)s_%(ident)s"

        req = self._make_request(body={"table": "t1"})
        req.META["REMOTE_ADDR"] = "1.2.3.4"
        req.data = {"table": "t1"}

        schema_tenant = SimpleNamespace(schema_name="schema_resto")

        with patch("menu.throttles.connection") as mock_conn:
            mock_conn.tenant = schema_tenant
            key = throttle.get_cache_key(req, view=None)

        self.assertIn("tbl:", key)
        self.assertIn("schema_resto", key)
        self.assertIn("t1", key)

    def test_waitercall_throttle_different_tables_get_different_keys(self):
        """table1 and table2 in the same restaurant get separate throttle buckets."""
        throttle = WaiterCallThrottle()
        throttle.cache_format = "throttle_%(scope)s_%(ident)s"

        schema_tenant = SimpleNamespace(schema_name="schema_abc")

        req1 = self._make_request()
        req1.META["REMOTE_ADDR"] = "1.2.3.4"
        req1.data = {"table": "table-1"}

        req2 = self._make_request()
        req2.META["REMOTE_ADDR"] = "1.2.3.4"  # same NAT IP
        req2.data = {"table": "table-2"}

        with patch("menu.throttles.connection") as mock_conn:
            mock_conn.tenant = schema_tenant
            key1 = throttle.get_cache_key(req1, view=None)
            key2 = throttle.get_cache_key(req2, view=None)

        self.assertNotEqual(key1, key2)

    def test_waitercall_throttle_falls_back_to_ip_without_table_slug(self):
        """No table_slug → fall back to IP-based key."""
        throttle = WaiterCallThrottle()
        throttle.cache_format = "throttle_%(scope)s_%(ident)s"

        req = self._make_request()
        req.META["REMOTE_ADDR"] = "5.6.7.8"
        req.data = {}

        schema_tenant = SimpleNamespace(schema_name="schema_abc")
        with patch("menu.throttles.connection") as mock_conn:
            mock_conn.tenant = schema_tenant
            key = throttle.get_cache_key(req, view=None)

        # No tbl: prefix — fell back to IP
        self.assertNotIn("tbl:", key)
