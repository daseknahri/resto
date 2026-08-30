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
    # PERF: the owner notification is now dispatched off the request thread via
    # accounts.tasks.enqueue(send_transactional_email, subject, message, from, [owner]).
    # enqueue positional args: (task, subject, message, from_email, recipient_list).

    @patch("accounts.tasks.enqueue")
    def test_enqueues_email_to_owner(self, enqueue_mock):
        from accounts.tasks import send_transactional_email
        with patch("accounts.models.User.objects") as user_mock:
            user_mock.filter.return_value.values_list.return_value.first.return_value = "owner@demo.com"
            _send_owner_new_reservation_email(_tenant(), _make_lead())

        enqueue_mock.assert_called_once()
        self.assertIs(enqueue_mock.call_args[0][0], send_transactional_email)
        self.assertIn("owner@demo.com", enqueue_mock.call_args[0][4])

    @patch("accounts.tasks.enqueue")
    def test_subject_includes_tenant_name(self, enqueue_mock):
        with patch("accounts.models.User.objects") as user_mock:
            user_mock.filter.return_value.values_list.return_value.first.return_value = "owner@demo.com"
            _send_owner_new_reservation_email(_tenant(name="Le Petit Bistro"), _make_lead())

        subject = enqueue_mock.call_args[0][1]
        self.assertIn("Le Petit Bistro", subject)

    @patch("accounts.tasks.enqueue")
    def test_body_includes_customer_details(self, enqueue_mock):
        with patch("accounts.models.User.objects") as user_mock:
            user_mock.filter.return_value.values_list.return_value.first.return_value = "owner@demo.com"
            _send_owner_new_reservation_email(
                _tenant(),
                _make_lead(name="Sara", phone="0600000000", notes="Party of 4 at 8pm")
            )

        message = enqueue_mock.call_args[0][2]
        self.assertIn("Sara", message)
        self.assertIn("0600000000", message)
        self.assertIn("Party of 4", message)

    @patch("accounts.tasks.enqueue")
    def test_skips_when_no_owner_email(self, enqueue_mock):
        with patch("accounts.models.User.objects") as user_mock:
            user_mock.filter.return_value.values_list.return_value.first.return_value = None
            _send_owner_new_reservation_email(_tenant(), _make_lead())

        enqueue_mock.assert_not_called()

    @patch("accounts.tasks.enqueue", side_effect=Exception("dispatch error"))
    def test_swallows_exceptions(self, _enqueue_mock):
        with patch("accounts.models.User.objects") as user_mock:
            user_mock.filter.return_value.values_list.return_value.first.return_value = "owner@demo.com"
            # Must not raise even if dispatch blows up
            _send_owner_new_reservation_email(_tenant(), _make_lead())
