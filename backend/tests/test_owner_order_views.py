"""
Tests for the owner-facing order management views:
  - OwnerOrderListView       GET  /api/owner/orders/
  - OwnerOrderDetailView     GET  /api/owner/orders/<id>/
  - OwnerOrderStatusUpdateView  PATCH /api/owner/orders/<id>/status/

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import (
    OwnerOrderListView,
    OwnerOrderDetailView,
    OwnerOrderStatusUpdateView,
)
from accounts.models import User


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user(role=User.Roles.TENANT_OWNER, tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = role
    u.tenant_id = tenant_id
    return u


def _tenant(tenant_id=1):
    return SimpleNamespace(id=tenant_id, name="Test Restaurant")


def _make_order(
    order_id=1,
    number="ORD001",
    order_status="pending",
    fulfillment_type="table",
    table_label="Table 3",
    table_slug="table-3",
    customer_name="Ali",
    customer_phone="0612345678",
    customer_note="extra sauce",
    owner_note="",
    delivery_address="",
    delivery_location_url="",
    delivery_lat=None,
    delivery_lng=None,
    estimated_ready_minutes=None,
    total="25.00",
    currency="MAD",
    created_at_iso="2026-05-15T10:00:00+00:00",
    updated_at_iso="2026-05-15T10:00:00+00:00",
    status_updated_at_iso=None,
    customer=None,
):
    item = MagicMock()
    item.id = 10
    item.dish_name = "Pizza"
    item.dish_slug = "pizza"
    item.qty = 2
    item.unit_price = Decimal("12.50")
    item.subtotal = Decimal("25.00")
    item.options = []
    item.note = ""

    items_qs = MagicMock()
    items_qs.all.return_value = [item]

    order = MagicMock()
    order.id = order_id
    order.order_number = number
    order.status = order_status
    order.fulfillment_type = fulfillment_type
    order.table_label = table_label
    order.table_slug = table_slug
    order.customer_name = customer_name
    order.customer_phone = customer_phone
    order.customer_note = customer_note
    order.owner_note = owner_note
    order.delivery_address = delivery_address
    order.delivery_location_url = delivery_location_url
    order.delivery_lat = delivery_lat
    order.delivery_lng = delivery_lng
    order.estimated_ready_minutes = estimated_ready_minutes
    order.total = Decimal(total)
    order.currency = currency
    order.customer = customer

    order.created_at = MagicMock()
    order.created_at.isoformat.return_value = created_at_iso
    order.updated_at = MagicMock()
    order.updated_at.isoformat.return_value = updated_at_iso

    if status_updated_at_iso:
        order.status_updated_at = MagicMock()
        order.status_updated_at.isoformat.return_value = status_updated_at_iso
    else:
        order.status_updated_at = None

    order.items = items_qs
    order.customer_id = None
    order.wallet_amount_paid = Decimal("0")
    return order


def _anon():
    u = MagicMock()
    u.is_authenticated = False
    return u


# ═══════════════════════════════════════════════════════════════════════════════
# OwnerOrderListView — GET /api/owner/orders/
# ═══════════════════════════════════════════════════════════════════════════════

class OwnerOrderListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerOrderListView.as_view()

    def _get(self, user=None, tenant=None, params=None):
        req = self.factory.get("/api/owner/orders/", params or {})
        req.user = user or _user()
        req.tenant = tenant or _tenant()
        return self.view(req)

    # ── Auth / permission ──────────────────────────────────────────────────────

    def test_unauthenticated_returns_403(self):
        req = self.factory.get("/api/owner/orders/")
        req.user = _anon()
        req.tenant = _tenant()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_tenant_staff_returns_403(self):
        user = _user(role=User.Roles.TENANT_STAFF, tenant_id=99)
        resp = self._get(user=user, tenant=_tenant(tenant_id=1))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Happy path ─────────────────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_owner_gets_200_with_results_shape(self, objects_mock):
        order = _make_order()
        qs_mock = MagicMock()
        qs_mock.count.return_value = 1
        qs_mock.__iter__ = lambda s: iter([order])
        qs_mock.__getitem__ = lambda s, sl: [order]
        objects_mock.select_related.return_value.prefetch_related.return_value.order_by.return_value = qs_mock

        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("results", resp.data)
        self.assertIn("count", resp.data)
        self.assertEqual(resp.data["count"], 1)

    @patch("menu.views.Order.objects")
    def test_staff_can_access_owner_list(self, objects_mock):
        qs_mock = MagicMock()
        qs_mock.count.return_value = 0
        qs_mock.__iter__ = lambda s: iter([])
        qs_mock.__getitem__ = lambda s, sl: []
        objects_mock.select_related.return_value.prefetch_related.return_value.order_by.return_value = qs_mock

        resp = self._get(user=_user(role=User.Roles.TENANT_STAFF))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    @patch("menu.views.Order.objects")
    def test_response_includes_delivery_fields(self, objects_mock):
        """Owner list must include delivery_address, delivery_lat/lng, customer_email."""
        order = _make_order(
            delivery_address="5 Rue de Paris",
            delivery_lat=33.99,
            delivery_lng=-6.85,
        )
        qs_mock = MagicMock()
        qs_mock.count.return_value = 1
        qs_mock.__iter__ = lambda s: iter([order])
        qs_mock.__getitem__ = lambda s, sl: [order]
        objects_mock.select_related.return_value.prefetch_related.return_value.order_by.return_value = qs_mock

        resp = self._get()
        result = resp.data["results"][0]
        for present_field in ("delivery_address", "delivery_lat", "delivery_lng", "customer_email"):
            self.assertIn(present_field, result)
        self.assertEqual(result["delivery_address"], "5 Rue de Paris")

    @patch("menu.views.Order.objects")
    def test_status_filter_applied_when_valid(self, objects_mock):
        qs_base = MagicMock()
        qs_filtered = MagicMock()
        qs_filtered.count.return_value = 0
        qs_filtered.__iter__ = lambda s: iter([])
        qs_filtered.__getitem__ = lambda s, sl: []
        objects_mock.select_related.return_value.prefetch_related.return_value.order_by.return_value = qs_base
        qs_base.filter.return_value = qs_filtered

        self._get(params={"status": "pending"})
        qs_base.filter.assert_called_once_with(status="pending")

    @patch("menu.views.Order.objects")
    def test_invalid_status_filter_ignored(self, objects_mock):
        qs_mock = MagicMock()
        qs_mock.count.return_value = 0
        qs_mock.__iter__ = lambda s: iter([])
        qs_mock.__getitem__ = lambda s, sl: []
        objects_mock.select_related.return_value.prefetch_related.return_value.order_by.return_value = qs_mock

        resp = self._get(params={"status": "not-a-status"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # secondary .filter() should NOT have been called with the invalid value
        qs_mock.filter.assert_not_called()

    @patch("menu.views.Order.objects")
    def test_orders_sorted_newest_first(self, objects_mock):
        qs_mock = MagicMock()
        qs_mock.count.return_value = 0
        qs_mock.__iter__ = lambda s: iter([])
        qs_mock.__getitem__ = lambda s, sl: []
        objects_mock.select_related.return_value.prefetch_related.return_value.order_by.return_value = qs_mock

        self._get()
        order_by_arg = objects_mock.select_related.return_value.prefetch_related.return_value.order_by.call_args[0][0]
        self.assertEqual(order_by_arg, "-created_at")


# ═══════════════════════════════════════════════════════════════════════════════
# OwnerOrderDetailView — GET /api/owner/orders/<id>/
# ═══════════════════════════════════════════════════════════════════════════════

class OwnerOrderDetailViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerOrderDetailView.as_view()

    def _get(self, order_id=1, user=None, tenant=None):
        req = self.factory.get(f"/api/owner/orders/{order_id}/")
        req.user = user or _user()
        req.tenant = tenant or _tenant()
        return self.view(req, order_id=order_id)

    def test_unauthenticated_returns_403(self):
        req = self.factory.get("/api/owner/orders/1/")
        req.user = _anon()
        req.tenant = _tenant()
        resp = self.view(req, order_id=1)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("menu.views.Order.objects")
    def test_not_found_returns_404(self, objects_mock):
        objects_mock.select_related.return_value.prefetch_related.return_value.filter.return_value.first.return_value = None
        resp = self._get(order_id=999)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("menu.views.Order.objects")
    def test_found_returns_full_detail_shape(self, objects_mock):
        order = _make_order(status_updated_at_iso="2026-05-15T10:05:00+00:00")
        objects_mock.select_related.return_value.prefetch_related.return_value.filter.return_value.first.return_value = order

        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in (
            "id", "order_number", "status", "fulfillment_type",
            "table_label", "table_slug",
            "customer_name", "customer_phone", "customer_email", "customer_note",
            "delivery_address", "delivery_location_url", "delivery_lat", "delivery_lng",
            "total", "currency", "owner_note", "estimated_ready_minutes",
            "items", "created_at", "updated_at", "status_updated_at",
        ):
            self.assertIn(field, resp.data, f"Missing field: {field}")

    @patch("menu.views.Order.objects")
    def test_status_updated_at_none_when_not_set(self, objects_mock):
        order = _make_order(status_updated_at_iso=None)
        objects_mock.select_related.return_value.prefetch_related.return_value.filter.return_value.first.return_value = order

        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp.data["status_updated_at"])

    @patch("menu.views.Order.objects")
    def test_items_include_id_and_prices(self, objects_mock):
        order = _make_order()
        objects_mock.select_related.return_value.prefetch_related.return_value.filter.return_value.first.return_value = order

        resp = self._get()
        self.assertEqual(len(resp.data["items"]), 1)
        item = resp.data["items"][0]
        for field in ("id", "dish_name", "dish_slug", "qty", "unit_price", "subtotal"):
            self.assertIn(field, item)


# ═══════════════════════════════════════════════════════════════════════════════
# OwnerOrderStatusUpdateView — PATCH /api/owner/orders/<id>/status/
# ═══════════════════════════════════════════════════════════════════════════════

class OwnerOrderStatusUpdateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerOrderStatusUpdateView.as_view()

    def _patch(self, order_id=1, data=None, user=None, tenant=None):
        req = self.factory.patch(
            f"/api/owner/orders/{order_id}/status/",
            data or {},
            format="json",
        )
        req.user = user or _user()
        req.tenant = tenant or _tenant()
        return self.view(req, order_id=order_id)

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_unauthenticated_returns_403(self):
        req = self.factory.patch("/api/owner/orders/1/status/", {}, format="json")
        req.user = _anon()
        req.tenant = _tenant()
        resp = self.view(req, order_id=1)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("menu.views.Order.objects")
    def test_not_found_returns_404(self, objects_mock):
        objects_mock.select_related.return_value.filter.return_value.first.return_value = None
        resp = self._patch(order_id=999, data={"status": "confirmed"})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ── Valid transitions ─────────────────────────────────────────────────────

    @patch("menu.views.timezone")
    @patch("menu.views.Order.objects")
    def test_pending_to_confirmed_succeeds(self, objects_mock, tz_mock):
        order = _make_order(order_status="pending")
        objects_mock.select_related.return_value.filter.return_value.first.return_value = order

        resp = self._patch(data={"status": "confirmed"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "confirmed")
        order.save.assert_called_once()

    @patch("menu.views.timezone")
    @patch("menu.views.Order.objects")
    def test_status_change_records_handler(self, objects_mock, tz_mock):
        """The user who advances an unattributed (customer-placed) order is recorded."""
        order = _make_order(order_status="pending")
        order.handled_by_user_id = None  # customer-placed order, not yet handled
        objects_mock.select_related.return_value.filter.return_value.first.return_value = order
        user = _user()
        user.id = 7

        resp = self._patch(data={"status": "confirmed"}, user=user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(order.handled_by_user_id, 7)
        _, kwargs = order.save.call_args
        self.assertIn("handled_by_user_id", kwargs["update_fields"])

    @patch("menu.views.timezone")
    @patch("menu.views.Order.objects")
    def test_status_change_preserves_existing_handler(self, objects_mock, tz_mock):
        """The waiter who took the order keeps credit when someone else advances it."""
        order = _make_order(order_status="pending")
        order.handled_by_user_id = 3  # original taker
        objects_mock.select_related.return_value.filter.return_value.first.return_value = order
        user = _user()
        user.id = 7

        resp = self._patch(data={"status": "confirmed"}, user=user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(order.handled_by_user_id, 3)  # unchanged
        _, kwargs = order.save.call_args
        self.assertNotIn("handled_by_user_id", kwargs["update_fields"])

    @patch("menu.views.timezone")
    @patch("menu.views.Order.objects")
    def test_confirmed_to_preparing_succeeds(self, objects_mock, tz_mock):
        order = _make_order(order_status="confirmed")
        objects_mock.select_related.return_value.filter.return_value.first.return_value = order

        resp = self._patch(data={"status": "preparing"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "preparing")

    @patch("menu.views.timezone")
    @patch("menu.views.Order.objects")
    def test_preparing_to_ready_succeeds(self, objects_mock, tz_mock):
        order = _make_order(order_status="preparing")
        objects_mock.select_related.return_value.filter.return_value.first.return_value = order

        resp = self._patch(data={"status": "ready"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "ready")

    @patch("menu.views.timezone")
    @patch("menu.views.Order.objects")
    def test_ready_to_completed_succeeds(self, objects_mock, tz_mock):
        order = _make_order(order_status="ready")
        objects_mock.select_related.return_value.filter.return_value.first.return_value = order

        resp = self._patch(data={"status": "completed"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "completed")

    @patch("menu.views.timezone")
    @patch("menu.views.Order.objects")
    def test_any_active_status_can_be_cancelled(self, objects_mock, tz_mock):
        for current in ("pending", "confirmed", "preparing", "ready"):
            order = _make_order(order_status=current)
            objects_mock.select_related.return_value.filter.return_value.first.return_value = order
            resp = self._patch(data={"status": "cancelled"})
            self.assertEqual(resp.status_code, status.HTTP_200_OK, f"Cancel from '{current}' failed")

    # ── Invalid transitions ───────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_invalid_transition_returns_400(self, objects_mock):
        order = _make_order(order_status="pending")
        objects_mock.select_related.return_value.filter.return_value.first.return_value = order

        resp = self._patch(data={"status": "completed"})  # pending → completed not allowed
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_transition")

    @patch("menu.views.Order.objects")
    def test_completed_order_cannot_change_status(self, objects_mock):
        order = _make_order(order_status="completed")
        objects_mock.select_related.return_value.filter.return_value.first.return_value = order

        resp = self._patch(data={"status": "pending"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_transition")

    @patch("menu.views.Order.objects")
    def test_cancelled_order_cannot_change_status(self, objects_mock):
        order = _make_order(order_status="cancelled")
        objects_mock.select_related.return_value.filter.return_value.first.return_value = order

        resp = self._patch(data={"status": "pending"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_transition")

    # ── Side-channel updates ──────────────────────────────────────────────────

    @patch("menu.views.timezone")
    @patch("menu.views.Order.objects")
    def test_owner_note_updated_without_status_change(self, objects_mock, tz_mock):
        order = _make_order(order_status="pending", owner_note="")
        objects_mock.select_related.return_value.filter.return_value.first.return_value = order

        resp = self._patch(data={"owner_note": "Allergy: nuts"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(order.owner_note, "Allergy: nuts")
        order.save.assert_called_once()

    @patch("menu.views.timezone")
    @patch("menu.views.Order.objects")
    def test_estimated_ready_minutes_updated(self, objects_mock, tz_mock):
        order = _make_order(order_status="confirmed")
        objects_mock.select_related.return_value.filter.return_value.first.return_value = order

        resp = self._patch(data={"estimated_ready_minutes": 15})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(order.estimated_ready_minutes, 15)

    @patch("menu.views.timezone")
    @patch("menu.views.Order.objects")
    def test_invalid_estimated_ready_minutes_sets_none(self, objects_mock, tz_mock):
        order = _make_order(order_status="confirmed")
        objects_mock.select_related.return_value.filter.return_value.first.return_value = order

        resp = self._patch(data={"estimated_ready_minutes": "bad"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(order.estimated_ready_minutes)

    @patch("menu.views.timezone")
    @patch("menu.views.Order.objects")
    def test_staff_can_update_status(self, objects_mock, tz_mock):
        order = _make_order(order_status="pending")
        objects_mock.select_related.return_value.filter.return_value.first.return_value = order

        resp = self._patch(
            data={"status": "confirmed"},
            user=_user(role=User.Roles.TENANT_STAFF),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    # ── Order status email notifications ──────────────────────────────────────

    @patch("menu.views.send_mail")
    @patch("menu.views.timezone")
    @patch("menu.views.Order.objects")
    def test_email_sent_on_confirmed(self, objects_mock, tz_mock, send_mail_mock):
        customer = MagicMock()
        customer.email = "customer@example.com"
        order = _make_order(order_status="pending", customer=customer)
        objects_mock.select_related.return_value.filter.return_value.first.return_value = order

        self._patch(data={"status": "confirmed"})

        send_mail_mock.assert_called_once()
        call_kwargs = send_mail_mock.call_args
        self.assertIn("customer@example.com", call_kwargs[1]["recipient_list"])
        self.assertIn("ORD001", call_kwargs[1]["subject"])

    @patch("menu.views.send_mail")
    @patch("menu.views.timezone")
    @patch("menu.views.Order.objects")
    def test_email_sent_on_ready(self, objects_mock, tz_mock, send_mail_mock):
        customer = MagicMock()
        customer.email = "customer@example.com"
        order = _make_order(order_status="preparing", customer=customer)
        objects_mock.select_related.return_value.filter.return_value.first.return_value = order

        self._patch(data={"status": "ready"})

        send_mail_mock.assert_called_once()

    @patch("menu.views.send_mail")
    @patch("menu.views.timezone")
    @patch("menu.views.Order.objects")
    def test_email_sent_on_cancelled(self, objects_mock, tz_mock, send_mail_mock):
        customer = MagicMock()
        customer.email = "customer@example.com"
        order = _make_order(order_status="pending", customer=customer)
        objects_mock.select_related.return_value.filter.return_value.first.return_value = order

        self._patch(data={"status": "cancelled"})

        send_mail_mock.assert_called_once()

    @patch("menu.views.send_mail")
    @patch("menu.views.timezone")
    @patch("menu.views.Order.objects")
    def test_no_email_when_no_customer_account(self, objects_mock, tz_mock, send_mail_mock):
        order = _make_order(order_status="pending", customer=None)
        objects_mock.select_related.return_value.filter.return_value.first.return_value = order

        self._patch(data={"status": "confirmed"})

        send_mail_mock.assert_not_called()

    @patch("menu.views.send_mail")
    @patch("menu.views.timezone")
    @patch("menu.views.Order.objects")
    def test_no_email_on_completed(self, objects_mock, tz_mock, send_mail_mock):
        """'completed' status does not trigger a customer email."""
        customer = MagicMock()
        customer.email = "customer@example.com"
        order = _make_order(order_status="ready", customer=customer)
        objects_mock.select_related.return_value.filter.return_value.first.return_value = order

        self._patch(data={"status": "completed"})

        send_mail_mock.assert_not_called()
