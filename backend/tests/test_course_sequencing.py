"""
Tests for course sequencing (fire starters before mains) — backend.

Covers:
  StaffFireCourseView  POST /api/staff/orders/<id>/fire-course/
    - happy path (fired_course set, broadcast called, full staff payload returned)
    - monotonic 409 already_fired
    - 400 invalid_course (0, 5, "x", None)
    - 409 not_table for pickup / delivery
    - 409 bad_status for terminal orders (completed / cancelled)
    - section-gate enforced (mirrors existing section-bypass tests)
  Placement snapshot (PlaceOrderView path):
    - course flows dish.category.course → item dict (verified via item_om.create call_kwargs)
  Append snapshot (StaffAppendOrderItemsView):
    - course flows dish.category.course → item dict
  Payload shape:
    - _staff_order_payload items carry "course"
    - _staff_order_payload order carries "fired_course"

House style: SimpleTestCase + MagicMock, no real DB.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from menu.views import (
    StaffFireCourseView,
    StaffAppendOrderItemsView,
    _staff_order_payload,
)
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
    course=0,
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
    item.course = course
    item.combo_components = []
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
    fired_course=1,
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
    order.fired_course = fired_course
    order.save = MagicMock()
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


def _make_dish(slug="burger", name="Burger", price=Decimal("12.50"),
               stock_qty=None, is_published=True, is_available=True,
               pk=1, category_course=0):
    cat = MagicMock()
    cat.course = category_course
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


# ═══════════════════════════════════════════════════════════════════════════════
# StaffFireCourseView — POST /api/staff/orders/<order_id>/fire-course/
# ═══════════════════════════════════════════════════════════════════════════════

class StaffFireCourseViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffFireCourseView.as_view()
        _patcher = patch("menu.views._can_access_order", return_value=True)
        self._access_mock = _patcher.start()
        self.addCleanup(_patcher.stop)

        # The view now uses transaction.atomic() + select_for_update() to prevent
        # concurrent fires.  Patch transaction so SimpleTestCase (no DB) doesn't choke.
        class _FakeAtomic:
            def __enter__(self): return self
            def __exit__(self, *a): return False

        _tx_patcher = patch("menu.views.transaction")
        self._tx_mock = _tx_patcher.start()
        self._tx_mock.atomic.return_value = _FakeAtomic()
        self.addCleanup(_tx_patcher.stop)

    def _post(self, order_id=10, body=None, user=None):
        body = body if body is not None else {"course": 2}
        req = self.factory.post(
            f"/api/staff/orders/{order_id}/fire-course/",
            body,
            format="json",
        )
        u = user or _user()
        force_authenticate(req, user=u)
        req.tenant = _tenant()
        return self.view(req, order_id=order_id)

    # ── Auth / permission ─────────────────────────────────────────────────────

    def test_unauthenticated_is_403(self):
        req = self.factory.post("/api/staff/orders/10/fire-course/", {}, format="json")
        with patch("menu.views.Order.objects") as om:
            om.prefetch_related.return_value.filter.return_value.first.return_value = None
            resp = self.view(req, order_id=10)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("menu.views._can_edit_tenant_order", return_value=False)
    def test_no_permission_is_403(self, _mock):
        req = self.factory.post("/api/staff/orders/10/fire-course/", {}, format="json")
        force_authenticate(req, user=_user())
        req.tenant = _tenant()
        resp = self.view(req, order_id=10)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Section gate ──────────────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_section_gate_enforced(self, om):
        """When _can_access_order returns False, view must return 403 section_denied."""
        order = _make_order()
        om.filter.return_value.exists.return_value = True
        om.select_for_update.return_value.prefetch_related.return_value.filter.return_value.first.return_value = order
        with patch("menu.views._can_access_order", return_value=False):
            resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "section_denied")

    # ── Not-found ─────────────────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_order_not_found_404(self, om):
        # exists() returns False → early 404 before the lock
        om.filter.return_value.exists.return_value = False
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "not_found")

    # ── Guards ────────────────────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_terminal_status_completed_409(self, om):
        order = _make_order(status_val=Order.Status.COMPLETED)
        om.filter.return_value.exists.return_value = True
        om.select_for_update.return_value.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "bad_status")

    @patch("menu.views.Order.objects")
    def test_terminal_status_cancelled_409(self, om):
        order = _make_order(status_val=Order.Status.CANCELLED)
        om.filter.return_value.exists.return_value = True
        om.select_for_update.return_value.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "bad_status")

    @patch("menu.views.Order.objects")
    def test_not_table_pickup_409(self, om):
        order = _make_order(fulfillment_type=Order.FulfillmentType.PICKUP)
        om.filter.return_value.exists.return_value = True
        om.select_for_update.return_value.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "not_table")

    @patch("menu.views.Order.objects")
    def test_not_table_delivery_409(self, om):
        order = _make_order(fulfillment_type=Order.FulfillmentType.DELIVERY)
        om.filter.return_value.exists.return_value = True
        om.select_for_update.return_value.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "not_table")

    # ── Invalid course values ─────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_course_zero_is_400(self, om):
        order = _make_order()
        om.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post(body={"course": 0})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_course")

    @patch("menu.views.Order.objects")
    def test_course_five_is_400(self, om):
        order = _make_order()
        om.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post(body={"course": 5})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_course")

    @patch("menu.views.Order.objects")
    def test_course_string_is_400(self, om):
        order = _make_order()
        om.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post(body={"course": "x"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_course")

    @patch("menu.views.Order.objects")
    def test_course_none_is_400(self, om):
        order = _make_order()
        om.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post(body={"course": None})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_course")

    # ── Already fired (monotonic) ─────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_already_fired_same_course_409(self, om):
        """Firing the same course twice must return 409 already_fired."""
        order = _make_order(fired_course=2)
        om.filter.return_value.exists.return_value = True
        om.select_for_update.return_value.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post(body={"course": 2})
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_fired")

    @patch("menu.views.Order.objects")
    def test_already_fired_lower_course_409(self, om):
        """Firing a lower course when a higher course is already fired must return 409."""
        order = _make_order(fired_course=3)
        om.filter.return_value.exists.return_value = True
        om.select_for_update.return_value.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post(body={"course": 2})
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_fired")

    # ── Happy path ────────────────────────────────────────────────────────────

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Order.objects")
    def test_happy_path_sets_fired_course_and_broadcasts(self, om, broadcast_mock):
        """Firing course 2 on a fresh order sets fired_course=2, saves, broadcasts."""
        item = _make_item(course=2)
        first_order = _make_order(fired_course=1, items=[item])
        second_order = _make_order(fired_course=2, items=[item])

        om.filter.return_value.exists.return_value = True
        om.select_for_update.return_value.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        om.prefetch_related.return_value.get.return_value = second_order

        resp = self._post(body={"course": 2})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # fired_course was set and saved
        self.assertEqual(first_order.fired_course, 2)
        first_order.save.assert_called_once_with(update_fields=["fired_course", "updated_at"])
        # broadcast fired
        broadcast_mock.assert_called_once()

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Order.objects")
    def test_happy_path_returns_staff_payload_with_fired_course(self, om, broadcast_mock):
        """Response must include fired_course at the order level."""
        item = _make_item(course=2)
        first_order = _make_order(fired_course=1, items=[item])
        second_order = _make_order(fired_course=2, items=[item])

        om.filter.return_value.exists.return_value = True
        om.select_for_update.return_value.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        om.prefetch_related.return_value.get.return_value = second_order

        resp = self._post(body={"course": 2})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("fired_course", resp.data)
        self.assertEqual(resp.data["fired_course"], 2)

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Order.objects")
    def test_happy_path_items_carry_course(self, om, broadcast_mock):
        """Items in the response payload must include 'course'."""
        item = _make_item(course=2)
        first_order = _make_order(fired_course=1, items=[item])
        second_order = _make_order(fired_course=2, items=[item])

        om.filter.return_value.exists.return_value = True
        om.select_for_update.return_value.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        om.prefetch_related.return_value.get.return_value = second_order

        resp = self._post(body={"course": 2})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("items", resp.data)
        for it in resp.data["items"]:
            self.assertIn("course", it)

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Order.objects")
    def test_monotonic_fire_course_3_after_2(self, om, broadcast_mock):
        """Firing course 3 when fired_course is already 2 must succeed."""
        item = _make_item(course=3)
        first_order = _make_order(fired_course=2, items=[item])
        second_order = _make_order(fired_course=3, items=[item])

        om.filter.return_value.exists.return_value = True
        om.select_for_update.return_value.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        om.prefetch_related.return_value.get.return_value = second_order

        resp = self._post(body={"course": 3})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(first_order.fired_course, 3)

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Order.objects")
    def test_broadcast_exception_does_not_fail_request(self, om, broadcast_mock):
        """A broadcast exception must not propagate — response is still 200."""
        broadcast_mock.side_effect = Exception("ws down")
        item = _make_item(course=1)
        first_order = _make_order(fired_course=1, items=[item])
        second_order = _make_order(fired_course=2, items=[item])

        om.filter.return_value.exists.return_value = True
        om.select_for_update.return_value.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        om.prefetch_related.return_value.get.return_value = second_order

        resp = self._post(body={"course": 2})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════════════════════
# Placement snapshot — course flows dish.category.course → OrderItem
# ═══════════════════════════════════════════════════════════════════════════════

class PlacementCourseSnapshotTests(SimpleTestCase):
    """Verify the PlaceOrderView path snapshots category.course onto each OrderItem."""

    def setUp(self):
        from menu.views import PlaceOrderView
        self.factory = APIRequestFactory()
        self.view = PlaceOrderView.as_view()

    def _post(self, body, user=None):
        req = self.factory.post("/api/place-order/", body, format="json")
        if user:
            force_authenticate(req, user=user)
        req.tenant = _tenant()
        req.session = {}
        return req

    @patch("menu.views.RecipeLine")
    @patch("menu.views.OrderItem.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.DishOption.objects")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    @patch("menu.views.Profile.objects")
    @patch("menu.views.Promotion.objects")
    @patch("menu.views.LoyaltyConfig.objects")
    @patch("menu.views.get_all_active_hh_rules", return_value=[])
    @patch("menu.views._generate_order_number", return_value="ORD-TEST")
    def test_place_order_snapshots_category_course(
        self, mock_gen, mock_hh, mock_lc, mock_promo,
        mock_profile_om, mock_order_om, mock_tx,
        mock_dish_opt, mock_dish_om, mock_item_om, mock_rl,
    ):
        # Category with course=2
        dish = _make_dish(slug="steak", name="Steak", price=Decimal("50.00"),
                          category_course=2, pk=5)

        profile = MagicMock()
        profile.is_menu_published = True
        profile.is_menu_temporarily_disabled = False
        profile.is_ordering_enabled = True
        profile.is_open = True
        # Empty schedule → _schedule_open returns None → falls back to is_open=True
        profile.business_hours_schedule = {}
        profile.capabilities = {}
        profile.lat = None
        profile.lng = None
        mock_profile_om.filter.return_value.first.return_value = profile

        mock_dish_om.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]
        mock_dish_opt.filter.return_value.select_related.return_value = []
        mock_promo.objects = MagicMock()
        mock_promo.filter.return_value = []
        mock_lc.filter.return_value.first.return_value = None

        # transaction.atomic as passthrough
        class _FakeAtomic:
            def __enter__(self): return self
            def __exit__(self, *a): return False

        mock_tx.atomic.return_value = _FakeAtomic()

        created_order = _make_order()
        mock_order_om.create.return_value = created_order

        # Only finite-stock dishes hit select_for_update — steak has no stock
        mock_dish_om.select_for_update.return_value.filter.return_value = []

        mock_item_om.create = MagicMock()

        # Build a tenant with a plan that permits checkout so the plan-gate passes
        tenant = _tenant()
        plan = MagicMock()
        plan.can_checkout = True
        plan.can_whatsapp_order = False
        tenant.plan = plan

        req = self.factory.post("/api/place-order/", {
            "items": [{"slug": "steak", "qty": 1}],
            "fulfillment_type": "table",
            "table_slug": "t1",
            "customer_name": "Bob",
        }, format="json")
        # Authenticate as staff so can_preview=True bypasses closed-restaurant check
        u = _user()
        u.tenant_id = tenant.id
        force_authenticate(req, user=u)
        req.tenant = tenant
        req.session = {}

        # Patch TableLink lookup too
        with patch("menu.views.TableLink.objects") as tl_om:
            tl = MagicMock()
            tl.label = "T1"
            tl_om.filter.return_value.first.return_value = tl
            resp = self.view(req, order_id=None)

        # The view must have reached OrderItem.create — assert unconditionally
        self.assertTrue(
            mock_item_om.create.called,
            f"OrderItem.create was never called (status={resp.status_code}, "
            f"data={getattr(resp, 'data', None)}). "
            "The mock setup must allow the view to reach item creation.",
        )
        kwargs = mock_item_om.create.call_args[1]
        self.assertEqual(kwargs.get("course"), 2,
                         "OrderItem.create must receive course=2 (from category)")


# ═══════════════════════════════════════════════════════════════════════════════
# Append snapshot — StaffAppendOrderItemsView snapshots course
# ═══════════════════════════════════════════════════════════════════════════════

class AppendCourseSnapshotTests(SimpleTestCase):
    """Verify StaffAppendOrderItemsView snapshots dish.category.course onto OrderItem."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffAppendOrderItemsView.as_view()
        _patcher = patch("menu.views._can_access_order", return_value=True)
        self._access_mock = _patcher.start()
        self.addCleanup(_patcher.stop)

    def _post(self, order_id=10, body=None, user=None):
        body = body or {"items": [{"dish_slug": "steak", "qty": 1}]}
        req = self.factory.post(f"/api/staff/orders/{order_id}/items/", body, format="json")
        u = user or _user()
        force_authenticate(req, user=u)
        req.tenant = _tenant()
        return self.view(req, order_id=order_id)

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.OrderItem.objects")
    @patch("menu.views.DishOption.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_append_snapshots_category_course(
        self, order_om, tx_mock, dish_om, option_om, item_om, broadcast_mock
    ):
        """Dish with category.course=3 → item dict must have course=3."""
        dish = _make_dish(slug="steak", name="Steak", price=Decimal("50.00"),
                          category_course=3, pk=5)

        first_order = _make_order()
        new_item = _make_item(item_id=902, dish_slug="steak", course=3)
        second_order = _make_order(items=[new_item])

        order_om.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        order_om.prefetch_related.return_value.get.return_value = second_order

        class _FakeAtomic:
            def __enter__(self): return self
            def __exit__(self, *a): return False

        tx_mock.atomic.return_value = _FakeAtomic()

        dish_om.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]
        dish_om.select_for_update.return_value.filter.return_value = [dish]
        option_om.filter.return_value = []
        item_om.create = MagicMock()

        resp = self._post(body={"items": [{"dish_slug": "steak", "qty": 1}]})

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(item_om.create.called, "OrderItem.create should have been called")
        kwargs = item_om.create.call_args[1]
        self.assertEqual(kwargs.get("course"), 3,
                         "OrderItem.create must receive course=3 (from category)")

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.OrderItem.objects")
    @patch("menu.views.DishOption.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.transaction")
    @patch("menu.views.Order.objects")
    def test_append_course_zero_when_category_course_zero(
        self, order_om, tx_mock, dish_om, option_om, item_om, broadcast_mock
    ):
        """Dish with category.course=0 → item dict must have course=0 (no course)."""
        dish = _make_dish(slug="salad", name="Salad", price=Decimal("10.00"),
                          category_course=0, pk=6)

        first_order = _make_order()
        new_item = _make_item(item_id=903, dish_slug="salad", course=0)
        second_order = _make_order(items=[new_item])

        order_om.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        order_om.prefetch_related.return_value.get.return_value = second_order

        class _FakeAtomic:
            def __enter__(self): return self
            def __exit__(self, *a): return False

        tx_mock.atomic.return_value = _FakeAtomic()

        dish_om.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]
        dish_om.select_for_update.return_value.filter.return_value = [dish]
        option_om.filter.return_value = []
        item_om.create = MagicMock()

        resp = self._post(body={"items": [{"dish_slug": "salad", "qty": 1}]})

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        kwargs = item_om.create.call_args[1]
        self.assertEqual(kwargs.get("course"), 0)


