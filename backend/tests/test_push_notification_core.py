"""
Tests for menu/push.py core functions:
  - _send_one: single subscription delivery
  - _push_to_tenant: batch delivery with expired-subscription cleanup
  - push_new_order: fire-and-forget thread spawning

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

from django.test import SimpleTestCase, override_settings

from menu.push import _send_one, _push_to_tenant, push_new_order


# ══════════════════════════════════════════════════════════════════════════════
# _send_one
# ══════════════════════════════════════════════════════════════════════════════

class SendOneTests(SimpleTestCase):
    ENDPOINT = "https://fcm.example.com/push/abc123"
    P256DH = "BNgTa8xSomeDHKey=="
    AUTH = "secretauth"

    @override_settings(VAPID_PRIVATE_KEY="", VAPID_PUBLIC_KEY="")
    def test_returns_error_when_vapid_keys_not_configured(self):
        result = _send_one(self.ENDPOINT, self.P256DH, self.AUTH, "T", "B", "/")
        self.assertEqual(result, "error")

    @override_settings(VAPID_PRIVATE_KEY="fake-private-key", VAPID_PUBLIC_KEY="fake-public-key")
    def test_returns_ok_on_successful_push(self):
        with patch("pywebpush.webpush") as mock_webpush:
            # webpush doesn't raise → ok
            result = _send_one(self.ENDPOINT, self.P256DH, self.AUTH, "Title", "Body", "/url")
        self.assertEqual(result, "ok")
        mock_webpush.assert_called_once()

    @override_settings(VAPID_PRIVATE_KEY="fake-private-key", VAPID_PUBLIC_KEY="fake-public-key")
    def test_returns_gone_on_http_410(self):
        exc = Exception("expired")
        exc.response = SimpleNamespace(status_code=410)
        with patch("pywebpush.webpush", side_effect=exc):
            result = _send_one(self.ENDPOINT, self.P256DH, self.AUTH, "T", "B", "/")
        self.assertEqual(result, "gone")

    @override_settings(VAPID_PRIVATE_KEY="fake-private-key", VAPID_PUBLIC_KEY="fake-public-key")
    def test_returns_error_on_non_410_exception(self):
        exc = Exception("network error")
        exc.response = SimpleNamespace(status_code=500)
        with patch("pywebpush.webpush", side_effect=exc):
            result = _send_one(self.ENDPOINT, self.P256DH, self.AUTH, "T", "B", "/")
        self.assertEqual(result, "error")

    @override_settings(VAPID_PRIVATE_KEY="fake-private-key", VAPID_PUBLIC_KEY="fake-public-key")
    def test_returns_error_on_exception_without_response(self):
        """Exception with no .response attribute → error (not gone)."""
        with patch("pywebpush.webpush", side_effect=RuntimeError("crash")):
            result = _send_one(self.ENDPOINT, self.P256DH, self.AUTH, "T", "B", "/")
        self.assertEqual(result, "error")

    @override_settings(VAPID_PRIVATE_KEY="fake-private-key", VAPID_PUBLIC_KEY="fake-public-key", VAPID_ADMIN_EMAIL="admin@example.com")
    def test_vapid_claims_use_admin_email(self):
        with patch("pywebpush.webpush") as mock_webpush:
            _send_one(self.ENDPOINT, self.P256DH, self.AUTH, "T", "B", "/")
        kwargs = mock_webpush.call_args[1]
        self.assertIn("mailto:admin@example.com", kwargs["vapid_claims"]["sub"])


# ══════════════════════════════════════════════════════════════════════════════
# _push_to_tenant
# ══════════════════════════════════════════════════════════════════════════════

def _passthrough_cm():
    cm = MagicMock()
    cm.__enter__ = lambda s: None
    cm.__exit__ = lambda s, *a: None
    return cm


def _sub(sub_id=1, endpoint="https://push.example.com/sub1"):
    return SimpleNamespace(id=sub_id, endpoint=endpoint, p256dh="key==", auth="auth==")


class PushToTenantTests(SimpleTestCase):
    def test_no_subs_returns_early_without_sending(self):
        with patch("django_tenants.utils.schema_context", return_value=_passthrough_cm()):
            with patch("menu.models.PushSubscription") as sub_mock:
                sub_mock.objects.all.return_value = []
                with patch("menu.push._send_one") as send_mock:
                    _push_to_tenant("demo", "Title", "Body", "/url")
        send_mock.assert_not_called()

    def test_sends_to_all_subscriptions(self):
        subs = [_sub(1), _sub(2)]
        with patch("django_tenants.utils.schema_context", return_value=_passthrough_cm()):
            with patch("menu.models.PushSubscription") as sub_mock:
                sub_mock.objects.all.return_value = subs
                sub_mock.objects.filter.return_value.delete = MagicMock()
                with patch("menu.push._send_one", return_value="ok") as send_mock:
                    _push_to_tenant("demo", "Title", "Body", "/url")
        self.assertEqual(send_mock.call_count, 2)

    def test_expired_subs_are_deleted(self):
        subs = [_sub(1), _sub(2, "https://push.example.com/expired")]

        def fake_send_one(endpoint, p256dh, auth, title, body, url):
            # Second sub returns 'gone'
            if endpoint == "https://push.example.com/expired":
                return "gone"
            return "ok"

        with patch("django_tenants.utils.schema_context", return_value=_passthrough_cm()):
            with patch("menu.models.PushSubscription") as sub_mock:
                sub_mock.objects.all.return_value = subs
                delete_mock = MagicMock()
                filter_qs = MagicMock()
                filter_qs.delete = delete_mock
                sub_mock.objects.filter.return_value = filter_qs
                with patch("menu.push._send_one", side_effect=fake_send_one):
                    _push_to_tenant("demo", "Title", "Body", "/url")

        # Filter should be called with the gone sub's id
        sub_mock.objects.filter.assert_called_with(id__in=[2])
        delete_mock.assert_called_once()

    def test_no_deletion_when_no_subs_expire(self):
        subs = [_sub(1)]
        with patch("django_tenants.utils.schema_context", return_value=_passthrough_cm()):
            with patch("menu.models.PushSubscription") as sub_mock:
                sub_mock.objects.all.return_value = subs
                with patch("menu.push._send_one", return_value="ok"):
                    _push_to_tenant("demo", "Title", "Body", "/url")
        sub_mock.objects.filter.assert_not_called()

    def test_swallows_exception_gracefully(self):
        with patch("django_tenants.utils.schema_context", side_effect=Exception("db down")):
            # Should not raise
            _push_to_tenant("demo", "Title", "Body", "/url")


# ══════════════════════════════════════════════════════════════════════════════
# push_new_order
# ══════════════════════════════════════════════════════════════════════════════

class PushNewOrderTests(SimpleTestCase):
    """push_new_order now dispatches via the Celery layer (accounts.tasks.enqueue),
    which routes to the worker or falls back to a thread — see test_celery_tasks."""

    @patch("accounts.tasks.enqueue")
    def test_enqueues_web_push_task(self, enqueue):
        from accounts.tasks import web_push_tenant
        push_new_order("demo_schema", "99", "Bob", "120.00", "MAD")
        enqueue.assert_called_once()
        args = enqueue.call_args[0]
        self.assertIs(args[0], web_push_tenant)
        self.assertEqual(args[1], "demo_schema")   # schema_name
        self.assertIn("99", args[2])               # title contains order number
        self.assertIn("Bob", args[3])              # body contains customer name
        self.assertEqual(args[4], "/owner/orders")

    @patch("accounts.tasks.enqueue")
    def test_order_number_in_title(self, enqueue):
        push_new_order("demo", "777", "Alice", "55.00", "EUR")
        self.assertIn("777", enqueue.call_args[0][2])

    @patch("accounts.tasks.enqueue")
    def test_empty_customer_name_falls_back_to_customer(self, enqueue):
        push_new_order("demo", "42", "", "25.00", "EUR")
        self.assertIn("Customer", enqueue.call_args[0][3])
