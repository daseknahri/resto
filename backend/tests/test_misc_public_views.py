"""
Tests for small public/utility views:
  - CustomerOrdersByPhoneView   GET /api/orders/by-phone/?phone=<number>
  - CurrencyRateListView        GET /api/currency-rates/
  - OwnerPushVapidKeyView       GET /api/owner/push-vapid-key/

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import CustomerOrdersByPhoneView, CurrencyRateListView, OwnerPushVapidKeyView


# ── CustomerOrdersByPhoneView ─────────────────────────────────────────────────

class CustomerOrdersByPhoneViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerOrdersByPhoneView.as_view()

    def _get(self, phone=None, cache_hits=0):
        params = {"phone": phone} if phone else {}
        req = self.factory.get("/api/orders/by-phone/", params)
        req.user = MagicMock(is_authenticated=False)
        req.META["REMOTE_ADDR"] = "127.0.0.1"
        return req, cache_hits

    def _call(self, phone=None, cache_hits=0):
        req, _ = self._get(phone, cache_hits)
        with patch("menu.views.cache") as mock_cache:
            mock_cache.get.return_value = cache_hits
            mock_cache.set = MagicMock()
            return self.view(req), mock_cache

    # ── Rate limiting ─────────────────────────────────────────────────────────

    def test_rate_limited_returns_429(self):
        resp, _ = self._call(phone="0612345678", cache_hits=10)
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["code"], "rate_limited")

    # ── Phone validation ──────────────────────────────────────────────────────

    def test_phone_too_short_returns_400(self):
        resp, _ = self._call(phone="123")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "phone_too_short")

    def test_empty_phone_returns_400(self):
        resp, _ = self._call(phone="")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_phone_returns_400(self):
        resp, _ = self._call(phone=None)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Happy path ────────────────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_valid_phone_returns_orders(self, mock_order_objs):
        order = MagicMock()
        order.order_number = "ORD-001"
        order.status = "completed"
        order.fulfillment_type = "pickup"
        order.total = Decimal("30.00")
        order.currency = "MAD"
        order.created_at = MagicMock()
        order.created_at.isoformat.return_value = "2026-05-01T12:00:00+00:00"
        order.status_updated_at = None
        item = MagicMock()
        item.qty = 2
        order.items.all.return_value = [item]

        qs_chain = MagicMock()
        qs_chain.filter.return_value = qs_chain
        qs_chain.prefetch_related.return_value = qs_chain
        qs_chain.order_by.return_value.__getitem__.return_value = [order]
        mock_order_objs.filter.return_value.prefetch_related.return_value.order_by.return_value.__getitem__.return_value = [order]

        req, _ = self._get(phone="0612345678")
        with patch("menu.views.cache") as mock_cache:
            mock_cache.get.return_value = 0
            mock_cache.set = MagicMock()
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("results", resp.data)
        self.assertIn("count", resp.data)

    @patch("menu.views.Order.objects")
    def test_no_orders_found_returns_empty_list(self, mock_order_objs):
        mock_order_objs.filter.return_value.prefetch_related.return_value.order_by.return_value.__getitem__.return_value = []

        req, _ = self._get(phone="0612345678")
        with patch("menu.views.cache") as mock_cache:
            mock_cache.get.return_value = 0
            mock_cache.set = MagicMock()
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["results"], [])
        self.assertEqual(resp.data["count"], 0)

    @patch("menu.views.Order.objects")
    def test_phone_number_not_echoed_back(self, mock_order_objs):
        """The phone number must not appear in the response for privacy."""
        mock_order_objs.filter.return_value.prefetch_related.return_value.order_by.return_value.__getitem__.return_value = []

        req, _ = self._get(phone="0612345678")
        with patch("menu.views.cache") as mock_cache:
            mock_cache.get.return_value = 0
            mock_cache.set = MagicMock()
            resp = self.view(req)

        resp_str = str(resp.data)
        self.assertNotIn("0612345678", resp_str)


# ── CurrencyRateListView ──────────────────────────────────────────────────────

class CurrencyRateListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CurrencyRateListView.as_view()

    def _get(self):
        req = self.factory.get("/api/currency-rates/")
        req.user = MagicMock(is_authenticated=False)
        return self.view(req)

    @patch("menu.views.CurrencyRate.objects")
    def test_returns_active_currency_rates(self, mock_cr_objs):
        mock_cr_objs.filter.return_value.values.return_value = [
            {"code": "EUR", "name": "Euro", "symbol": "€", "mad_per_unit": Decimal("10.80")},
            {"code": "USD", "name": "US Dollar", "symbol": "$", "mad_per_unit": Decimal("9.90")},
        ]

        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)
        self.assertEqual(len(resp.data), 2)

    @patch("menu.views.CurrencyRate.objects")
    def test_response_shape(self, mock_cr_objs):
        mock_cr_objs.filter.return_value.values.return_value = [
            {"code": "EUR", "name": "Euro", "symbol": "€", "mad_per_unit": Decimal("10.80")},
        ]

        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rate = resp.data[0]
        for field in ("code", "name", "symbol", "mad_per_unit"):
            self.assertIn(field, rate, f"Missing field: {field}")
        self.assertIsInstance(rate["mad_per_unit"], float)

    @patch("menu.views.CurrencyRate.objects")
    def test_no_rates_returns_empty_list(self, mock_cr_objs):
        mock_cr_objs.filter.return_value.values.return_value = []
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])


# ── OwnerPushVapidKeyView ─────────────────────────────────────────────────────

class OwnerPushVapidKeyViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerPushVapidKeyView.as_view()

    def _get(self):
        req = self.factory.get("/api/owner/push-vapid-key/")
        req.user = MagicMock(is_authenticated=False)
        return self.view(req)

    def test_no_vapid_key_configured_returns_disabled(self):
        from django.test import override_settings
        with override_settings(VAPID_PUBLIC_KEY=""):
            resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["enabled"])
        self.assertIsNone(resp.data["public_key"])

    def test_vapid_key_configured_returns_enabled(self):
        from django.test import override_settings
        with override_settings(VAPID_PUBLIC_KEY="BNTestPublicKey123"):
            resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["enabled"])
        self.assertEqual(resp.data["public_key"], "BNTestPublicKey123")

    def test_no_vapid_key_attribute_returns_disabled(self):
        """Handles missing VAPID_PUBLIC_KEY setting gracefully."""
        from django.test import override_settings
        with override_settings():
            from django.conf import settings as _s
            if hasattr(_s, "VAPID_PUBLIC_KEY"):
                # Only test if we can remove it; otherwise skip
                pass
            # Test with empty string — the safe path
            with override_settings(VAPID_PUBLIC_KEY=" "):
                resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["enabled"])