# ═══════════════════════════════════════════════════════════════════════════════
# _staff_order_payload shape tests
# ═══════════════════════════════════════════════════════════════════════════════

class StaffOrderPayloadShapeTests(SimpleTestCase):
    """Verify _staff_order_payload includes course on items and fired_course on order."""

    def test_payload_includes_fired_course(self):
        item = _make_item(course=2)
        order = _make_order(fired_course=2, items=[item])
        payload = _staff_order_payload(order)
        self.assertIn("fired_course", payload)
        self.assertEqual(payload["fired_course"], 2)

    def test_payload_items_include_course(self):
        item = _make_item(course=1)
        order = _make_order(fired_course=1, items=[item])
        payload = _staff_order_payload(order)
        self.assertIn("items", payload)
        for it in payload["items"]:
            self.assertIn("course", it)

    def test_payload_items_course_value_matches_item(self):
        item1 = _make_item(item_id=1, course=1)
        item2 = _make_item(item_id=2, course=3)
        order = _make_order(fired_course=1, items=[item1, item2])
        payload = _staff_order_payload(order)
        courses = [it["course"] for it in payload["items"]]
        self.assertEqual(courses, [1, 3])

    def test_payload_fired_course_default_one(self):
        """When fired_course is 1 (default) the payload reflects it."""
        item = _make_item(course=0)
        order = _make_order(fired_course=1, items=[item])
        payload = _staff_order_payload(order)
        self.assertEqual(payload["fired_course"], 1)


