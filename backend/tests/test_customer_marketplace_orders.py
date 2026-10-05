"""Tests for CustomerMarketplaceOrdersView (cross-restaurant order history). No-DB.

RISK IDENTITY-1: the view reads the customer via customer_or_none(request.user); it stays
AllowAny, so a signed-out caller still gets an empty list (not a 401). Tests
force_authenticate a real Customer principal for the signed-in path.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer
from accounts.views import CustomerMarketplaceOrdersView


class CustomerMarketplaceOrdersViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerMarketplaceOrdersView.as_view()

    def _get(self, customer=None):
        req = self.factory.get("/api/customer/orders/all/")
        req.session = {}
        if customer is not None:
            force_authenticate(req, user=customer)
        return self.view(req)

    def test_no_session_returns_empty(self):
        resp = self._get(customer=None)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["orders"], [])
        self.assertEqual(resp.data["count"], 0)

    def test_returns_indexed_orders_across_restaurants(self):
        ref = MagicMock()
        ref.order_number = "ORD-AAA"
        ref.restaurant_name = "Pizza Place"
        ref.restaurant_slug = "pizza-place"
        ref.status = "completed"
        ref.fulfillment_type = "delivery"
        ref.total = "85.00"
        ref.currency = "MAD"
        ref.order_created_at = MagicMock()
        ref.order_created_at.isoformat.return_value = "2026-06-01T10:00:00+00:00"

        with patch("accounts.models.CustomerOrderRef") as mock_ref:
            mock_ref.objects.filter.return_value.order_by.return_value.__getitem__ = lambda s, k: [ref]
            resp = self._get(customer=Customer(id=5))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)
        row = resp.data["orders"][0]
        self.assertEqual(row["restaurant_name"], "Pizza Place")
        self.assertEqual(row["restaurant_slug"], "pizza-place")
        self.assertEqual(row["order_number"], "ORD-AAA")
        self.assertEqual(row["total"], "85.00")

    def _ref(self, **overrides):
        ref = MagicMock()
        ref.order_number = "ORD-SCH"
        ref.restaurant_name = "Pizza Place"
        ref.restaurant_slug = "pizza-place"
        ref.status = "scheduled"
        ref.fulfillment_type = "delivery"
        ref.total = "85.00"
        ref.currency = "MAD"
        ref.vertical = "food"
        ref.items_snapshot = []
        ref.order_created_at = MagicMock()
        ref.order_created_at.isoformat.return_value = "2026-06-01T10:00:00+00:00"
        ref.scheduled_for = None
        for k, v in overrides.items():
            setattr(ref, k, v)
        return ref

    def _list(self, ref):
        with patch("accounts.models.CustomerOrderRef") as mock_ref:
            mock_ref.objects.filter.return_value.order_by.return_value.__getitem__ = lambda s, k: [ref]
            return self._get(customer=Customer(id=5))

    def test_scheduled_order_exposes_its_due_time(self):
        """M6: the list can only say when a prepaid advance order is due if the payload
        carries the mirrored scheduled_for."""
        due = MagicMock()
        due.isoformat.return_value = "2026-06-02T19:30:00+00:00"
        resp = self._list(self._ref(scheduled_for=due))
        self.assertEqual(resp.data["orders"][0]["scheduled_for"], "2026-06-02T19:30:00+00:00")

    def test_asap_order_has_null_due_time(self):
        resp = self._list(self._ref(status="pending", scheduled_for=None))
        row = resp.data["orders"][0]
        self.assertIn("scheduled_for", row)
        self.assertIsNone(row["scheduled_for"])
