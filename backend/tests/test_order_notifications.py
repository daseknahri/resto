"""
Tests for owner email notifications triggered by PlaceOrderView and
LeadViewSet (reservation submission).

All unit-level — no real DB, no real SMTP.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

from django.test import SimpleTestCase

from menu.views import _send_owner_new_order_email, _send_owner_new_reservation_email


# ── helpers ───────────────────────────────────────────────────────────────────

def _tenant(tenant_id=1, name="Demo"):
    return SimpleNamespace(id=tenant_id, name=name)


def _make_order(number="ORD001", fulfillment="table", table_label="Table 5",
                customer_name="Ali", customer_phone="0612345678",
                total="45.00", currency="MAD"):
    item = SimpleNamespace(dish_name="Burger", qty=2)
    items_qs = MagicMock()
    items_qs.all.return_value = [item]

    order = MagicMock()
    order.order_number = number
    order.fulfillment_type = fulfillment
    order.table_label = table_label
    order.customer_name = customer_name
    order.customer_phone = customer_phone
    order.total = total
    order.currency = currency
    order.items = items_qs
    return order


def _make_lead(name="Sara", phone="0600000000", email="sara@example.com", notes="Party of 4 at 8pm"):
    lead = MagicMock()
    lead.name = name
    lead.phone = phone
    lead.email = email
    lead.notes = notes
    return lead


# ── _send_owner_new_order_email ───────────────────────────────────────────────

class SendOwnerNewOrderEmailTests(SimpleTestCase):

    @patch("menu.views.send_mail")
    def test_sends_email_to_owner(self, send_mail_mock):
        """Should resolve owner email and call send_mail once."""
        tenant = _tenant()
        order = _make_order()

        with patch("accounts.models.User.objects") as user_mock:
            user_mock.filter.return_value.values_list.return_value.first.return_value = "owner@demo.com"
            _send_owner_new_order_email(tenant, order)

        send_mail_mock.assert_called_once()
        kwargs = send_mail_mock.call_args
        recipient_list = kwargs[1].get("recipient_list") or kwargs[0][3]
        self.assertEqual(recipient_list, ["owner@demo.com"])

    @patch("menu.views.send_mail")
    def test_subject_includes_order_number_and_tenant(self, send_mail_mock):
        with patch("accounts.models.User.objects") as user_mock:
            user_mock.filter.return_value.values_list.return_value.first.return_value = "owner@demo.com"
            _send_owner_new_order_email(_tenant(name="CafeX"), _make_order(number="ORD099"))

        subject = send_mail_mock.call_args[1].get("subject") or send_mail_mock.call_args[0][0]
        self.assertIn("ORD099", subject)
        self.assertIn("CafeX", subject)

    @patch("menu.views.send_mail")
    def test_body_includes_items_and_total(self, send_mail_mock):
        with patch("accounts.models.User.objects") as user_mock:
            user_mock.filter.return_value.values_list.return_value.first.return_value = "owner@demo.com"
            _send_owner_new_order_email(_tenant(), _make_order(total="90.00", currency="MAD"))

        message = send_mail_mock.call_args[1].get("message") or send_mail_mock.call_args[0][1]
        self.assertIn("Burger", message)
        self.assertIn("90.00", message)
        self.assertIn("MAD", message)

    @patch("menu.views.send_mail")
    def test_skips_when_no_owner_email(self, send_mail_mock):
        """If no tenant owner is found, no email is sent."""
        with patch("accounts.models.User.objects") as user_mock:
            user_mock.filter.return_value.values_list.return_value.first.return_value = None
            _send_owner_new_order_email(_tenant(), _make_order())

        send_mail_mock.assert_not_called()

    @patch("menu.views.send_mail", side_effect=Exception("SMTP down"))
    def test_swallows_smtp_exceptions(self, _send_mail_mock):
        """Email errors must never propagate — order creation should always succeed."""
        with patch("accounts.models.User.objects") as user_mock:
            user_mock.filter.return_value.values_list.return_value.first.return_value = "owner@demo.com"
            # Should not raise
            _send_owner_new_order_email(_tenant(), _make_order())


# ── _send_owner_new_reservation_email ────────────────────────────────────────

class SendOwnerNewReservationEmailTests(SimpleTestCase):

    @patch("menu.views.send_mail")
    def test_sends_email_to_owner(self, send_mail_mock):
        with patch("accounts.models.User.objects") as user_mock:
            user_mock.filter.return_value.values_list.return_value.first.return_value = "owner@demo.com"
            _send_owner_new_reservation_email(_tenant(), _make_lead())

        send_mail_mock.assert_called_once()

    @patch("menu.views.send_mail")
    def test_subject_includes_tenant_name(self, send_mail_mock):
        with patch("accounts.models.User.objects") as user_mock:
            user_mock.filter.return_value.values_list.return_value.first.return_value = "owner@demo.com"
            _send_owner_new_reservation_email(_tenant(name="Le Petit Bistro"), _make_lead())

        subject = send_mail_mock.call_args[1].get("subject") or send_mail_mock.call_args[0][0]
        self.assertIn("Le Petit Bistro", subject)

    @patch("menu.views.send_mail")
    def test_body_includes_customer_details(self, send_mail_mock):
        with patch("accounts.models.User.objects") as user_mock:
            user_mock.filter.return_value.values_list.return_value.first.return_value = "owner@demo.com"
            _send_owner_new_reservation_email(
                _tenant(),
                _make_lead(name="Sara", phone="0600000000", notes="Party of 4 at 8pm")
            )

        message = send_mail_mock.call_args[1].get("message") or send_mail_mock.call_args[0][1]
        self.assertIn("Sara", message)
        self.assertIn("0600000000", message)
        self.assertIn("Party of 4", message)

    @patch("menu.views.send_mail")
    def test_skips_when_no_owner_email(self, send_mail_mock):
        with patch("accounts.models.User.objects") as user_mock:
            user_mock.filter.return_value.values_list.return_value.first.return_value = None
            _send_owner_new_reservation_email(_tenant(), _make_lead())

        send_mail_mock.assert_not_called()

    @patch("menu.views.send_mail", side_effect=Exception("network error"))
    def test_swallows_exceptions(self, _send_mail_mock):
        with patch("accounts.models.User.objects") as user_mock:
            user_mock.filter.return_value.values_list.return_value.first.return_value = "owner@demo.com"
            # Must not raise
            _send_owner_new_reservation_email(_tenant(), _make_lead())
