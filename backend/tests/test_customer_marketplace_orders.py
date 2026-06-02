"""Tests for CustomerMarketplaceOrdersView (cross-restaurant order history). No-DB."""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import CustomerMarketplaceOrdersView


class CustomerMarketplaceOrdersViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerMarketplaceOrdersView.as_view()

    def _get(self, session=None):
        req = self.factory.get("/api/customer/orders/all/")
        req.session = session if session is not None else {}
        return self.view(req)

    def test_no_session_returns_empty(self):
        resp = self._get(session={})
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
            resp = self._get(session={"customer_id": 5})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)
        row = resp.data["orders"][0]
        self.assertEqual(row["restaurant_name"], "Pizza Place")
        self.assertEqual(row["restaurant_slug"], "pizza-place")
        self.assertEqual(row["order_number"], "ORD-AAA")
        self.assertEqual(row["total"], "85.00")