# ═══════════════════════════════════════════════════════════════════════════════
# WAITER-COURSING — per-line course override + initial fired_course at PLACEMENT
# ═══════════════════════════════════════════════════════════════════════════════

class PlacementCourseOverrideTests(SimpleTestCase):
    """Verify PlaceOrderView honors a per-line `course` override + initial
    `fired_course`, and that omitting both preserves today's behavior exactly.
    """

    def setUp(self):
        from menu.views import PlaceOrderView
        self.factory = APIRequestFactory()
        self.view = PlaceOrderView.as_view()

    def _run_place(self, items, extra_body=None, category_course=2):
        """Drive PlaceOrderView to OrderItem.create with fully-mocked deps.
        Returns (resp, item_create_mock, order_create_mock).
        """
        dish = _make_dish(slug="steak", name="Steak", price=Decimal("50.00"),
                          category_course=category_course, pk=5)

        body = {
            "items": items,
            "fulfillment_type": "table",
            "table_slug": "t1",
            "customer_name": "Bob",
        }
        if extra_body:
            body.update(extra_body)

        tenant = _tenant()
        plan = MagicMock()
        plan.can_checkout = True
        plan.can_whatsapp_order = False
        tenant.plan = plan

        with patch("menu.views.RecipeLine"), \
             patch("menu.views.OrderItem.objects") as item_om, \
             patch("menu.views.Dish.objects") as dish_om, \
             patch("menu.views.DishOption.objects") as dish_opt, \
             patch("menu.views.transaction") as tx_mock, \
             patch("menu.views.Order.objects") as order_om, \
             patch("menu.views.Profile.objects") as profile_om, \
             patch("menu.views.Promotion.objects") as promo_om, \
             patch("menu.views.LoyaltyConfig.objects") as lc_om, \
             patch("menu.views.get_all_active_hh_rules", return_value=[]), \
             patch("menu.views._generate_order_number", return_value="ORD-TEST"), \
             patch("menu.views.TableLink.objects") as tl_om:

            profile = MagicMock()
            profile.is_menu_published = True
            profile.is_menu_temporarily_disabled = False
            profile.is_ordering_enabled = True
            profile.is_open = True
            profile.business_hours_schedule = {}
            profile.capabilities = {}
            profile.lat = None
            profile.lng = None
            profile_om.filter.return_value.first.return_value = profile

            dish_om.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]
            dish_om.select_for_update.return_value.filter.return_value = []
            dish_opt.filter.return_value.select_related.return_value = []
            promo_om.filter.return_value = []
            lc_om.filter.return_value.first.return_value = None

            class _FakeAtomic:
                def __enter__(self): return self
                def __exit__(self, *a): return False

            tx_mock.atomic.return_value = _FakeAtomic()

            created_order = _make_order()
            order_om.create.return_value = created_order
            item_om.create = MagicMock()

            tl = MagicMock()
            tl.label = "T1"
            tl_om.filter.return_value.first.return_value = tl

            req = self.factory.post("/api/place-order/", body, format="json")
            u = _user()
            u.tenant_id = tenant.id
            force_authenticate(req, user=u)
            req.tenant = tenant
            req.session = {}
            resp = self.view(req, order_id=None)

        return resp, item_om.create, order_om.create

    # ── Per-line override wins over the category snapshot ──────────────────────

    def test_per_line_course_override_wins(self):
        """An explicit per-line course=3 overrides the category snapshot (2)."""
        resp, item_create, _ = self._run_place(
            [{"slug": "steak", "qty": 1, "course": 3}], category_course=2,
        )
        self.assertTrue(item_create.called, getattr(resp, "data", None))
        self.assertEqual(item_create.call_args[1].get("course"), 3)

    def test_per_line_course_zero_override(self):
        """course=0 explicitly forces 'fire immediately' even when category is 2."""
        resp, item_create, _ = self._run_place(
            [{"slug": "steak", "qty": 1, "course": 0}], category_course=2,
        )
        self.assertTrue(item_create.called, getattr(resp, "data", None))
        self.assertEqual(item_create.call_args[1].get("course"), 0)

    # ── DEFAULT-PRESERVING: no override → category snapshot (today's behavior) ─

    def test_default_omitting_course_uses_category_snapshot(self):
        """Omitting course → category snapshot is used (byte-for-byte today)."""
        resp, item_create, _ = self._run_place(
            [{"slug": "steak", "qty": 1}], category_course=2,
        )
        self.assertTrue(item_create.called, getattr(resp, "data", None))
        self.assertEqual(item_create.call_args[1].get("course"), 2)

    # ── Initial fired_course (Send-now / Hold at entry) ────────────────────────

    def test_explicit_fired_course_passed_to_order_create(self):
        """fired_course=4 ('Send now') is passed to Order.objects.create."""
        resp, _, order_create = self._run_place(
            [{"slug": "steak", "qty": 1, "course": 2}],
            extra_body={"fired_course": 4},
        )
        self.assertTrue(order_create.called, getattr(resp, "data", None))
        self.assertEqual(order_create.call_args[1].get("fired_course"), 4)

    def test_default_no_fired_course_kw_when_omitted(self):
        """DEFAULT-PRESERVING: omitting fired_course must NOT pass the kwarg, so the
        model default (1) stands — identical to today."""
        resp, _, order_create = self._run_place(
            [{"slug": "steak", "qty": 1}],
        )
        self.assertTrue(order_create.called, getattr(resp, "data", None))
        self.assertNotIn("fired_course", order_create.call_args[1])

    def test_out_of_range_fired_course_ignored(self):
        """A garbage fired_course (e.g. 9) is ignored — model default stands."""
        resp, _, order_create = self._run_place(
            [{"slug": "steak", "qty": 1}],
            extra_body={"fired_course": 9},
        )
        self.assertTrue(order_create.called, getattr(resp, "data", None))
        self.assertNotIn("fired_course", order_create.call_args[1])

    def test_invalid_per_line_course_rejected_by_serializer(self):
        """course=5 is out of the serializer's 0..4 range → 400 (never reaches create)."""
        resp, item_create, _ = self._run_place(
            [{"slug": "steak", "qty": 1, "course": 5}],
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(item_create.called)


# ═══════════════════════════════════════════════════════════════════════════════
# WAITER-COURSING — per-line course override + send_now on APPEND
# ═══════════════════════════════════════════════════════════════════════════════

class AppendCourseOverrideTests(SimpleTestCase):
    """Verify StaffAppendOrderItemsView honors a per-line `course` override and the
    `send_now` toggle, with the default (omitted) preserving today's behavior.
    """

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffAppendOrderItemsView.as_view()
        _patcher = patch("menu.views._can_access_order", return_value=True)
        self._access_mock = _patcher.start()
        self.addCleanup(_patcher.stop)

    def _run_append(self, body, first_order=None):
        """Drive the append view to OrderItem.create. Returns (resp, item_create, order)."""
        dish = _make_dish(slug="steak", name="Steak", price=Decimal("50.00"),
                          category_course=2, pk=5)
        order = first_order if first_order is not None else _make_order(fired_course=1)
        new_item = _make_item(item_id=902, dish_slug="steak", course=2)
        second_order = _make_order(items=[new_item], fired_course=order.fired_course)

        with patch("menu.views._broadcast_order_change"), \
             patch("menu.views.OrderItem.objects") as item_om, \
             patch("menu.views.DishOption.objects") as option_om, \
             patch("menu.views.Dish.objects") as dish_om, \
             patch("menu.views.transaction") as tx_mock, \
             patch("menu.views.Order.objects") as order_om:

            order_om.prefetch_related.return_value.filter.return_value.first.return_value = order
            order_om.prefetch_related.return_value.get.return_value = second_order

            class _FakeAtomic:
                def __enter__(self): return self
                def __exit__(self, *a): return False

            tx_mock.atomic.return_value = _FakeAtomic()
            dish_om.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]
            dish_om.select_for_update.return_value.filter.return_value = [dish]
            option_om.filter.return_value = []
            item_om.create = MagicMock()

            req = self.factory.post("/api/staff/orders/10/items/", body, format="json")
            force_authenticate(req, user=_user())
            req.tenant = _tenant()
            resp = self.view(req, order_id=10)

        return resp, item_om.create, order

    def test_append_per_line_course_override_wins(self):
        """Per-line course=3 overrides the category snapshot (2) on append."""
        resp, item_create, _ = self._run_append(
            {"items": [{"dish_slug": "steak", "qty": 1, "course": 3}]},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(item_create.call_args[1].get("course"), 3)

    def test_append_default_uses_category_snapshot(self):
        """DEFAULT-PRESERVING: omitting course → category snapshot (2)."""
        resp, item_create, _ = self._run_append(
            {"items": [{"dish_slug": "steak", "qty": 1}]},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(item_create.call_args[1].get("course"), 2)

    def test_append_send_now_bumps_fired_course(self):
        """send_now=True with an appended course-2 item bumps fired_course 1 → 2."""
        order = _make_order(fired_course=1)
        resp, _, order_ref = self._run_append(
            {"items": [{"dish_slug": "steak", "qty": 1, "course": 2}], "send_now": True},
            first_order=order,
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(order_ref.fired_course, 2)

    def test_append_default_hold_does_not_bump_fired_course(self):
        """DEFAULT-PRESERVING: omitting send_now leaves fired_course untouched (held)."""
        order = _make_order(fired_course=1)
        resp, _, order_ref = self._run_append(
            {"items": [{"dish_slug": "steak", "qty": 1, "course": 2}]},
            first_order=order,
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(order_ref.fired_course, 1)

    def test_append_send_now_is_monotonic(self):
        """send_now never lowers an already-higher fired_course (monotonic guard)."""
        order = _make_order(fired_course=3)
        resp, _, order_ref = self._run_append(
            {"items": [{"dish_slug": "steak", "qty": 1, "course": 2}], "send_now": True},
            first_order=order,
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(order_ref.fired_course, 3)
