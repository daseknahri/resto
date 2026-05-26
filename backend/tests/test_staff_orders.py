"""
Tests for StaffOrderListView — the waiter-facing active-orders endpoint.

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from menu.views import StaffOrderListView
from accounts.models import User


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user(role=User.Roles.TENANT_STAFF, tenant_id=1, **kwargs):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = role
    u.tenant_id = tenant_id
    return u


def _tenant(tenant_id=1):
    return SimpleNamespace(id=tenant_id)


def _make_order(
    order_id=1,
    number="ORD001",
    order_status="pending",
    fulfillment_type="table",
    table_label="Table 5",
    customer_name="",
    customer_note="no onion",
    owner_note="",
    estimated_ready_minutes=None,
    total="45.00",
    currency="MAD",
    created_at="2026-05-15T10:00:00+00:00",
    updated_at="2026-05-15T10:00:00+00:00",
):
    item = SimpleNamespace(
        dish_name="Burger",
        qty=2,
        unit_price="12.50",
        subtotal="25.00",
        options=[],
        note="",
    )
    items_qs = MagicMock()
    items_qs.all.return_value = [item]

    order = MagicMock()
    order.id = order_id
    order.order_number = number
    order.status = order_status
    order.fulfillment_type = fulfillment_type
    order.table_label = table_label
    order.customer_name = customer_name
    order.customer_note = customer_note
    order.owner_note = owner_note
    order.estimated_ready_minutes = estimated_ready_minutes
    order.total = total
    order.currency = currency
    order.created_at = MagicMock()
    order.created_at.isoformat.return_value = created_at
    order.updated_at = MagicMock()
    order.updated_at.isoformat.return_value = updated_at
    order.items = items_qs
    return order


class StaffOrderListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffOrderListView.as_view()

    def _get(self, user=None, tenant=None, params=None):
        req = self.factory.get("/api/staff/orders/", params or {})
        req.user = user or _user()
        req.tenant = tenant or _tenant()
        return self.view(req)

    # ── Auth / permission ──────────────────────────────────────────────────────

    def test_unauthenticated_returns_403(self):
        req = self.factory.get("/api/staff/orders/")
        anon = MagicMock()
        anon.is_authenticated = False
        req.user = anon
        req.tenant = _tenant()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_from_different_tenant_returns_403(self):
        """A staff user whose tenant_id doesn't match request.tenant.id is denied."""
        user = _user(role=User.Roles.TENANT_STAFF, tenant_id=99)
        tenant = _tenant(tenant_id=1)
        resp = self._get(user=user, tenant=tenant)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Happy path ─────────────────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_staff_returns_active_orders(self, objects_mock):
        order = _make_order()
        qs_mock = MagicMock()
        qs_mock.__iter__ = lambda s: iter([order])
        qs_mock.__getitem__ = lambda s, sl: [order]
        objects_mock.filter.return_value.prefetch_related.return_value.order_by.return_value = qs_mock

        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)
        result = resp.data["results"][0]
        self.assertEqual(result["order_number"], "ORD001")
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["table_label"], "Table 5")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["dish_name"], "Burger")
        self.assertEqual(result["items"][0]["qty"], 2)

    @patch("menu.views.Order.objects")
    def test_owner_can_also_access_staff_endpoint(self, objects_mock):
        qs_mock = MagicMock()
        qs_mock.__iter__ = lambda s: iter([])
        qs_mock.__getitem__ = lambda s, sl: []
        objects_mock.filter.return_value.prefetch_related.return_value.order_by.return_value = qs_mock

        owner = _user(role=User.Roles.TENANT_OWNER)
        resp = self._get(user=owner)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    @patch("menu.views.Order.objects")
    def test_response_excludes_delivery_fields(self, objects_mock):
        """Waiter payload must not include delivery_address, delivery_lat/lng, customer_email."""
        order = _make_order()
        qs_mock = MagicMock()
        qs_mock.__iter__ = lambda s: iter([order])
        qs_mock.__getitem__ = lambda s, sl: [order]
        objects_mock.filter.return_value.prefetch_related.return_value.order_by.return_value = qs_mock

        resp = self._get()
        result = resp.data["results"][0]
        for absent_field in ("delivery_address", "delivery_lat", "delivery_lng", "customer_email"):
            self.assertNotIn(absent_field, result, f"Sensitive field '{absent_field}' should not appear in waiter payload")

    # ── since= filtering ───────────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_since_param_filters_queryset(self, objects_mock):
        qs_step1 = MagicMock()
        qs_step2 = MagicMock()
        qs_final = MagicMock()
        qs_final.__iter__ = lambda s: iter([])
        qs_final.__getitem__ = lambda s, sl: []
        objects_mock.filter.return_value.prefetch_related.return_value.order_by.return_value = qs_step1
        qs_step1.filter.return_value = qs_final

        resp = self._get(params={"since": "2026-05-15T09:00:00Z"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # updated_at__gt filter should have been applied
        qs_step1.filter.assert_called_once()
        call_kwargs = qs_step1.filter.call_args[1]
        self.assertIn("updated_at__gt", call_kwargs)

    @patch("menu.views.Order.objects")
    def test_invalid_since_param_is_ignored(self, objects_mock):
        """An unparseable ?since= value must not crash — returns the full list."""
        qs_mock = MagicMock()
        qs_mock.__iter__ = lambda s: iter([])
        qs_mock.__getitem__ = lambda s, sl: []
        objects_mock.filter.return_value.prefetch_related.return_value.order_by.return_value = qs_mock

        resp = self._get(params={"since": "not-a-date"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # No secondary .filter() call — invalid timestamp was silently ignored
        qs_mock.filter.assert_not_called()

    # ── Only active statuses are queried ──────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_queries_only_active_statuses(self, objects_mock):
        qs_mock = MagicMock()
        qs_mock.__iter__ = lambda s: iter([])
        qs_mock.__getitem__ = lambda s, sl: []
        objects_mock.filter.return_value.prefetch_related.return_value.order_by.return_value = qs_mock

        self._get()
        filter_kwargs = objects_mock.filter.call_args[1]
        statuses = set(filter_kwargs.get("status__in", []))
        self.assertIn("pending", statuses)
        self.assertIn("confirmed", statuses)
        self.assertIn("preparing", statuses)
        self.assertIn("ready", statuses)
        self.assertNotIn("completed", statuses)
        self.assertNotIn("cancelled", statuses)
