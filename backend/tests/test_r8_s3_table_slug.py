"""Run 8 S3 follow-up (B-33): the staff order list must carry table_slug.

The waiter board groups orders by slug (B-33); without this field the list
payload only carries table_label, so grouping falls back to the label and two
same-label tables collapse into one group. Mirrors test_staff_orders.py
(SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import StaffOrderListView
from accounts.models import User


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
    table_slug="t1",
    customer_name="",
    total="45.00",
    currency="MAD",
    created_at="2026-05-15T10:00:00+00:00",
    updated_at="2026-05-15T10:00:00+00:00",
):
    item = SimpleNamespace(
        id=901,
        dish_name="Burger",
        qty=2,
        unit_price="12.50",
        subtotal="25.00",
        options=[],
        note="",
        is_ready=False,
        is_voided=False,
        combo_components=[],
    )
    items_qs = MagicMock()
    items_qs.all.return_value = [item]

    order = MagicMock()
    order.id = order_id
    order.order_number = number
    order.status = order_status
    order.payment_status = "unpaid"
    order.fulfillment_type = fulfillment_type
    order.table_label = table_label
    order.table_slug = table_slug
    order.customer_name = customer_name
    order.customer_note = ""
    order.owner_note = ""
    order.estimated_ready_minutes = None
    order.total = total
    order.delivery_fee = "0.00"
    order.wallet_amount_paid = "0.00"
    order.currency = currency
    order.created_at = MagicMock()
    order.created_at.isoformat.return_value = created_at
    order.updated_at = MagicMock()
    order.updated_at.isoformat.return_value = updated_at
    order.items = items_qs
    return order


class StaffOrderListTableSlugTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffOrderListView.as_view()
        # Same stubs as test_staff_orders.py: the section hard-filter delegates
        # to waiter_views, so stub both modules to stay DB-free.
        self._patchers = [
            patch("menu.waiter_views.SectionServer"),
            patch("menu.waiter_views.TableLink"),
            patch("menu.views.TableLink"),
        ]
        wvss, wvtl, vtl = (p.start() for p in self._patchers)
        wvss.objects.filter.return_value.values_list.return_value = []
        wvss.objects.values_list.return_value = []
        wvtl.objects.filter.return_value.values_list.return_value = []
        vtl.objects.filter.return_value.values_list.return_value = []
        vtl.objects.exclude.return_value.values_list.return_value = []

    def tearDown(self):
        for p in self._patchers:
            p.stop()

    def _get(self, user=None, tenant=None, params=None):
        req = self.factory.get("/api/staff/orders/", params or {})
        req.user = user or _user()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def _get_result(self, order):
        with patch("menu.views.Order.objects") as objects_mock:
            qs_mock = MagicMock()
            qs_mock.__iter__ = lambda s: iter([order])
            qs_mock.__getitem__ = lambda s, sl: [order]
            objects_mock.filter.return_value.prefetch_related.return_value.order_by.return_value = qs_mock
            resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)
        return resp.data["results"][0]

    def test_list_includes_table_slug(self):
        result = self._get_result(_make_order(table_slug="t1", table_label="Table 5"))
        self.assertEqual(result["table_slug"], "t1")
        self.assertEqual(result["table_label"], "Table 5")

    def test_list_includes_empty_table_slug_when_unset(self):
        # A table order with no slug assigned yet: the key is still present
        # (empty), so the frontend fallback treats it like a label-only order.
        result = self._get_result(_make_order(table_slug="", table_label="Table 5"))
        self.assertIn("table_slug", result)
        self.assertEqual(result["table_slug"], "")
