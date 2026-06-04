"""
Unit tests for menu/views.py _send_order_status_email helper.

This function sends a plain-text status-change notification to the customer.
All tests are unit-level (SimpleTestCase + mocks — no real DB, no real email).
"""
from types import SimpleNamespace
from unittest.mock import call, patch

from django.test import SimpleTestCase

from menu.models import Order
from menu.views import _send_order_status_email


def _order(
    *,
    order_number="ORD-001",
    customer_name="Alice",
    customer_email="alice@example.com",
    estimated_ready_minutes=None,
    fulfillment_type=Order.FulfillmentType.PICKUP,
    owner_note="",
    status=Order.Status.CONFIRMED,
):
    customer = SimpleNamespace(email=customer_email) if customer_email else None
    return SimpleNamespace(
        order_number=order_number,
        customer=customer,
        customer_name=customer_name,
        estimated_ready_minutes=estimated_ready_minutes,
        fulfillment_type=fulfillment_type,
        owner_note=owner_note,
        status=status,
    )


def _tenant(name="Demo Restaurant"):
    return SimpleNamespace(name=name)


class SendOrderStatusEmailTests(SimpleTestCase):

    # ── no customer email → no mail sent ─────────────────────────────────────
    def test_no_customer_returns_early_no_email(self):
        order = _order(customer_email=None)
        order.customer = None
        with patch("menu.views.send_mail") as mock_send:
            _send_order_status_email(order, _tenant(), Order.Status.CONFIRMED)
        mock_send.assert_not_called()

    def test_empty_customer_email_returns_early(self):
        order = _order(customer_email="")
        with patch("menu.views.send_mail") as mock_send:
            _send_order_status_email(order, _tenant(), Order.Status.CONFIRMED)
        mock_send.assert_not_called()

    # ── email is sent to the customer ─────────────────────────────────────────
    def test_email_sent_to_customer_address(self):
        order = _order(customer_email="bob@example.com")
        with patch("menu.views.send_mail") as mock_send:
            _send_order_status_email(order, _tenant(), Order.Status.CONFIRMED)
        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        self.assertIn("bob@example.com", kwargs.get("recipient_list", []))

    def test_subject_contains_order_number_and_tenant(self):
        order = _order(order_number="ORD-XYZ", customer_email="x@example.com")
        with patch("menu.views.send_mail") as mock_send:
            _send_order_status_email(order, _tenant("My Place"), Order.Status.CONFIRMED)
        _, kwargs = mock_send.call_args
        subject = kwargs["subject"]
        self.assertIn("ORD-XYZ", subject)
        self.assertIn("My Place", subject)

    # ── status labels ─────────────────────────────────────────────────────────
    def test_confirmed_status_label_in_body(self):
        order = _order(customer_email="x@example.com")
        with patch("menu.views.send_mail") as mock_send:
            _send_order_status_email(order, _tenant(), Order.Status.CONFIRMED)
        body = mock_send.call_args[1]["message"]
        self.assertIn("confirmed", body)

    def test_preparing_status_label_in_body(self):
        order = _order(customer_email="x@example.com")
        with patch("menu.views.send_mail") as mock_send:
            _send_order_status_email(order, _tenant(), Order.Status.PREPARING)
        body = mock_send.call_args[1]["message"]
        self.assertIn("being prepared", body)

    def test_ready_status_label_in_body(self):
        order = _order(customer_email="x@example.com")
        with patch("menu.views.send_mail") as mock_send:
            _send_order_status_email(order, _tenant(), Order.Status.READY)
        body = mock_send.call_args[1]["message"]
        self.assertIn("ready", body)

    def test_cancelled_status_label_in_body(self):
        order = _order(customer_email="x@example.com")
        with patch("menu.views.send_mail") as mock_send:
            _send_order_status_email(order, _tenant(), Order.Status.CANCELLED)
        body = mock_send.call_args[1]["message"]
        self.assertIn("cancelled", body)

    # ── estimated wait time ───────────────────────────────────────────────────
    def test_confirmed_with_wait_time_shows_minutes(self):
        order = _order(customer_email="x@example.com", estimated_ready_minutes=20)
        with patch("menu.views.send_mail") as mock_send:
            _send_order_status_email(order, _tenant(), Order.Status.CONFIRMED)
        body = mock_send.call_args[1]["message"]
        self.assertIn("20 minutes", body)

    def test_confirmed_without_wait_time_no_minutes_line(self):
        order = _order(customer_email="x@example.com", estimated_ready_minutes=None)
        with patch("menu.views.send_mail") as mock_send:
            _send_order_status_email(order, _tenant(), Order.Status.CONFIRMED)
        body = mock_send.call_args[1]["message"]
        self.assertNotIn("minutes", body)

    # ── ready + fulfillment type ──────────────────────────────────────────────
    def test_ready_delivery_says_dispatched_shortly(self):
        order = _order(
            customer_email="x@example.com",
            fulfillment_type=Order.FulfillmentType.DELIVERY,
        )
        with patch("menu.views.send_mail") as mock_send:
            _send_order_status_email(order, _tenant(), Order.Status.READY)
        body = mock_send.call_args[1]["message"]
        self.assertIn("dispatched", body)

    def test_out_for_delivery_says_on_its_way(self):
        order = _order(
            customer_email="x@example.com",
            fulfillment_type=Order.FulfillmentType.DELIVERY,
        )
        with patch("menu.views.send_mail") as mock_send:
            _send_order_status_email(order, _tenant(), Order.Status.OUT_FOR_DELIVERY)
        body = mock_send.call_args[1]["message"]
        self.assertIn("on its way", body)
        self.assertIn("out for delivery", body)

    def test_ready_pickup_says_ready_for_pickup(self):
        order = _order(
            customer_email="x@example.com",
            fulfillment_type=Order.FulfillmentType.PICKUP,
        )
        with patch("menu.views.send_mail") as mock_send:
            _send_order_status_email(order, _tenant(), Order.Status.READY)
        body = mock_send.call_args[1]["message"]
        self.assertIn("ready for pickup", body)

    def test_ready_table_says_ready(self):
        order = _order(
            customer_email="x@example.com",
            fulfillment_type=Order.FulfillmentType.TABLE,
        )
        with patch("menu.views.send_mail") as mock_send:
            _send_order_status_email(order, _tenant(), Order.Status.READY)
        body = mock_send.call_args[1]["message"]
        # Generic ready line
        self.assertIn("ready", body.lower())

    # ── owner note ────────────────────────────────────────────────────────────
    def test_owner_note_included_in_body(self):
        order = _order(customer_email="x@example.com", owner_note="Extra napkins requested.")
        with patch("menu.views.send_mail") as mock_send:
            _send_order_status_email(order, _tenant(), Order.Status.CONFIRMED)
        body = mock_send.call_args[1]["message"]
        self.assertIn("Extra napkins requested.", body)

    def test_no_owner_note_no_note_line(self):
        order = _order(customer_email="x@example.com", owner_note="")
        with patch("menu.views.send_mail") as mock_send:
            _send_order_status_email(order, _tenant(), Order.Status.CONFIRMED)
        body = mock_send.call_args[1]["message"]
        self.assertNotIn("Note from restaurant", body)

    # ── exceptions are swallowed ──────────────────────────────────────────────
    def test_exception_swallowed_does_not_raise(self):
        order = _order(customer_email="x@example.com")
        with patch("menu.views.send_mail", side_effect=RuntimeError("SMTP down")):
            # Should not raise
            _send_order_status_email(order, _tenant(), Order.Status.CONFIRMED)

    # ── customer name in greeting ─────────────────────────────────────────────
    def test_customer_name_in_greeting(self):
        order = _order(customer_email="x@example.com", customer_name="Bob")
        with patch("menu.views.send_mail") as mock_send:
            _send_order_status_email(order, _tenant(), Order.Status.CONFIRMED)
        body = mock_send.call_args[1]["message"]
        self.assertIn("Bob", body)

    def test_anonymous_customer_says_there(self):
        order = _order(customer_email="x@example.com", customer_name="")
        with patch("menu.views.send_mail") as mock_send:
            _send_order_status_email(order, _tenant(), Order.Status.CONFIRMED)
        body = mock_send.call_args[1]["message"]
        self.assertIn("there", body)
