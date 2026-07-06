"""
Tests for the R2 dine-in item management endpoints:

  POST /api/staff/orders/<order_id>/items/        — StaffAppendOrderItemsView
  POST /api/staff/orders/<order_id>/items/<item_id>/void/  — StaffVoidOrderItemView
  POST /api/staff/orders/<order_id>/items/<item_id>/comp/  — StaffCompOrderItemView (V3)

All tests are unit-level (SimpleTestCase + mocks — no real DB).

House-style rules:
  - Only update_fields kwarg saves are accepted (checked via mock assertions).
  - All DB calls are patched; no real DB connection is used.
  - Wallet-service interactions are fully mocked.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from menu.views import StaffAppendOrderItemsView, StaffVoidOrderItemView, StaffCompOrderItemView
from menu.models import Order
from accounts.models import User


# ── Shared helpers ────────────────────────────────────────────────────────────

def _user(role=User.Roles.TENANT_STAFF, tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = role
    u.tenant_id = tenant_id
    u.effective_perm_manage_orders = MagicMock(return_value=True)
    return u


def _tenant(tenant_id=1):
    return SimpleNamespace(id=tenant_id)


def _make_item(
    item_id=901,
    dish_name="Burger",
    dish_slug="burger",
    qty=1,
    unit_price=Decimal("12.50"),
    subtotal=Decimal("12.50"),
    options=None,
    note="",
    is_ready=False,
    is_voided=False,
    is_comped=False,
):
    item = MagicMock()
    item.id = item_id
    item.dish_name = dish_name
    item.dish_slug = dish_slug
    item.qty = qty
    item.unit_price = unit_price
    item.subtotal = subtotal
    item.options = options or []
    item.note = note
    item.is_ready = is_ready
    item.is_voided = is_voided
    # V3: _recompute_order_totals now excludes comped items too — default False
    # so every existing void/append test (which never sets this) keeps summing
    # the item into the total exactly as before.
    item.is_comped = is_comped
    item.save = MagicMock()
    return item


def _make_order(
    order_id=10,
    status_val=Order.Status.PENDING,
    fulfillment_type=Order.FulfillmentType.TABLE,
    payment_status=Order.PaymentStatus.UNPAID,
    total=Decimal("12.50"),
    delivery_fee=Decimal("0"),
    tip_amount=Decimal("0"),
    promotion_discount=Decimal("0"),
    loyalty_discount=Decimal("0"),
    wallet_amount_paid=Decimal("0"),
    customer_id=None,
    items=None,
):
    order = MagicMock()
    order.id = order_id
    order.order_number = "ORD-001"
    order.status = status_val
    order.fulfillment_type = fulfillment_type
    order.payment_status = payment_status
    order.total = total
    order.delivery_fee = delivery_fee
    order.tip_amount = tip_amount
    order.promotion_discount = promotion_discount
    order.loyalty_discount = loyalty_discount
    order.wallet_amount_paid = wallet_amount_paid
    order.customer_id = customer_id
    order.table_label = "T1"
    order.customer_name = "Alice"
    order.customer_note = ""
    order.owner_note = ""
    order.estimated_ready_minutes = None
    order.currency = "MAD"
    order.scheduled_for = None
    order.save = MagicMock()
    order.created_at = MagicMock()
    order.created_at.isoformat.return_value = "2026-06-11T10:00:00+00:00"
    order.updated_at = MagicMock()
    order.updated_at.isoformat.return_value = "2026-06-11T10:00:00+00:00"

    _items = items or []
    items_qs = MagicMock()
    items_qs.all.return_value = _items
    items_qs.filter.return_value.first.return_value = _items[0] if _items else None
    order.items = items_qs

    # R4: payments ledger (empty by default for existing tests — no split-bill rows)
    payments_qs = MagicMock()
    payments_qs.all.return_value = []
    order.payments = payments_qs

    return order


def _make_dish(slug="burger", name="Burger", price=Decimal("12.50"), stock_qty=None,
               is_published=True, is_available=True, pk=1):
    d = MagicMock()
    d.pk = pk
    d.slug = slug
    d.name = name
    d.price = price
    d.stock_qty = stock_qty
    d.is_published = is_published
    d.is_available = is_available
    d.currency = "MAD"
    return d


# ═══════════════════════════════════════════════════════════════════════════════
# StaffAppendOrderItemsView — POST /api/staff/orders/<order_id>/items/
# ═══════════════════════════════════════════════════════════════════════════════

class StaffAppendOrderItemsViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffAppendOrderItemsView.as_view()
        # Patch _can_access_order so unit tests don't hit the DB for section lookups.
        _patcher = patch("menu.views._can_access_order", return_value=True)
        self._access_mock = _patcher.start()
        self.addCleanup(_patcher.stop)

    def _post(self, order_id=10, body=None, user=None):
        body = body or {"items": [{"dish_slug": "burger", "qty": 1}]}
        req = self.factory.post(f"/api/staff/orders/{order_id}/items/", body, format="json")
        u = user or _user()
        force_authenticate(req, user=u)
        req.tenant = _tenant()
        return self.view(req, order_id=order_id)

    # ── Auth / permission ─────────────────────────────────────────────────────

    def test_unauthenticated_is_403(self):
        req = self.factory.post("/api/staff/orders/10/items/", {}, format="json")
        # no force_authenticate
        with patch("menu.views.Order.objects") as om:
            om.prefetch_related.return_value.filter.return_value.first.return_value = None
            resp = self.view(req, order_id=10)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("menu.views._can_edit_tenant_order", return_value=False)
    def test_no_permission_403(self, _mock):
        req = self.factory.post("/api/staff/orders/10/items/", {}, format="json")
        force_authenticate(req, user=_user())
        req.tenant = _tenant()
        resp = self.view(req, order_id=10)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Guards ────────────────────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_order_not_found_404(self, om):
        om.prefetch_related.return_value.filter.return_value.first.return_value = None
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "not_found")

    @patch("menu.views.Order.objects")
    def test_not_table_order_409(self, om):
        order = _make_order(fulfillment_type=Order.FulfillmentType.PICKUP)
        om.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "not_table")

    @patch("menu.views.Order.objects")
    def test_bad_status_409(self, om):
        order = _make_order(status_val=Order.Status.COMPLETED)
        om.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "bad_status")

    @patch("menu.views.Order.objects")
    def test_already_paid_409(self, om):
        order = _make_order(payment_status=Order.PaymentStatus.PAID)
        om.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_paid")

    @patch("menu.views.Order.objects")
    def test_empty_items_400(self, om):
        order = _make_order()
        om.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post(body={"items": []})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Happy path: append + recompute totals + stock decremented ─────────────

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.OrderItem.objects")
    @patch("menu.views.DishOption.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_happy_path_appends_item_recomputes_total(
        self, order_om, tx_mock, dish_om, option_om, item_om, broadcast_mock
    ):
        dish = _make_dish(slug="burger", price=Decimal("10.00"))

        # First call: find the order; second call (inside atomic): reload
        existing_item = _make_item(subtotal=Decimal("20.00"), is_voided=False)
        new_item = _make_item(item_id=902, dish_slug="burger", qty=2,
                              unit_price=Decimal("10.00"), subtotal=Decimal("20.00"))

        first_order = _make_order(items=[existing_item])
        second_order = _make_order(
            total=Decimal("20.00"),
            items=[existing_item, new_item],
        )

        order_om.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        order_om.prefetch_related.return_value.get.return_value = second_order

        # transaction.atomic() as context manager
        tx_mock.atomic.return_value.__enter__ = MagicMock(return_value=None)
        tx_mock.atomic.return_value.__exit__ = MagicMock(return_value=False)

        dish_om.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]
        # All dishes are now locked via select_for_update().filter(pk__in=...)
        dish_om.select_for_update.return_value.filter.return_value = [dish]
        option_om.filter.return_value = []
        item_om.create = MagicMock()

        resp = self._post(body={"items": [{"dish_slug": "burger", "qty": 2}]})

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # Item was created
        item_om.create.assert_called_once()
        call_kwargs = item_om.create.call_args[1]
        self.assertEqual(call_kwargs["dish_slug"], "burger")
        self.assertEqual(call_kwargs["qty"], 2)
        self.assertFalse(call_kwargs["is_ready"])
        # Total save used update_fields
        second_order.save.assert_called_once_with(update_fields=["total", "updated_at"])
        # Broadcast fired
        broadcast_mock.assert_called_once()

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.OrderItem.objects")
    @patch("menu.views.DishOption.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_out_of_stock_rolls_back_409(
        self, order_om, tx_mock, dish_om, option_om, item_om, broadcast_mock
    ):
        """An out-of-stock dish must return 409 and must not create any OrderItem.

        We mock transaction.atomic as a passthrough context manager so the view's
        body executes, then supply a locked dish with stock_qty=0 so the _OutOfStock
        exception is raised and caught before any OrderItem.create call.
        """

        # transaction.atomic() as a plain passthrough (no real DB needed)
        class _FakeAtomic:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                return False  # don't suppress exceptions

        tx_mock.atomic.return_value = _FakeAtomic()

        # Dish visible in catalogue (stock_qty=1 passes the outer availability check)
        dish = _make_dish(slug="burger", price=Decimal("10.00"), stock_qty=1, pk=1)
        # But under select_for_update the row shows stock_qty=0 (depleted by a race)
        locked_dish = _make_dish(slug="burger", name="Burger", stock_qty=0, pk=1)

        first_order = _make_order()
        order_om.prefetch_related.return_value.filter.return_value.first.return_value = first_order

        dish_om.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]
        option_om.filter.return_value = []
        # The view calls Dish.objects.select_for_update().filter(pk__in=...)
        # so the mock chain is: dish_om.select_for_update().filter() -> [locked_dish]
        dish_om.select_for_update.return_value.filter.return_value = [locked_dish]

        item_om.create = MagicMock()

        resp = self._post(body={"items": [{"dish_slug": "burger", "qty": 2}]})

        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "out_of_stock")
        item_om.create.assert_not_called()
        broadcast_mock.assert_not_called()

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.OrderItem.objects")
    @patch("menu.views.DishOption.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_unlimited_stock_dish_disabled_under_lock_is_rejected(
        self, order_om, tx_mock, dish_om, option_om, item_om, broadcast_mock
    ):
        """Unlimited-stock dish disabled (is_available=False) after outer query but
        before the locked re-read must return 409 out_of_stock (finding 4 regression
        guard — the lock now covers all dishes, not just stock-tracked ones)."""
        class _FakeAtomic:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

        tx_mock.atomic.return_value = _FakeAtomic()

        # Outer query sees is_available=True, stock_qty=None (unlimited)
        dish = _make_dish(slug="pasta", price=Decimal("8.00"), stock_qty=None, pk=2)
        # Under the lock: concurrent disable has set is_available=False
        locked_dish = _make_dish(slug="pasta", name="Pasta", stock_qty=None, is_available=False, pk=2)

        first_order = _make_order()
        order_om.prefetch_related.return_value.filter.return_value.first.return_value = first_order

        dish_om.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]
        option_om.filter.return_value = []
        dish_om.select_for_update.return_value.filter.return_value = [locked_dish]

        item_om.create = MagicMock()

        resp = self._post(body={"items": [{"dish_slug": "pasta", "qty": 1}]})

        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "out_of_stock")
        item_om.create.assert_not_called()
        broadcast_mock.assert_not_called()

    # ── is_voided present in response payload ─────────────────────────────────

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.OrderItem.objects")
    @patch("menu.views.DishOption.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_response_items_include_is_voided(
        self, order_om, tx_mock, dish_om, option_om, item_om, broadcast_mock
    ):
        dish = _make_dish(slug="burger", price=Decimal("10.00"))
        existing = _make_item(is_voided=False)
        first_order = _make_order(items=[existing])
        second_order = _make_order(items=[existing])

        order_om.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        order_om.prefetch_related.return_value.get.return_value = second_order

        tx_mock.atomic.return_value.__enter__ = MagicMock(return_value=None)
        tx_mock.atomic.return_value.__exit__ = MagicMock(return_value=False)

        dish_om.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]
        # All dishes are now locked via select_for_update().filter(pk__in=...)
        dish_om.select_for_update.return_value.filter.return_value = [dish]
        option_om.filter.return_value = []
        item_om.create = MagicMock()

        resp = self._post(body={"items": [{"dish_slug": "burger", "qty": 1}]})

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("items", resp.data)
        for item in resp.data["items"]:
            self.assertIn("is_voided", item)


    @patch("menu.views.Order.objects")
    def test_stale_option_ids_return_400(self, order_om):
        """An option_id that does not belong to the requested dish must return 400
        stale_options — stale cart must surface, not silently order at base price."""
        from types import SimpleNamespace
        order = _make_order()
        order_om.prefetch_related.return_value.filter.return_value.first.return_value = order

        # Two dishes; option 99 belongs to sushi, not burger.
        burger = _make_dish(slug="burger", name="Burger", price=Decimal("10.00"), pk=1)
        bad_opt = SimpleNamespace(id=99, name="Soy", price_delta=Decimal("1.00"),
                                  dish=SimpleNamespace(slug="sushi"))

        with patch("menu.views.Dish.objects") as dish_om, \
             patch("menu.views.DishOption.objects") as opt_om:
            dish_om.filter.return_value.select_related.return_value.prefetch_related.return_value = [burger]
            opt_om.filter.return_value.select_related.return_value = [bad_opt]

            resp = self._post(body={"items": [{"dish_slug": "burger", "qty": 1, "option_ids": [99]}]})

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "stale_options")
        self.assertIn("Burger", resp.data["detail"])
        self.assertEqual(resp.data["invalid_option_ids"], [99])


# ═══════════════════════════════════════════════════════════════════════════════
# StaffVoidOrderItemView — POST /api/staff/orders/<order_id>/items/<item_id>/void/
# ═══════════════════════════════════════════════════════════════════════════════

class StaffVoidOrderItemViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffVoidOrderItemView.as_view()
        # Patch _can_access_order so unit tests don't hit the DB for section lookups.
        _patcher = patch("menu.views._can_access_order", return_value=True)
        self._access_mock = _patcher.start()
        self.addCleanup(_patcher.stop)

    def _post(self, order_id=10, item_id=901, body=None, user=None):
        body = body or {}
        req = self.factory.post(
            f"/api/staff/orders/{order_id}/items/{item_id}/void/",
            body,
            format="json",
        )
        u = user or _user()
        force_authenticate(req, user=u)
        req.tenant = _tenant()
        return self.view(req, order_id=order_id, item_id=item_id)

    # ── Guards ────────────────────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_order_not_found_404(self, om):
        om.prefetch_related.return_value.filter.return_value.first.return_value = None
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("menu.views.Order.objects")
    def test_item_not_found_404(self, om):
        order = _make_order(items=[])
        # items.filter().first() returns None (no item with that id)
        order.items.filter.return_value.first.return_value = None
        om.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post(item_id=999)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("menu.views.Order.objects")
    def test_already_voided_409(self, om):
        item = _make_item(is_voided=True)
        order = _make_order(items=[item])
        order.items.filter.return_value.first.return_value = item
        om.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_voided")

    @patch("menu.views.Order.objects")
    def test_terminal_status_409(self, om):
        item = _make_item(is_voided=False)
        order = _make_order(
            status_val=Order.Status.COMPLETED,
            items=[item],
        )
        order.items.filter.return_value.first.return_value = item
        om.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "bad_status")

    # ── Happy path: void + restock + recompute totals ─────────────────────────

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_void_restocks_and_recomputes_totals(
        self, order_om, tx_mock, dish_om, broadcast_mock
    ):
        item = _make_item(dish_slug="burger", qty=2,
                          unit_price=Decimal("10.00"), subtotal=Decimal("20.00"),
                          is_voided=False)
        remaining_item = _make_item(item_id=902, dish_slug="pasta",
                                    subtotal=Decimal("15.00"), is_voided=False)

        first_order = _make_order(
            total=Decimal("35.00"),
            items=[item, remaining_item],
        )
        first_order.items.filter.return_value.first.return_value = item

        # After reload only remaining_item is non-voided
        voided_item = _make_item(is_voided=True, qty=2)
        second_order = _make_order(
            total=Decimal("35.00"),
            items=[voided_item, remaining_item],
        )

        order_om.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        # Order reload now uses select_for_update() to lock the row (TOCTOU fix)
        order_om.select_for_update.return_value.prefetch_related.return_value.get.return_value = second_order

        tx_mock.atomic.return_value.__enter__ = MagicMock(return_value=None)
        tx_mock.atomic.return_value.__exit__ = MagicMock(return_value=False)

        # No stock tracking on this dish
        dish_om.filter.return_value.select_for_update.return_value = []

        resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # item.save called with the exact update_fields
        item.save.assert_called_once_with(update_fields=["is_voided", "voided_at", "void_reason", "voided_by_user_id"])
        # order.save — no wallet refund so wallet_amount_paid NOT in update_fields
        second_order.save.assert_called_once_with(
            update_fields=["total", "updated_at"]
        )
        # Total recomputed: only remaining_item (15.00) is non-voided
        self.assertEqual(second_order.total, Decimal("15.00"))
        broadcast_mock.assert_called_once()

    # ── Wallet refund on PAID order ───────────────────────────────────────────

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_void_on_paid_wallet_order_refunds_exact_line_total(
        self, order_om, tx_mock, dish_om, broadcast_mock
    ):
        """
        PAID wallet order: credit_wallet is called with the item's subtotal as the
        refund amount and the idempotency key f"voiditem:{schema}:{item_id}".
        wallet_amount_paid is decremented by that amount.

        The view does `from accounts.wallet_service import credit_wallet` inside
        the atomic block, so we patch at the source module.
        """
        line_total = Decimal("20.00")
        wallet_paid = Decimal("35.00")

        item = _make_item(item_id=901, dish_slug="burger", qty=2,
                          unit_price=Decimal("10.00"), subtotal=line_total,
                          is_voided=False)
        remaining = _make_item(item_id=902, subtotal=Decimal("15.00"), is_voided=False)

        first_order = _make_order(
            payment_status=Order.PaymentStatus.PAID,
            wallet_amount_paid=wallet_paid,
            customer_id=42,
            items=[item, remaining],
        )
        first_order.items.filter.return_value.first.return_value = item

        voided_item = _make_item(item_id=901, is_voided=True, subtotal=line_total)
        second_order = _make_order(
            payment_status=Order.PaymentStatus.PAID,
            wallet_amount_paid=wallet_paid,
            customer_id=42,
            items=[voided_item, remaining],
        )

        order_om.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        # Order reload now uses select_for_update() (TOCTOU fix)
        order_om.select_for_update.return_value.prefetch_related.return_value.get.return_value = second_order

        tx_mock.atomic.return_value.__enter__ = MagicMock(return_value=None)
        tx_mock.atomic.return_value.__exit__ = MagicMock(return_value=False)

        dish_om.filter.return_value.select_for_update.return_value = []

        # Patch at the source — the view imports credit_wallet from accounts.wallet_service
        with patch("accounts.wallet_service.credit_wallet") as mock_cw:
            resp = self._post(item_id=901)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # wallet_amount_paid decremented on the reloaded order BEFORE credit_wallet is called
        self.assertEqual(second_order.wallet_amount_paid, Decimal("15.00"))  # 35 - 20
        # order.save includes wallet_amount_paid since a refund occurred
        second_order.save.assert_called_once_with(
            update_fields=["total", "updated_at", "wallet_amount_paid"]
        )
        mock_cw.assert_called_once()
        call_kwargs = mock_cw.call_args
        pos_args = call_kwargs[0]
        kw_args = call_kwargs[1]
        self.assertEqual(pos_args[0], 42)                   # customer_id
        self.assertEqual(pos_args[1], Decimal("20.00"))     # refund = min(line_total, wallet_paid)
        # OPS-5g: tenant-schema-namespaced (shared-schema ledger → GLOBAL key namespace).
        from django.db import connection as _c
        self.assertEqual(kw_args["idempotency_key"], f"voiditem:{_c.schema_name}:901")
        # tx_type is WalletTransaction.Type.REFUND — compare the value string
        tx_type_val = kw_args["tx_type"]
        self.assertEqual(
            tx_type_val.value if hasattr(tx_type_val, "value") else str(tx_type_val),
            "refund",
        )

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_double_void_409(self, order_om, tx_mock, dish_om, broadcast_mock):
        """A second void of the same item must return 409 already_voided."""
        item = _make_item(is_voided=True)  # already voided
        order = _make_order(items=[item])
        order.items.filter.return_value.first.return_value = item
        order_om.prefetch_related.return_value.filter.return_value.first.return_value = order

        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_voided")
        # save must not have been called
        item.save.assert_not_called()

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_cash_paid_void_rejected_cannot_void_paid(
        self, order_om, tx_mock, dish_om, broadcast_mock
    ):
        """V1: an order paid in cash (wallet_amount_paid == 0, so the money can't
        be auto-reconciled by a wallet refund) must be REJECTED with 400
        cannot_void_paid rather than silently shrinking the total below what was
        actually collected. No mutation, no wallet call, no broadcast."""
        item = _make_item(is_voided=False, subtotal=Decimal("10.00"))
        first_order = _make_order(
            payment_status=Order.PaymentStatus.PAID,
            wallet_amount_paid=Decimal("0"),  # cash payment
            customer_id=42,
            items=[item],
        )
        first_order.items.filter.return_value.first.return_value = item

        order_om.prefetch_related.return_value.filter.return_value.first.return_value = first_order

        with patch("accounts.wallet_service.credit_wallet") as mock_cw:
            resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "cannot_void_paid")
        mock_cw.assert_not_called()
        item.save.assert_not_called()  # item was never mutated
        broadcast_mock.assert_not_called()

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_unpaid_order_void_still_works(
        self, order_om, tx_mock, dish_om, broadcast_mock
    ):
        """V1 must not affect voiding on an UNPAID order — only already-PAID,
        non-wallet-refundable orders are blocked."""
        item = _make_item(is_voided=False, subtotal=Decimal("10.00"))
        first_order = _make_order(
            payment_status=Order.PaymentStatus.UNPAID,
            wallet_amount_paid=Decimal("0"),
            items=[item],
        )
        first_order.items.filter.return_value.first.return_value = item

        second_order = _make_order(
            payment_status=Order.PaymentStatus.UNPAID,
            wallet_amount_paid=Decimal("0"),
            items=[],
        )

        order_om.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        order_om.select_for_update.return_value.prefetch_related.return_value.get.return_value = second_order

        tx_mock.atomic.return_value.__enter__ = MagicMock(return_value=None)
        tx_mock.atomic.return_value.__exit__ = MagicMock(return_value=False)
        dish_om.filter.return_value.select_for_update.return_value = []

        with patch("accounts.wallet_service.credit_wallet") as mock_cw:
            resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_cw.assert_not_called()

    # ── is_voided in staff payload ────────────────────────────────────────────

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_response_items_include_is_voided_flag(
        self, order_om, tx_mock, dish_om, broadcast_mock
    ):
        item = _make_item(is_voided=False)
        first_order = _make_order(items=[item])
        first_order.items.filter.return_value.first.return_value = item

        voided = _make_item(is_voided=True)
        second_order = _make_order(items=[voided])

        order_om.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        # Order reload now uses select_for_update() (TOCTOU fix)
        order_om.select_for_update.return_value.prefetch_related.return_value.get.return_value = second_order

        tx_mock.atomic.return_value.__enter__ = MagicMock(return_value=None)
        tx_mock.atomic.return_value.__exit__ = MagicMock(return_value=False)
        dish_om.filter.return_value.select_for_update.return_value = []

        resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for it in resp.data["items"]:
            self.assertIn("is_voided", it)


# ═══════════════════════════════════════════════════════════════════════════════
# StaffCompOrderItemView — POST /api/staff/orders/<order_id>/items/<item_id>/comp/ (V3)
# ═══════════════════════════════════════════════════════════════════════════════

class StaffCompOrderItemViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffCompOrderItemView.as_view()
        # Patch _can_access_order so unit tests don't hit the DB for section lookups.
        _patcher = patch("menu.views._can_access_order", return_value=True)
        self._access_mock = _patcher.start()
        self.addCleanup(_patcher.stop)

    def _post(self, order_id=10, item_id=901, body=None, user=None):
        body = body if body is not None else {"reason": "Manager goodwill"}
        req = self.factory.post(
            f"/api/staff/orders/{order_id}/items/{item_id}/comp/",
            body,
            format="json",
        )
        u = user or _user()
        force_authenticate(req, user=u)
        req.tenant = _tenant()
        return self.view(req, order_id=order_id, item_id=item_id)

    # ── Auth ──────────────────────────────────────────────────────────────────

    @patch("menu.views._can_void_order_item", return_value=False)
    def test_no_void_permission_403(self, _mock):
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "forbidden")

    # ── Guards ────────────────────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_order_not_found_404(self, om):
        om.prefetch_related.return_value.filter.return_value.first.return_value = None
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("menu.views.Order.objects")
    def test_item_not_found_404(self, om):
        order = _make_order(items=[])
        order.items.filter.return_value.first.return_value = None
        om.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post(item_id=999)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("menu.views.Order.objects")
    def test_already_comped_409(self, om):
        item = _make_item(is_comped=True)
        order = _make_order(items=[item])
        order.items.filter.return_value.first.return_value = item
        om.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_comped")

    @patch("menu.views.Order.objects")
    def test_already_voided_409(self, om):
        item = _make_item(is_voided=True)
        order = _make_order(items=[item])
        order.items.filter.return_value.first.return_value = item
        om.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_voided")

    @patch("menu.views.Order.objects")
    def test_terminal_status_409(self, om):
        item = _make_item(is_comped=False)
        order = _make_order(status_val=Order.Status.COMPLETED, items=[item])
        order.items.filter.return_value.first.return_value = item
        om.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "bad_status")

    @patch("menu.views.Order.objects")
    def test_reason_required_400(self, om):
        item = _make_item(is_comped=False)
        order = _make_order(items=[item])
        order.items.filter.return_value.first.return_value = item
        om.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post(body={"reason": "   "})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "reason_required")
        item.save.assert_not_called()

    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_cash_paid_comp_rejected_cannot_comp_paid(self, om, tx_mock):
        """Same money rule as void: a cash-settled PAID order (wallet_amount_paid
        == 0) cannot auto-reconcile a comp and must be rejected."""
        item = _make_item(is_comped=False, subtotal=Decimal("10.00"))
        order = _make_order(
            payment_status=Order.PaymentStatus.PAID,
            wallet_amount_paid=Decimal("0"),
            customer_id=42,
            items=[item],
        )
        order.items.filter.return_value.first.return_value = item
        om.prefetch_related.return_value.filter.return_value.first.return_value = order

        with patch("accounts.wallet_service.credit_wallet") as mock_cw:
            resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "cannot_comp_paid")
        mock_cw.assert_not_called()
        item.save.assert_not_called()

    # ── Happy path: comp excludes item from total, records who/reason ─────────

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_comp_excludes_item_from_total_and_records_who_reason(
        self, order_om, tx_mock, broadcast_mock
    ):
        item = _make_item(item_id=901, dish_slug="burger", qty=2,
                          unit_price=Decimal("10.00"), subtotal=Decimal("20.00"),
                          is_comped=False)
        remaining_item = _make_item(item_id=902, dish_slug="pasta",
                                    subtotal=Decimal("15.00"), is_comped=False)

        first_order = _make_order(
            total=Decimal("35.00"),
            items=[item, remaining_item],
        )
        first_order.items.filter.return_value.first.return_value = item

        # After reload only remaining_item is non-comped/non-voided
        comped_item = _make_item(is_comped=True, qty=2)
        second_order = _make_order(
            total=Decimal("35.00"),
            items=[comped_item, remaining_item],
        )

        order_om.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        order_om.select_for_update.return_value.prefetch_related.return_value.get.return_value = second_order

        tx_mock.atomic.return_value.__enter__ = MagicMock(return_value=None)
        tx_mock.atomic.return_value.__exit__ = MagicMock(return_value=False)

        staff = _user()
        staff.id = 77
        resp = self._post(body={"reason": "Sent out wrong dish, comped"}, user=staff)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # item.save called with the exact update_fields, recording who/reason/when
        item.save.assert_called_once_with(
            update_fields=["is_comped", "comped_at", "comp_reason", "comped_by_user_id"]
        )
        self.assertTrue(item.is_comped)
        self.assertEqual(item.comp_reason, "Sent out wrong dish, comped")
        self.assertEqual(item.comped_by_user_id, 77)
        self.assertIsNotNone(item.comped_at)
        # Total recomputed: only remaining_item (15.00) is non-voided/non-comped
        self.assertEqual(second_order.total, Decimal("15.00"))
        broadcast_mock.assert_called_once()

    # ── Wallet refund on PAID order — follows the same rule as void ───────────

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_comp_on_paid_wallet_order_refunds_exact_line_total(
        self, order_om, tx_mock, broadcast_mock
    ):
        line_total = Decimal("20.00")
        wallet_paid = Decimal("35.00")

        item = _make_item(item_id=901, dish_slug="burger", qty=2,
                          unit_price=Decimal("10.00"), subtotal=line_total,
                          is_comped=False)
        remaining = _make_item(item_id=902, subtotal=Decimal("15.00"), is_comped=False)

        first_order = _make_order(
            payment_status=Order.PaymentStatus.PAID,
            wallet_amount_paid=wallet_paid,
            customer_id=42,
            items=[item, remaining],
        )
        first_order.items.filter.return_value.first.return_value = item

        comped_item = _make_item(is_comped=True, qty=2, subtotal=line_total)
        second_order = _make_order(
            payment_status=Order.PaymentStatus.PAID,
            wallet_amount_paid=wallet_paid,
            customer_id=42,
            total=Decimal("15.00"),
            items=[comped_item, remaining],
        )

        order_om.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        order_om.select_for_update.return_value.prefetch_related.return_value.get.return_value = second_order

        tx_mock.atomic.return_value.__enter__ = MagicMock(return_value=None)
        tx_mock.atomic.return_value.__exit__ = MagicMock(return_value=False)

        with patch("accounts.wallet_service.credit_wallet") as mock_cw:
            from django.db import connection as _c
            resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_cw.assert_called_once()
        kw_args = mock_cw.call_args.kwargs
        self.assertEqual(mock_cw.call_args.args[1], line_total)
        self.assertEqual(kw_args["idempotency_key"], f"compitem:{_c.schema_name}:901")
        self.assertEqual(second_order.wallet_amount_paid, wallet_paid - line_total)

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_double_comp_409(self, order_om, tx_mock, broadcast_mock):
        """A second comp of the same item must return 409 already_comped."""
        item = _make_item(is_comped=True)  # already comped
        order = _make_order(items=[item])
        order.items.filter.return_value.first.return_value = item
        order_om.prefetch_related.return_value.filter.return_value.first.return_value = order

        resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_comped")

    # ── is_comped in staff payload ─────────────────────────────────────────────

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_response_items_include_is_comped_flag(
        self, order_om, tx_mock, broadcast_mock
    ):
        item = _make_item(is_comped=False)
        first_order = _make_order(items=[item])
        first_order.items.filter.return_value.first.return_value = item

        comped = _make_item(is_comped=True)
        second_order = _make_order(items=[comped])

        order_om.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        order_om.select_for_update.return_value.prefetch_related.return_value.get.return_value = second_order

        tx_mock.atomic.return_value.__enter__ = MagicMock(return_value=None)
        tx_mock.atomic.return_value.__exit__ = MagicMock(return_value=False)

        resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for it in resp.data["items"]:
            self.assertIn("is_comped", it)
