"""
Tests for accounts.push.send_review_request_sync — the post-order review nudge.

Unit-level (SimpleTestCase + mocks — no real DB, no real Web Push).
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from accounts.push import send_review_request_sync


def _sub(sid=1):
    s = MagicMock()
    s.id = sid
    s.endpoint = f"https://push.example/{sid}"
    s.p256dh = "p256dh"
    s.auth = "auth"
    return s


class SendReviewRequestSyncTests(SimpleTestCase):
    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    def test_no_subscriptions_returns_zero(self, cust_m, sub_m, _sc):
        cust_m.objects.filter.return_value.first.return_value = MagicMock(locale="en")
        sub_m.objects.filter.return_value = []
        self.assertEqual(send_review_request_sync(42, "Resto", "ORD-1"), 0)

    @patch("menu.push._send_one", return_value="ok")
    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    def test_sends_to_each_sub_and_deep_links_to_order(self, cust_m, sub_m, _sc, send_one_m):
        cust_m.objects.filter.return_value.first.return_value = MagicMock(locale="en")
        sub_m.objects.filter.return_value = [_sub(1), _sub(2)]
        n = send_review_request_sync(42, "Bella Pizza", "ORD-9")
        self.assertEqual(n, 2)
        # _send_one(endpoint, p256dh, auth, title, body, url) — url deep-links to the order page
        args = send_one_m.call_args[0]
        self.assertEqual(args[5], "/orders/ORD-9")
        self.assertIn("Bella Pizza", args[3])  # restaurant name in title

    @patch("menu.push._send_one", return_value="ok")
    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    def test_unknown_locale_falls_back_to_english(self, cust_m, sub_m, _sc, send_one_m):
        cust_m.objects.filter.return_value.first.return_value = MagicMock(locale="zz")
        sub_m.objects.filter.return_value = [_sub(1)]
        self.assertEqual(send_review_request_sync(42, "Resto", "ORD-3"), 1)
        title = send_one_m.call_args[0][3]
        self.assertTrue(title.startswith("How was"))  # English copy

    @patch("menu.push._send_one", return_value="gone")
    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    def test_expired_subscription_is_pruned(self, cust_m, sub_m, _sc, send_one_m):
        cust_m.objects.filter.return_value.first.return_value = MagicMock(locale="en")
        qs = MagicMock()
        qs.__iter__.return_value = iter([_sub(7)])
        sub_m.objects.filter.return_value = qs
        n = send_review_request_sync(42, "Resto", "ORD-4")
        self.assertEqual(n, 0)  # "gone" is not counted as delivered
        qs.delete.assert_called_once()  # the dead subscription was deleted
