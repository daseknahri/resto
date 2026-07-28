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
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer
from menu.views import CustomerOrderStatusView


def _customer(pk=42):
    """A real (unsaved) Customer principal — IsOrderOwner duck-types on class name.

    RISK IDENTITY-1: this view now authenticates via CustomerSessionAuthentication and
    resolves ownership through the shared IsOrderOwner predicate off request.user, so
    tests force-authenticate a principal instead of hand-setting request.session.
    It stays AllowAny: a non-owner (incl. anonymous) still gets the minimal payload.
    """
    c = Customer(id=pk)
    c.save = MagicMock()
    return c


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

    # Default to an anonymous order (no linked customer) so the full-body shape/leak
    # tests below exercise the details path. A bare MagicMock would be TRUTHY and read as
    # an *identified* order, which the ownership gate now (correctly) reduces to a minimal
    # payload for an unauthenticated caller. Tests that need an identified order set
    # order.customer_id explicitly.
    order.customer_id = None

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

    # ── Restaurant feedback (owner→customer) is gated to the order owner ───────

    def _make_cr(self, score=4, note="Reliable customer"):
        cr = MagicMock()
        cr.score = score
        cr.note = note
        cr.created_at.isoformat.return_value = "2026-05-16T10:00:00+00:00"
        return cr

    @patch("menu.views.Order.objects")
    def test_restaurant_feedback_field_always_present(self, objects_mock):
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = _make_order()
        resp = self._get()
        self.assertIn("restaurant_feedback", resp.data)

    @patch("menu.views.Order.objects")
    def test_restaurant_feedback_hidden_for_anonymous_viewer(self, objects_mock):
        """No session → even if a rating exists, it must not be exposed."""
        order = _make_order(order_status="completed")
        order.customer_id = 42
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = order
        resp = self._get()  # no session on the request
        # Identified order + anonymous viewer → minimal payload: the feedback (and the
        # rest of the body) is not present at all, so it can't leak.
        self.assertNotIn("restaurant_feedback", resp.data)
        self.assertNotIn("customer_name", resp.data)

    @patch("accounts.models.CustomerRating")
    @patch("menu.views.Order.objects")
    def test_restaurant_feedback_hidden_for_non_owning_customer(self, objects_mock, cr_mock):
        order = _make_order(order_status="completed")
        order.customer_id = 42
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = order
        cr_mock.objects.filter.return_value.order_by.return_value.first.return_value = self._make_cr()
        req = self.factory.get("/api/order-status/ORD123/")
        force_authenticate(req, user=_customer(99))  # a different customer
        req.tenant = MagicMock(id=7)
        resp = self.view(req, order_number="ORD123")
        # A different customer is a non-owner → minimal payload, nothing to leak.
        self.assertNotIn("restaurant_feedback", resp.data)
        self.assertNotIn("items", resp.data)

    @patch("accounts.models.CustomerRating")
    @patch("menu.views.Order.objects")
    def test_restaurant_feedback_shown_to_owning_customer(self, objects_mock, cr_mock):
        order = _make_order(order_status="completed")
        order.customer_id = 42
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = order
        cr_mock.objects.filter.return_value.order_by.return_value.first.return_value = self._make_cr(score=5, note="Great")
        req = self.factory.get("/api/order-status/ORD123/")
        force_authenticate(req, user=_customer(42))  # the order's owner
        req.tenant = MagicMock(id=7)
        resp = self.view(req, order_number="ORD123")
        fb = resp.data["restaurant_feedback"]
        self.assertIsNotNone(fb)
        self.assertEqual(fb["score"], 5)
        self.assertEqual(fb["note"], "Great")
        self.assertEqual(fb["created_at"], "2026-05-16T10:00:00+00:00")

    # ── IDOR: identified orders are gated; anonymous dine-in tabs are not ──────

    @patch("menu.views.Order.objects")
    def test_identified_order_minimal_for_anonymous_viewer(self, objects_mock):
        """An order with a linked customer must NOT leak its body to an anonymous caller
        who merely guessed the order number — only status/timing/contact come back."""
        order = _make_order(customer_name="Sara", delivery_address="12 Rue X", total="99.00")
        order.customer_id = 42
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = order
        resp = self._get()  # no session
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ("order_number", "status", "fulfillment_type"):
            self.assertIn(field, resp.data)
        for leaked in ("customer_name", "delivery_address", "total", "items",
                       "items_count", "payment_status", "owner_note", "rating"):
            self.assertNotIn(leaked, resp.data, f"leaked {leaked} to anonymous viewer")

    @patch("menu.views.Order.objects")
    def test_identified_order_full_for_owning_customer(self, objects_mock):
        order = _make_order(customer_name="Sara", total="99.00")
        order.customer_id = 42
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = order
        req = self.factory.get("/api/order-status/ORD123/")
        force_authenticate(req, user=_customer(42))  # the owner
        req.tenant = MagicMock(id=7)
        resp = self.view(req, order_number="ORD123")
        self.assertIn("customer_name", resp.data)
        self.assertIn("items", resp.data)
        self.assertEqual(resp.data["total"], "99.00")

    @patch("menu.views.Order.objects")
    def test_anonymous_dinein_order_shows_details(self, objects_mock):
        """A dine-in / cash order with NO linked customer has no account PII to protect,
        and the table-QR viewer needs their bill — so the full body is returned."""
        order = _make_order(fulfillment_type="dine_in", total="45.00")
        order.customer_id = None
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = order
        resp = self._get()
        self.assertIn("items", resp.data)
        self.assertEqual(resp.data["total"], "45.00")
