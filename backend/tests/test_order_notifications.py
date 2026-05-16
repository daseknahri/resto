"""
Tests for owner email notification triggered by LeadViewSet (reservation submission).

All unit-level — no real DB, no real SMTP.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from menu.views import _send_owner_new_reservation_email


# ── helpers ───────────────────────────────────────────────────────────────────

def _tenant(tenant_id=1, name="Demo"):
    return SimpleNamespace(id=tenant_id, name=name)


def _make_lead(name="Sara", phone="0600000000", email="sara@example.com", notes="Party of 4 at 8pm"):
    lead = MagicMock()
    lead.name = name
    lead.phone = phone
    lead.email = email
    lead.notes = notes
    return lead


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
