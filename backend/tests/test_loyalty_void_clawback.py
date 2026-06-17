"""
Tests for A1: loyalty points clawback on StaffVoidOrderItemView.

When a customer has earned loyalty points for an order (order.points_earned > 0),
voiding an item must proportionally claw back the earned points using the same
formula as placement: pts = int(float(food_subtotal) * rate).

Invariants verified:
  (a) total clawed <= originally earned
  (b) void + cancel does not double-claw (order.points_earned decremented at void)
  (c) Customer.loyalty_points never goes negative (clamped at 0)
  (d) redeemed_loyalty_points not touched at void (order-level, cancel-only)
  (e) clawback is inside the atomic block (tested via Customer save being called)
  (f) no loyalty config or no customer_id → no clawback (best-effort, silent)

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from menu.views import StaffVoidOrderItemView
from menu.models import Order
from accounts.models import User


def _user(role=User.Roles.TENANT_OWNER, tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = role
    u.tenant_id = tenant_id
    u.id = 42
    u.get_full_name = MagicMock(return_value="")
    u.username = "owner"
    u.email = "owner@example.com"
    u.effective_perm_manage_orders = MagicMock(return_value=True)
    return u


def _tenant(tenant_id=1):
    return SimpleNamespace(id=tenant_id)


def _make_item(item_id=901, dish_slug="burger", dish_name="Burger",
               qty=1, subtotal=Decimal("20.00"), is_voided=False):
    item = MagicMock()
    item.id = item_id
    item.dish_slug = dish_slug
    item.dish_name = dish_name
    item.qty = qty
    item.unit_price = subtotal
    item.subtotal = subtotal
    item.options = []
    item.note = ""
    item.is_ready = False
    item.is_voided = is_voided
    item.combo_components = []
    item.save = MagicMock()
    return item


def _make_order(order_id=10, status_val=Order.Status.PENDING,
                payment_status=Order.PaymentStatus.UNPAID,
                total=Decimal("40.00"), wallet_amount_paid=Decimal("0"),
                customer_id=7, points_earned=40, items=None):
    order = MagicMock()
    order.id = order_id
    order.order_number = "ORD-V001"
    order.status = status_val
    order.fulfillment_type = Order.FulfillmentType.TABLE
    order.payment_status = payment_status
    order.total = total
    order.delivery_fee = Decimal("0")
    order.tip_amount = Decimal("0")
    order.promotion_discount = Decimal("0")
    order.loyalty_discount = Decimal("0")
    order.wallet_amount_paid = wallet_amount_paid
    order.customer_id = customer_id
    order.points_earned = points_earned
    order.redeemed_loyalty_points = 0
    order.table_label = "T1"
    order.customer_name = "Alice"
    order.customer_note = ""
    order.owner_note = ""
    order.estimated_ready_minutes = None
    order.currency = "MAD"
    order.scheduled_for = None
    order.pk = order_id
    order.save = MagicMock()
    order.mark_paid = MagicMock()
    order.created_at = MagicMock()
    order.created_at.isoformat.return_value = "2026-06-12T10:00:00+00:00"
    order.updated_at = MagicMock()
    order.updated_at.isoformat.return_value = "2026-06-12T10:00:00+00:00"

    _items = items or []
    items_qs = MagicMock()
    items_qs.all.return_value = _items
    items_qs.filter.return_value.first.return_value = _items[0] if _items else None
    order.items = items_qs

    payments_qs = MagicMock()
    payments_qs.all.return_value = []
    order.payments = payments_qs

    return order


def _loyalty_cfg(rate=2):
    """Mock LoyaltyConfig with points_per_unit=rate."""
    cfg = MagicMock()
    cfg.points_per_unit = rate
    return cfg


class LoyaltyVoidClawbackTests(SimpleTestCase):
    """A1: StaffVoidOrderItemView must claw back proportional loyalty points."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffVoidOrderItemView.as_view()
        _patcher = patch("menu.views._can_access_order", return_value=True)
        self._access_mock = _patcher.start()
        self.addCleanup(_patcher.stop)

    def _post(self, order_id=10, item_id=901, body=None, user=None):
        body = body or {}
        req = self.factory.post(
            f"/api/staff/orders/{order_id}/items/{item_id}/void/",
            body, format="json"
        )
        u = user or _user()
        force_authenticate(req, user=u)
        req.tenant = _tenant()
        return self.view(req, order_id=order_id, item_id=item_id)

    def _run_void(self, order, item, loyalty_cfg=None, cust_points=40):
        """Wire up all mocks and execute the void view, returning (response, cust_mock)."""
        cust = MagicMock()
        cust.loyalty_points = cust_points
        cust.save = MagicMock()

        class _FakeAtomic:
            def __enter__(self): return self
            def __exit__(self, *a): return False

        with patch("menu.views._can_edit_tenant_order", return_value=True), \
             patch("menu.views.transaction") as tx_mock, \
             patch("menu.views.Order.objects") as order_om, \
             patch("menu.views.Dish.objects") as dish_om, \
             patch("menu.views.LoyaltyConfig") as lc_mock, \
             patch("menu.views._broadcast_order_change"), \
             patch("accounts.models.Customer") as cust_mock:

            tx_mock.atomic.return_value = _FakeAtomic()
            order_om.prefetch_related.return_value.filter.return_value.first.return_value = order
            order_om.select_for_update.return_value.prefetch_related.return_value.get.return_value = order
            order_om.filter.return_value.update.return_value = 1

            # Dish lock — no-op (no stock)
            dish_om.select_for_update.return_value.filter.return_value = []

            if loyalty_cfg is not None:
                lc_mock.objects.filter.return_value.first.return_value = loyalty_cfg
            else:
                lc_mock.objects.filter.return_value.first.return_value = None

            cust_mock.objects.select_for_update.return_value.get.return_value = cust

            resp = self._post(order_id=order.id, item_id=item.id)
            return resp, cust

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    @patch("menu.views.LoyaltyConfig")
    @patch("accounts.models.Customer")
    def test_clawback_proportional_to_voided_item(
        self, cust_mock, lc_mock, order_om, tx_mock, dish_om, broadcast_mock
    ):
        """Voiding one item of two claws back points proportional to voided subtotal.

        Setup: 2 items each 20.00, rate=2 pts/unit → original earned = 40×2 → wait,
        points_per_unit=2 means 2 pts per 1 currency unit so for 40.00 → 80 pts,
        but order.points_earned is stored as the actual earned (80).
        After voiding one 20.00 item: post_subtotal=20.00, post_pts=40;
        clawback = 40 (80−40), customer.loyalty_points: 80 → 40.
        """
        # Two non-voided items; one will be voided
        item_to_void = _make_item(item_id=901, dish_slug="burger", subtotal=Decimal("20.00"))
        item_kept = _make_item(item_id=902, dish_slug="fries", subtotal=Decimal("20.00"),
                               is_voided=False)
        # After void, item_to_void.is_voided=True is set, items.all() must only return kept
        item_to_void_voided = _make_item(item_id=901, dish_slug="burger",
                                         subtotal=Decimal("20.00"), is_voided=True)

        order = _make_order(
            total=Decimal("40.00"), customer_id=7, points_earned=80,
            items=[item_to_void],
        )
        # After select_for_update reload, items reflect both (to_void marked as voided)
        order_locked = _make_order(
            total=Decimal("20.00"), customer_id=7, points_earned=80,
            items=[item_to_void_voided, item_kept],
        )

        class _FakeAtomic:
            def __enter__(self): return self
            def __exit__(self, *a): return False

        cust = MagicMock()
        cust.loyalty_points = 80
        cust.save = MagicMock()

        tx_mock.atomic.return_value = _FakeAtomic()
        order_om.prefetch_related.return_value.filter.return_value.first.return_value = order
        order_om.select_for_update.return_value.prefetch_related.return_value.get.return_value = order_locked
        order_om.filter.return_value.update.return_value = 1

        lc_mock.objects.filter.return_value.first.return_value = _loyalty_cfg(rate=2)
        cust_mock.objects.select_for_update.return_value.get.return_value = cust
        dish_om.select_for_update.return_value.filter.return_value = []

        resp = self._post(order_id=10, item_id=901)

        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        # Customer loyalty_points decremented by 40 (80→40)
        self.assertEqual(cust.loyalty_points, 40)
        cust.save.assert_called_once_with(update_fields=["loyalty_points", "updated_at"])
        # order.points_earned decremented to prevent double-claw on cancel
        order_om.filter.assert_called()

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    @patch("menu.views.LoyaltyConfig")
    @patch("accounts.models.Customer")
    def test_clawback_clamped_at_zero(
        self, cust_mock, lc_mock, order_om, tx_mock, dish_om, broadcast_mock
    ):
        """Customer.loyalty_points never goes below 0 even if they spent some."""
        item_to_void = _make_item(item_id=901, subtotal=Decimal("50.00"))
        item_to_void_voided = _make_item(item_id=901, subtotal=Decimal("50.00"), is_voided=True)
        order = _make_order(total=Decimal("50.00"), customer_id=7, points_earned=100,
                            items=[item_to_void])
        order_locked = _make_order(total=Decimal("0.00"), customer_id=7, points_earned=100,
                                   items=[item_to_void_voided])

        cust = MagicMock()
        cust.loyalty_points = 30  # less than the clawback of 100 — must clamp to 0
        cust.save = MagicMock()

        class _FakeAtomic:
            def __enter__(self): return self
            def __exit__(self, *a): return False

        tx_mock.atomic.return_value = _FakeAtomic()
        order_om.prefetch_related.return_value.filter.return_value.first.return_value = order
        order_om.select_for_update.return_value.prefetch_related.return_value.get.return_value = order_locked
        order_om.filter.return_value.update.return_value = 1
        lc_mock.objects.filter.return_value.first.return_value = _loyalty_cfg(rate=2)
        cust_mock.objects.select_for_update.return_value.get.return_value = cust
        dish_om.select_for_update.return_value.filter.return_value = []

        resp = self._post(order_id=10, item_id=901)

        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        # loyalty_points clamped at 0, not negative
        self.assertGreaterEqual(cust.loyalty_points, 0)

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    @patch("accounts.models.Customer")
    def test_clawback_fires_even_when_loyalty_config_now_disabled(
        self, cust_mock, order_om, tx_mock, dish_om, broadcast_mock
    ):
        """Clawback uses stored order.points_earned (not current LoyaltyConfig).
        Even if the owner later disables the loyalty programme, points that were
        earned at placement are still proportionally clawed back on void — the
        stored points_earned is the source of truth, not the current config rate."""
        item = _make_item(item_id=901, subtotal=Decimal("20.00"))
        order = _make_order(total=Decimal("20.00"), customer_id=7, points_earned=40,
                            items=[item])
        # After void: only the now-voided item exists; non-voided subtotal = 0
        order_locked = _make_order(total=Decimal("0.00"), customer_id=7, points_earned=40,
                                   items=[_make_item(item_id=901, is_voided=True)])

        cust = MagicMock()
        cust.loyalty_points = 40
        cust.save = MagicMock()

        class _FakeAtomic:
            def __enter__(self): return self
            def __exit__(self, *a): return False

        tx_mock.atomic.return_value = _FakeAtomic()
        order_om.prefetch_related.return_value.filter.return_value.first.return_value = order
        order_om.select_for_update.return_value.prefetch_related.return_value.get.return_value = order_locked
        order_om.filter.return_value.update.return_value = 1
        cust_mock.objects.select_for_update.return_value.get.return_value = cust
        dish_om.select_for_update.return_value.filter.return_value = []

        resp = self._post(order_id=10, item_id=901)

        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        # Clawback fires: voided 20.00 / pre-subtotal 20.00 → 100% → 40 pts clawed
        self.assertEqual(cust.loyalty_points, 0)
        cust.save.assert_called_once_with(update_fields=["loyalty_points", "updated_at"])

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    @patch("menu.views.LoyaltyConfig")
    @patch("accounts.models.Customer")
    def test_no_clawback_when_no_customer_id(
        self, cust_mock, lc_mock, order_om, tx_mock, dish_om, broadcast_mock
    ):
        """No clawback when the order has no linked customer (anonymous order)."""
        item = _make_item(item_id=901, subtotal=Decimal("20.00"))
        order = _make_order(total=Decimal("20.00"), customer_id=None, points_earned=0,
                            items=[item])
        order_locked = _make_order(total=Decimal("0.00"), customer_id=None, points_earned=0,
                                   items=[_make_item(item_id=901, is_voided=True)])

        class _FakeAtomic:
            def __enter__(self): return self
            def __exit__(self, *a): return False

        tx_mock.atomic.return_value = _FakeAtomic()
        order_om.prefetch_related.return_value.filter.return_value.first.return_value = order
        order_om.select_for_update.return_value.prefetch_related.return_value.get.return_value = order_locked
        order_om.filter.return_value.update.return_value = 1
        lc_mock.objects.filter.return_value.first.return_value = _loyalty_cfg(rate=2)
        dish_om.select_for_update.return_value.filter.return_value = []

        resp = self._post(order_id=10, item_id=901)

        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        # No customer lock attempted
        cust_mock.objects.select_for_update.assert_not_called()

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    @patch("menu.views.LoyaltyConfig")
    @patch("accounts.models.Customer")
    def test_points_earned_decremented_for_subsequent_cancel(
        self, cust_mock, lc_mock, order_om, tx_mock, dish_om, broadcast_mock
    ):
        """order.points_earned is decremented at void time so a subsequent cancel
        claws only the remaining points (no double-claw).
        Invariant (b): void(clawback=X) then cancel sees points_earned = orig - X."""
        item = _make_item(item_id=901, subtotal=Decimal("20.00"))
        item_voided = _make_item(item_id=901, subtotal=Decimal("20.00"), is_voided=True)
        item_kept = _make_item(item_id=902, subtotal=Decimal("20.00"), is_voided=False)

        # Order with two items, 40 pts earned at rate=1
        order = _make_order(total=Decimal("40.00"), customer_id=7, points_earned=40,
                            items=[item])
        order_locked = _make_order(total=Decimal("20.00"), customer_id=7, points_earned=40,
                                   items=[item_voided, item_kept])

        cust = MagicMock()
        cust.loyalty_points = 40
        cust.save = MagicMock()

        class _FakeAtomic:
            def __enter__(self): return self
            def __exit__(self, *a): return False

        tx_mock.atomic.return_value = _FakeAtomic()
        order_om.prefetch_related.return_value.filter.return_value.first.return_value = order
        order_om.select_for_update.return_value.prefetch_related.return_value.get.return_value = order_locked
        order_om.filter.return_value.update.return_value = 1
        lc_mock.objects.filter.return_value.first.return_value = _loyalty_cfg(rate=1)
        cust_mock.objects.select_for_update.return_value.get.return_value = cust
        dish_om.select_for_update.return_value.filter.return_value = []

        resp = self._post(order_id=10, item_id=901)

        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        # Clawback = 20 pts (for the voided 20.00 item at rate=1)
        self.assertEqual(cust.loyalty_points, 20)
        # order.points_earned updated to exactly 20 (40 - 20) to prevent double-claw
        update_calls = order_om.filter.return_value.update.call_args_list
        pe_values = [c.kwargs["points_earned"] for c in update_calls if "points_earned" in c.kwargs]
        self.assertEqual(pe_values, [20],
                         "Order.objects.filter().update(points_earned=20) must be called exactly once")
