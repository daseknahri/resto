"""
Tests for menu/push.py core functions:
  - _send_one: single subscription delivery
  - _push_to_tenant: batch delivery with expired-subscription cleanup
  - push_new_order: fire-and-forget thread spawning

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
import threading
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
    def test_spawns_daemon_thread(self):
        started_threads = []
        original_start = threading.Thread.start

        class TrackedThread(threading.Thread):
            def start(self):
                started_threads.append(self)
                # Don't actually start to keep test fast

        with patch("menu.push.threading.Thread", TrackedThread):
            with patch("menu.push._push_to_tenant"):
                push_new_order("demo", "42", "Alice", "55.00", "EUR")

        self.assertEqual(len(started_threads), 1)
        self.assertTrue(started_threads[0].daemon)

    def test_thread_target_is_push_to_tenant(self):
        thread_kwargs = {}

        class CapturingThread(threading.Thread):
            def __init__(self, target=None, args=(), daemon=False, **kwargs):
                thread_kwargs["target"] = target
                thread_kwargs["args"] = args
                thread_kwargs["daemon"] = daemon

            def start(self):
                pass

        with patch("menu.push.threading.Thread", CapturingThread):
            push_new_order("demo_schema", "99", "Bob", "120.00", "MAD")

        self.assertIs(thread_kwargs["target"], _push_to_tenant)
        self.assertEqual(thread_kwargs["args"][0], "demo_schema")
        self.assertIn("99", thread_kwargs["args"][1])   # title contains order number
        self.assertIn("Bob", thread_kwargs["args"][2])  # body contains customer name

    def test_order_number_in_title(self):
        thread_kwargs = {}

        class CapturingThread(threading.Thread):
            def __init__(self, target=None, args=(), daemon=False, **kwargs):
                thread_kwargs["args"] = args

            def start(self):
                pass

        with patch("menu.push.threading.Thread", CapturingThread):
            push_new_order("demo", "777", "Alice", "55.00", "EUR")

        title = thread_kwargs["args"][1]
        self.assertIn("777", title)

    def test_empty_customer_name_falls_back_to_customer(self):
        thread_kwargs = {}

        class CapturingThread(threading.Thread):
            def __init__(self, target=None, args=(), daemon=False, **kwargs):
                thread_kwargs["args"] = args

            def start(self):
                pass

        with patch("menu.push.threading.Thread", CapturingThread):
            push_new_order("demo", "42", "", "25.00", "EUR")

        body = thread_kwargs["args"][2]
        self.assertIn("Customer", body)
