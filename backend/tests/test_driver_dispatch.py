"""
Tests for driver new-job web-push dispatch (accounts.push.notify_online_drivers_new_job_sync).

Unit-level (SimpleTestCase + mocks — no DB): we mock the public-schema model managers
and the low-level _send_one delivery so we exercise the targeting logic (online + free
drivers only) without a database.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from accounts.push import notify_online_drivers_new_job_sync


def _noop_ctx():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def _sub(customer_id=1, sub_id=10):
    s = MagicMock()
    s.id = sub_id
    s.customer_id = customer_id
    s.endpoint = "https://push.example/endpoint"
    s.p256dh = "p256dh-key"
    s.auth = "auth-key"
    return s


class NotifyOnlineDriversNewJobTests(SimpleTestCase):
    @patch("menu.push._send_one")
    @patch("accounts.models.DeliveryJob")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    @patch("django_tenants.utils.schema_context")
    def test_no_online_drivers_sends_nothing(self, sc_mock, cust_mock, sub_mock, job_mock, send_mock):
        sc_mock.return_value = _noop_ctx()
        cust_mock.objects.filter.return_value.values_list.return_value = []  # no online drivers

        sent = notify_online_drivers_new_job_sync("Demo Diner")

        self.assertEqual(sent, 0)
        send_mock.assert_not_called()

    @patch("menu.push._send_one", return_value="ok")
    @patch("accounts.models.DeliveryJob")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    @patch("django_tenants.utils.schema_context")
    def test_pushes_to_free_online_driver_with_driver_deeplink(self, sc_mock, cust_mock, sub_mock, job_mock, send_mock):
        sc_mock.return_value = _noop_ctx()
        # First values_list → online ids; second → (id, locale) pairs.
        cust_mock.objects.filter.return_value.values_list.side_effect = [[1], [(1, "en")]]
        # No busy drivers.
        job_mock.objects.filter.return_value.values_list.return_value = []
        # One push subscription for the free driver.
        sub_mock.objects.filter.return_value = [_sub(customer_id=1)]

        sent = notify_online_drivers_new_job_sync("Demo Diner")

        self.assertEqual(sent, 1)
        send_mock.assert_called_once()
        # _send_one(endpoint, p256dh, auth, title, body, url) — url must deep-link to /driver.
        self.assertEqual(send_mock.call_args[0][5], "/driver")

    @patch("menu.push._send_one", return_value="ok")
    @patch("accounts.models.DeliveryJob")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    @patch("django_tenants.utils.schema_context")
    def test_busy_driver_is_skipped(self, sc_mock, cust_mock, sub_mock, job_mock, send_mock):
        sc_mock.return_value = _noop_ctx()
        cust_mock.objects.filter.return_value.values_list.side_effect = [[1], []]
        # Driver 1 has an active job → busy → excluded → no free drivers.
        job_mock.objects.filter.return_value.values_list.return_value = [1]

        sent = notify_online_drivers_new_job_sync("Demo Diner")

        self.assertEqual(sent, 0)
        send_mock.assert_not_called()
