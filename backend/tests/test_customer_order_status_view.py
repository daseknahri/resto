"""
Tests for CustomerOrderStatusView — GET /api/order-status/<order_number>/

Covers: anonymous access (no auth required), not-found, full payload shape,
terminal statuses (completed/cancelled), null status_updated_at, items detail.

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import CustomerOrderStatusView


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_order(
    order_number="ORD123",
    order_status="pending",
    fulfillment_type="pickup",
    table_label="",
    customer_name="Sara",
    delivery_address="",
    delivery_location_url="",
    total="30.00",
    currency="MAD",
    owner_note="",
    estimated_ready_minutes=None,
    created_at_iso="2026-05-15T12:00:00+00:00",
    status_updated_at_iso=None,
):
    item = MagicMock()
    item.dish_slug = "margherita"
    item.dish_name = "Margherita"
    item.qty = 2
    item.unit_price = Decimal("15.00")
    item.subtotal = Decimal("30.00")
    item.options = []
    item.note = ""

    items_qs = MagicMock()
    items_qs.all.return_value = [item]

    order = MagicMock()
    order.order_number = order_number
    order.status = order_status
    order.fulfillment_type = fulfillment_type
    order.table_label = table_label
    order.customer_name = customer_name
    order.delivery_address = delivery_address
    order.delivery_location_url = delivery_location_url
    order.total = Decimal(total)
    order.currency = currency
    order.owner_note = owner_note
    order.estimated_ready_minutes = estimated_ready_minutes
    order.items = items_qs

    order.created_at = MagicMock()
    order.created_at.isoformat.return_value = created_at_iso

    if status_updated_at_iso:
        order.status_updated_at = MagicMock()
        order.status_updated_at.isoformat.return_value = status_updated_at_iso
    else:
        order.status_updated_at = None

    # Explicitly set to None so getattr(order, "rating", None) returns None
    # (MagicMock would otherwise auto-create a truthy MagicMock for any attribute)
    order.rating = None

    return order


class CustomerOrderStatusViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerOrderStatusView.as_view()

    def _get(self, order_number="ORD123"):
        """No authentication — the view is public (AllowAny)."""
        req = self.factory.get(f"/api/order-status/{order_number}/")
        # No req.user assignment needed — AllowAny
        return self.view(req, order_number=order_number)

    # ── Not found ─────────────────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_unknown_order_number_returns_404(self, objects_mock):
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = None
        resp = self._get(order_number="NOPE")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "not_found")

    # ── Payload shape ─────────────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_found_order_returns_200_with_full_shape(self, objects_mock):
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = _make_order()
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in (
            "order_number", "status", "fulfillment_type", "table_label",
            "customer_name", "delivery_address",
            "total", "currency", "owner_note", "estimated_ready_minutes",
            "items_count", "items", "created_at", "status_updated_at",
            "has_rating", "rating",
        ):
            self.assertIn(field, resp.data, f"Missing field: {field}")

    @patch("menu.views.Order.objects")
    def test_items_count_matches_qty_sum(self, objects_mock):
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = _make_order()
        resp = self._get()
        self.assertEqual(resp.data["items_count"], 2)  # qty=2 in the fixture
        self.assertEqual(len(resp.data["items"]), 1)

    @patch("menu.views.Order.objects")
    def test_item_shape_includes_prices(self, objects_mock):
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = _make_order()
        resp = self._get()
        item = resp.data["items"][0]
        for field in ("dish_slug", "dish_name", "qty", "unit_price", "subtotal", "currency", "options", "note"):
            self.assertIn(field, item, f"Missing item field: {field}")
        # Prices must be strings (JSON-safe decimals)
        self.assertIsInstance(item["unit_price"], str)
        self.assertIsInstance(item["subtotal"], str)

    @patch("menu.views.Order.objects")
    def test_status_updated_at_is_none_when_not_set(self, objects_mock):
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = _make_order(
            status_updated_at_iso=None
        )
        resp = self._get()
        self.assertIsNone(resp.data["status_updated_at"])

    @patch("menu.views.Order.objects")
    def test_status_updated_at_populated_when_set(self, objects_mock):
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = _make_order(
            status_updated_at_iso="2026-05-15T12:10:00+00:00"
        )
        resp = self._get()
        self.assertEqual(resp.data["status_updated_at"], "2026-05-15T12:10:00+00:00")

    # ── Terminal statuses ─────────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_completed_order_is_visible(self, objects_mock):
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = _make_order(
            order_status="completed"
        )
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "completed")

    @patch("menu.views.Order.objects")
    def test_cancelled_order_is_visible(self, objects_mock):
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = _make_order(
            order_status="cancelled"
        )
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "cancelled")

    # ── Lookup is case-insensitive (uppercase normalisation) ──────────────────

    @patch("menu.views.Order.objects")
    def test_order_number_uppercased_before_lookup(self, objects_mock):
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = None
        self._get(order_number="ord123")
        # The view should have queried with the uppercased version
        filter_kwargs = objects_mock.filter.call_args[1]
        self.assertEqual(filter_kwargs.get("order_number"), "ORD123")

    # ── No sensitive owner/delivery data leaks ────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_customer_phone_not_in_response(self, objects_mock):
        order = _make_order()
        order.customer_phone = "0612345678"
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = order
        resp = self._get()
        self.assertNotIn("customer_phone", resp.data)

    @patch("menu.views.Order.objects")
    def test_customer_email_not_in_response(self, objects_mock):
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = _make_order()
        resp = self._get()
        self.assertNotIn("customer_email", resp.data)
