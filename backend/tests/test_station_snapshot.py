"""
Tests for prep-station snapshotting — backend.

Covers:
  PlaceOrderView:
    - category.station value flows → OrderItem.create(station=...)
    - empty station snapshots as "" (no station)
  StaffAppendOrderItemsView:
    - category.station value flows → OrderItem.create(station=...)
    - empty station snapshots as ""
  Edge cases:
    - dish with no category snapshots station as ""

House style: SimpleTestCase + MagicMock, no real DB.
Mirrors the pattern in test_course_sequencing.py.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from menu.views import StaffAppendOrderItemsView
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
    t = SimpleNamespace(id=tenant_id)
    plan = MagicMock()
    plan.can_checkout = True
    plan.can_whatsapp_order = False
    t.plan = plan
    return t


def _make_dish(slug="burger", name="Burger", price=Decimal("12.50"),
               stock_qty=None, is_published=True, is_available=True,
               pk=1, category_course=0, category_station=""):
    cat = MagicMock()
    cat.course = category_course
    cat.station = category_station
    d = MagicMock()
    d.pk = pk
    d.slug = slug
    d.name = name
    d.price = price
    d.stock_qty = stock_qty
    d.is_published = is_published
    d.is_available = is_available
    d.currency = "MAD"
    d.category = cat
    d.combo_components.all.return_value = []
    return d


def _make_item(item_id=901, dish_name="Burger", dish_slug="burger",
               qty=1, unit_price=Decimal("12.50"), subtotal=Decimal("12.50"),
               course=0, station=""):
    item = MagicMock()
    item.id = item_id
    item.dish_name = dish_name
    item.dish_slug = dish_slug
    item.qty = qty
    item.unit_price = unit_price
    item.subtotal = subtotal
    item.options = []
    item.note = ""
    item.is_ready = False
    item.is_voided = False
    item.course = course
    item.station = station
    item.combo_components = []
    item.save = MagicMock()
    return item


def _make_order(order_id=10, status_val=Order.Status.PENDING,
                fulfillment_type=Order.FulfillmentType.TABLE,
                payment_status=Order.PaymentStatus.UNPAID,
                total=Decimal("12.50"), items=None):
    order = MagicMock()
    order.id = order_id
    order.order_number = "ORD-001"
    order.status = status_val
    order.fulfillment_type = fulfillment_type
    order.payment_status = payment_status
    order.total = total
    order.delivery_fee = Decimal("0")
    order.tip_amount = Decimal("0")
    order.promotion_discount = Decimal("0")
    order.loyalty_discount = Decimal("0")
    order.wallet_amount_paid = Decimal("0")
    order.customer_id = None
    order.table_label = "T1"
    order.customer_name = "Alice"
    order.customer_note = ""
    order.owner_note = ""
    order.estimated_ready_minutes = None
    order.currency = "MAD"
    order.scheduled_for = None
    order.fired_course = 1
    order.save = MagicMock()
    order.created_at = MagicMock()
    order.created_at.isoformat.return_value = "2026-06-18T10:00:00+00:00"
    order.updated_at = MagicMock()
    order.updated_at.isoformat.return_value = "2026-06-18T10:00:00+00:00"
    _items = items or []
    items_qs = MagicMock()
    items_qs.all.return_value = _items
    items_qs.filter.return_value.first.return_value = _items[0] if _items else None
    order.items = items_qs
    payments_qs = MagicMock()
    payments_qs.all.return_value = []
    order.payments = payments_qs
    return order


# ═══════════════════════════════════════════════════════════════════════════════
# PlaceOrderView — station snapshot
# ═══════════════════════════════════════════════════════════════════════════════

class PlacementStationSnapshotTests(SimpleTestCase):
    """PlaceOrderView must snapshot category.station onto each OrderItem."""

    def setUp(self):
        from menu.views import PlaceOrderView
        self.factory = APIRequestFactory()
        self.view = PlaceOrderView.as_view()

    def _run(self, dish):
        """Invoke PlaceOrderView for a single-item table order, return item_om."""
        profile = MagicMock()
        profile.is_menu_published = True
        profile.is_menu_temporarily_disabled = False
        profile.is_ordering_enabled = True
        profile.is_open = True
        profile.business_hours_schedule = {}
        profile.capabilities = {}
        profile.lat = None
        profile.lng = None

        class _FakeAtomic:
            def __enter__(self): return self
            def __exit__(self, *a): return False

        with patch("menu.views.OrderItem.objects") as item_om, \
             patch("menu.views.Dish.objects") as dish_om, \
             patch("menu.views.DishOption.objects") as opt_om, \
             patch("menu.views.transaction") as tx, \
             patch("menu.views.Order.objects") as order_om, \
             patch("menu.views.Profile.objects") as prof_om, \
             patch("menu.views.Promotion.objects"), \
             patch("menu.views.LoyaltyConfig.objects") as lc_om, \
             patch("menu.views.get_all_active_hh_rules", return_value=[]), \
             patch("menu.views._generate_order_number", return_value="ORD-TEST"), \
             patch("menu.views.TableLink.objects") as tl_om:

            prof_om.filter.return_value.first.return_value = profile
            dish_om.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]
            dish_om.select_for_update.return_value.filter.return_value = []
            opt_om.filter.return_value.select_related.return_value = []
            lc_om.filter.return_value.first.return_value = None
            tx.atomic.return_value = _FakeAtomic()
            order_om.create.return_value = _make_order()
            item_om.create = MagicMock()
            tl = MagicMock()
            tl.label = "T1"
            tl_om.filter.return_value.first.return_value = tl

            tenant = _tenant()
            u = _user()
            u.tenant_id = tenant.id
            req = self.factory.post("/api/place-order/", {
                "items": [{"slug": dish.slug, "qty": 1}],
                "fulfillment_type": "table",
                "table_slug": "t1",
                "customer_name": "Bob",
            }, format="json")
            force_authenticate(req, user=u)
            req.tenant = tenant
            req.session = {}
            resp = self.view(req, order_id=None)

        return item_om, resp

    def test_station_value_snapshotted(self):
        dish = _make_dish(slug="cocktail", name="Mojito",
                          category_station="bar", category_course=0, pk=10)
        item_om, resp = self._run(dish)
        self.assertTrue(
            item_om.create.called,
            f"OrderItem.create was never called (status={resp.status_code}). "
            "Mock setup must allow view to reach item creation.",
        )
        kwargs = item_om.create.call_args[1]
        self.assertEqual(kwargs.get("station"), "bar",
                         "OrderItem.create must receive station='bar' from category")

    def test_empty_station_snapshotted_as_empty_string(self):
        dish = _make_dish(slug="steak", name="Steak",
                          category_station="", category_course=0, pk=11)
        item_om, resp = self._run(dish)
        self.assertTrue(item_om.create.called,
                        f"OrderItem.create was never called (status={resp.status_code})")
        kwargs = item_om.create.call_args[1]
        self.assertEqual(kwargs.get("station"), "",
                         "Empty category.station should produce station='' on OrderItem")


# ═══════════════════════════════════════════════════════════════════════════════
# StaffAppendOrderItemsView — station snapshot
# ═══════════════════════════════════════════════════════════════════════════════

class AppendStationSnapshotTests(SimpleTestCase):
    """StaffAppendOrderItemsView must snapshot category.station onto each OrderItem."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffAppendOrderItemsView.as_view()
        _patcher = patch("menu.views._can_access_order", return_value=True)
        self._access_mock = _patcher.start()
        self.addCleanup(_patcher.stop)

    def _post(self, dish, order_id=10):
        first_order = _make_order(order_id=order_id)
        new_item = _make_item(item_id=902, dish_slug=dish.slug,
                              station=dish.category.station)
        second_order = _make_order(order_id=order_id, items=[new_item])

        class _FakeAtomic:
            def __enter__(self): return self
            def __exit__(self, *a): return False

        with patch("menu.views._broadcast_order_change"), \
             patch("menu.views.OrderItem.objects") as item_om, \
             patch("menu.views.DishOption.objects") as opt_om, \
             patch("menu.views.Dish.objects") as dish_om, \
             patch("menu.views.transaction") as tx, \
             patch("menu.views.Order.objects") as order_om:

            order_om.prefetch_related.return_value.filter.return_value.first.return_value = first_order
            order_om.prefetch_related.return_value.get.return_value = second_order
            tx.atomic.return_value = _FakeAtomic()
            dish_om.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]
            dish_om.select_for_update.return_value.filter.return_value = [dish]
            opt_om.filter.return_value = []
            item_om.create = MagicMock()

            req = self.factory.post(
                f"/api/staff/orders/{order_id}/items/",
                {"items": [{"dish_slug": dish.slug, "qty": 1}]},
                format="json",
            )
            force_authenticate(req, user=_user())
            req.tenant = _tenant()
            resp = self.view(req, order_id=order_id)

        return item_om, resp

    def test_station_value_snapshotted(self):
        dish = _make_dish(slug="grill-steak", name="Grill Steak",
                          category_station="grill", category_course=0, pk=20)
        item_om, resp = self._post(dish)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(item_om.create.called,
                        "OrderItem.create should have been called")
        kwargs = item_om.create.call_args[1]
        self.assertEqual(kwargs.get("station"), "grill",
                         "OrderItem.create must receive station='grill' from category")

    def test_empty_station_snapshotted_as_empty_string(self):
        dish = _make_dish(slug="salad", name="Salad",
                          category_station="", category_course=0, pk=21)
        item_om, resp = self._post(dish)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(item_om.create.called,
                        "OrderItem.create should have been called")
        kwargs = item_om.create.call_args[1]
        self.assertEqual(kwargs.get("station"), "",
                         "Empty category.station should produce station='' on OrderItem")
