"""
Tests for customer notification preferences (Phase 2 — notification preference center):
the profile-update endpoint accepts the opt-outs, and the dispatch paths respect them.

Unit-level (SimpleTestCase + mocks — no real DB).
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import CustomerProfileUpdateView


class ProfileUpdatePrefsTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerProfileUpdateView.as_view()

    @patch("accounts.views.Customer.objects")
    def test_updates_notification_prefs(self, objects_mock):
        cust = MagicMock(pk=5, email="a@b.co", notify_order_updates=True, notify_review_prompts=True)
        objects_mock.get.return_value = cust
        req = self.factory.patch("/api/customer/profile/", {
            "notify_order_updates": False, "notify_review_prompts": False,
        }, format="json")
        req.session = {"customer_id": 5}
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(cust.notify_order_updates)
        self.assertFalse(cust.notify_review_prompts)
        cust.save.assert_called_once()
        # update_fields includes both prefs
        kw = cust.save.call_args.kwargs
        self.assertIn("notify_order_updates", kw["update_fields"])
        self.assertIn("notify_review_prompts", kw["update_fields"])


class EmailRespectsPrefTests(SimpleTestCase):
    @patch("menu.views.send_mail")
    def test_email_skipped_when_opted_out(self, send_mail_mock):
        from menu.views import _send_order_status_email
        from menu.models import Order
        order = MagicMock()
        order.customer = MagicMock(email="a@b.co", notify_order_updates=False)
        _send_order_status_email(order, MagicMock(name="T"), Order.Status.READY)
        send_mail_mock.assert_not_called()

    @patch("menu.views.send_mail")
    def test_email_sent_when_opted_in(self, send_mail_mock):
        from menu.views import _send_order_status_email
        from menu.models import Order
        order = MagicMock()
        order.customer = MagicMock(email="a@b.co", notify_order_updates=True)
        order.customer_name = "Sam"
        order.owner_note = ""
        order.estimated_ready_minutes = None
        order.fulfillment_type = Order.FulfillmentType.PICKUP
        _send_order_status_email(order, MagicMock(), Order.Status.READY)
        send_mail_mock.assert_called_once()


class ReviewPushRespectsPrefTests(SimpleTestCase):
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    @patch("django_tenants.utils.schema_context")
    def test_review_push_skipped_when_opted_out(self, schema_ctx, Cust, Subs):
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=None)
        cm.__exit__ = MagicMock(return_value=False)
        schema_ctx.return_value = cm
        Cust.objects.filter.return_value.first.return_value = MagicMock(notify_review_prompts=False)
        Subs.objects.filter.return_value = [MagicMock()]  # has a subscription, but opted out
        from accounts.push import send_review_request_sync
        sent = send_review_request_sync(7, "Acme", "ORD-1")
        self.assertEqual(sent, 0)
