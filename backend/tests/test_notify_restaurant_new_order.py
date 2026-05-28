"""
Unit tests for menu/views._notify_restaurant_new_order.

This function sends a WhatsApp notification to the restaurant via Twilio when
a new order arrives. It must never raise — all errors are swallowed.

All tests are unit-level (SimpleTestCase + mocks — no real DB, no network).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from menu.models import Order
from menu.views import _notify_restaurant_new_order


_CREDS = {
    "TWILIO_ACCOUNT_SID": "ACtest",
    "TWILIO_AUTH_TOKEN": "tok",
    "TWILIO_FROM_NUMBER": "+15550001111",
}


def _item(dish_name="Burger", qty=2, options=None):
    return SimpleNamespace(
        dish_name=dish_name,
        qty=qty,
        options=options or [],
    )


def _order(
    *,
    order_number="ORD-001",
    customer_name="Alice",
    customer_note="",
    total="45.00",
    currency="MAD",
    fulfillment_type=Order.FulfillmentType.PICKUP,
    table_label="",
    items=None,
):
    obj = SimpleNamespace(
        order_number=order_number,
        customer_name=customer_name,
        customer_note=customer_note,
        total=total,
        currency=currency,
        fulfillment_type=fulfillment_type,
        table_label=table_label,
    )
    # Simulate order.items.all() returning a list
    items_qs = MagicMock()
    items_qs.all.return_value = items or []
    obj.items = items_qs
    return obj


class NotifyRestaurantNewOrderTests(SimpleTestCase):

    # ── early exit when credentials are missing ───────────────────────────────
    @override_settings(TWILIO_ACCOUNT_SID="", TWILIO_AUTH_TOKEN="tok", TWILIO_FROM_NUMBER="+1")
    def test_missing_sid_skips_silently(self):
        with patch("urllib.request.urlopen") as mock_url:
            _notify_restaurant_new_order(_order(), "Demo", "+212600000000")
        mock_url.assert_not_called()

    @override_settings(TWILIO_ACCOUNT_SID="ACtest", TWILIO_AUTH_TOKEN="", TWILIO_FROM_NUMBER="+1")
    def test_missing_token_skips_silently(self):
        with patch("urllib.request.urlopen") as mock_url:
            _notify_restaurant_new_order(_order(), "Demo", "+212600000000")
        mock_url.assert_not_called()

    @override_settings(**_CREDS)
    def test_empty_whatsapp_phone_skips_silently(self):
        with patch("urllib.request.urlopen") as mock_url:
            _notify_restaurant_new_order(_order(), "Demo", "")
        mock_url.assert_not_called()

    # ── successful call ───────────────────────────────────────────────────────
    @override_settings(**_CREDS)
    def test_urlopen_called_for_valid_inputs(self):
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=None)
        ctx.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=ctx) as mock_url:
            _notify_restaurant_new_order(_order(), "My Restaurant", "+212600000000")
        mock_url.assert_called_once()

    @override_settings(**_CREDS)
    def test_url_contains_account_sid(self):
        captured = []

        def _fake_urlopen(req, timeout=None):
            captured.append(req.full_url)
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=None)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
            _notify_restaurant_new_order(_order(), "My Restaurant", "+212600000000")

        self.assertTrue(len(captured) == 1)
        self.assertIn("ACtest", captured[0])

    # ── body content ──────────────────────────────────────────────────────────
    @override_settings(**_CREDS)
    def test_body_contains_order_number(self):
        payload_bodies = []

        def _capture(req, timeout=None):
            import urllib.parse
            payload_bodies.append(urllib.parse.unquote_plus(req.data.decode()))
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=None)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        with patch("urllib.request.urlopen", side_effect=_capture):
            _notify_restaurant_new_order(
                _order(order_number="ORD-TEST99"), "Demo", "+212600000000"
            )

        self.assertTrue(any("ORD-TEST99" in b for b in payload_bodies))

    @override_settings(**_CREDS)
    def test_body_contains_tenant_name(self):
        payload_bodies = []

        def _capture(req, timeout=None):
            import urllib.parse
            payload_bodies.append(urllib.parse.unquote_plus(req.data.decode()))
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=None)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        with patch("urllib.request.urlopen", side_effect=_capture):
            _notify_restaurant_new_order(_order(), "Fantastic Bistro", "+212600000000")

        self.assertTrue(any("Fantastic Bistro" in b for b in payload_bodies))

    # ── fulfillment label ─────────────────────────────────────────────────────
    @override_settings(**_CREDS)
    def test_table_fulfillment_shows_table_label(self):
        payload_bodies = []

        def _capture(req, timeout=None):
            import urllib.parse
            payload_bodies.append(urllib.parse.unquote_plus(req.data.decode()))
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=None)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        with patch("urllib.request.urlopen", side_effect=_capture):
            _notify_restaurant_new_order(
                _order(fulfillment_type=Order.FulfillmentType.TABLE, table_label="T5"),
                "Demo",
                "+212600000000",
            )

        self.assertTrue(any("Table T5" in b for b in payload_bodies))

    @override_settings(**_CREDS)
    def test_delivery_fulfillment_shows_delivery(self):
        payload_bodies = []

        def _capture(req, timeout=None):
            import urllib.parse
            payload_bodies.append(urllib.parse.unquote_plus(req.data.decode()))
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=None)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        with patch("urllib.request.urlopen", side_effect=_capture):
            _notify_restaurant_new_order(
                _order(fulfillment_type=Order.FulfillmentType.DELIVERY),
                "Demo",
                "+212600000000",
            )

        self.assertTrue(any("Delivery" in b for b in payload_bodies))

    # ── exception swallowed ───────────────────────────────────────────────────
    @override_settings(**_CREDS)
    def test_network_error_does_not_raise(self):
        """Errors must be swallowed so the order flow is not affected."""
        with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
            _notify_restaurant_new_order(_order(), "Demo", "+212600000000")  # no raise

    @override_settings(**_CREDS)
    def test_unexpected_exception_does_not_raise(self):
        with patch("urllib.request.urlopen", side_effect=RuntimeError("boom")):
            _notify_restaurant_new_order(_order(), "Demo", "+212600000000")

    # ── phone normalisation ───────────────────────────────────────────────────
    @override_settings(**_CREDS)
    def test_phone_without_plus_gets_prefixed(self):
        """WhatsApp `To` value must start with 'whatsapp:+...'."""
        payload_bodies = []

        def _capture(req, timeout=None):
            import urllib.parse
            payload_bodies.append(urllib.parse.unquote_plus(req.data.decode()))
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=None)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        with patch("urllib.request.urlopen", side_effect=_capture):
            _notify_restaurant_new_order(_order(), "Demo", "212600000000")  # no leading +

        self.assertTrue(any("whatsapp:+212600000000" in b for b in payload_bodies))
