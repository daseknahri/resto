"""
Unit tests for core utility functions:
  - menu/sms.py: _normalize_phone, send_order_ready_sms
  - sales/audit.py: get_request_ip, log_admin_action

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

from django.test import SimpleTestCase

from menu.sms import _normalize_phone, send_order_ready_sms
from sales.audit import get_request_ip, log_admin_action


# ══════════════════════════════════════════════════════════════════════════════
# _normalize_phone
# ══════════════════════════════════════════════════════════════════════════════

class NormalizePhoneTests(SimpleTestCase):
    def test_strips_spaces_and_dashes(self):
        self.assertEqual(_normalize_phone("+33 6 00 00 00 01"), "+33600000001")

    def test_prepends_plus_if_missing(self):
        self.assertEqual(_normalize_phone("33600000001"), "+33600000001")

    def test_returns_empty_for_empty_string(self):
        self.assertEqual(_normalize_phone(""), "")

    def test_returns_empty_for_none(self):
        self.assertEqual(_normalize_phone(None), "")

    def test_returns_empty_for_too_short(self):
        # fewer than 8 chars after stripping → too short
        self.assertEqual(_normalize_phone("+123"), "")

    def test_preserves_leading_plus(self):
        result = _normalize_phone("+212600000001")
        self.assertTrue(result.startswith("+"))

    def test_letters_stripped(self):
        result = _normalize_phone("+abc33600000001def")
        self.assertEqual(result, "+33600000001")


# ══════════════════════════════════════════════════════════════════════════════
# send_order_ready_sms
# ══════════════════════════════════════════════════════════════════════════════

class SendOrderReadySmsTests(SimpleTestCase):
    def test_returns_false_when_no_credentials(self):
        with patch("menu.sms._credentials", return_value=None):
            result = send_order_ready_sms("+33600000001", "Demo", "42")
        self.assertFalse(result)

    def test_returns_false_when_phone_invalid(self):
        with patch("menu.sms._credentials", return_value=("SID", "TOK", "+15550000")):
            result = send_order_ready_sms("not-a-phone", "Demo", "42")
        self.assertFalse(result)

    def test_returns_true_on_twilio_201(self):
        resp = MagicMock()
        resp.status_code = 201
        with patch("menu.sms._credentials", return_value=("SID", "TOK", "+15550000")):
            with patch("requests.post", return_value=resp):
                result = send_order_ready_sms("+33600000001", "Demo", "42")
        self.assertTrue(result)

    def test_returns_true_on_twilio_200(self):
        resp = MagicMock()
        resp.status_code = 200
        with patch("menu.sms._credentials", return_value=("SID", "TOK", "+15550000")):
            with patch("requests.post", return_value=resp):
                result = send_order_ready_sms("+33600000001", "Demo", "42")
        self.assertTrue(result)

    def test_raises_sms_provider_error_on_twilio_error(self):
        from menu.sms import SmsProviderError
        resp = MagicMock()
        resp.status_code = 429
        resp.text = "rate limited"
        with patch("menu.sms._credentials", return_value=("SID", "TOK", "+15550000")):
            with patch("requests.post", return_value=resp):
                with self.assertRaises(SmsProviderError):
                    send_order_ready_sms("+33600000001", "Demo", "42")

    def test_raises_sms_provider_error_on_network_exception(self):
        from menu.sms import SmsProviderError
        with patch("menu.sms._credentials", return_value=("SID", "TOK", "+15550000")):
            with patch("requests.post", side_effect=Exception("timeout")):
                with self.assertRaises(SmsProviderError):
                    send_order_ready_sms("+33600000001", "Demo", "42")

    def test_message_body_includes_order_number_and_tenant(self):
        resp = MagicMock()
        resp.status_code = 201
        with patch("menu.sms._credentials", return_value=("SID", "TOK", "+15550000")):
            with patch("requests.post", return_value=resp) as mock_post:
                send_order_ready_sms("+33600000001", "Bistro Bleu", "99")
        data = mock_post.call_args[1]["data"]
        self.assertIn("99", data["Body"])
        self.assertIn("Bistro Bleu", data["Body"])


# ══════════════════════════════════════════════════════════════════════════════
# get_request_ip
# ══════════════════════════════════════════════════════════════════════════════

class GetRequestIpTests(SimpleTestCase):
    def _req(self, forwarded_for=None, remote_addr=None):
        meta = {}
        if forwarded_for is not None:
            meta["HTTP_X_FORWARDED_FOR"] = forwarded_for
        if remote_addr is not None:
            meta["REMOTE_ADDR"] = remote_addr
        return SimpleNamespace(META=meta)

    def test_returns_rightmost_trusted_ip_from_x_forwarded_for(self):
        """With TRUSTED_PROXY_COUNT=1 (default), return the entry at len-1.

        XFF "203.0.113.1, 10.0.0.1": our proxy appended 10.0.0.1 as the IP
        it received the connection from.  With 1 trusted proxy, idx = 2-1 = 1,
        so we return the proxy-seen IP (10.0.0.1), not the spoofable leading one.
        """
        req = self._req(forwarded_for="203.0.113.1, 10.0.0.1", remote_addr="10.0.0.1")
        self.assertEqual(get_request_ip(req), "10.0.0.1")

    def test_strips_whitespace_from_forwarded_ip(self):
        """Whitespace is stripped; rightmost-trusted entry is returned."""
        req = self._req(forwarded_for="  203.0.113.5  , 10.0.0.1")
        self.assertEqual(get_request_ip(req), "10.0.0.1")

    def test_falls_back_to_remote_addr(self):
        req = self._req(remote_addr="192.168.1.42")
        self.assertEqual(get_request_ip(req), "192.168.1.42")

    def test_returns_none_when_no_ip_info(self):
        req = self._req()
        self.assertIsNone(get_request_ip(req))

    def test_prefers_forwarded_for_over_remote_addr(self):
        req = self._req(forwarded_for="1.2.3.4", remote_addr="5.6.7.8")
        self.assertEqual(get_request_ip(req), "1.2.3.4")


# ══════════════════════════════════════════════════════════════════════════════
# log_admin_action
# ══════════════════════════════════════════════════════════════════════════════

class LogAdminActionTests(SimpleTestCase):
    def _make_request(self, user=None, ip="203.0.113.1"):
        req = SimpleNamespace(
            META={"REMOTE_ADDR": ip},
            user=user or SimpleNamespace(is_authenticated=True, id=1),
        )
        return req

    @patch("sales.audit.AdminAuditLog")
    def test_creates_audit_log_entry(self, AuditLogMock):
        log_admin_action(action="lead_provisioned", target_repr="tenant:demo")
        AuditLogMock.objects.create.assert_called_once()
        kwargs = AuditLogMock.objects.create.call_args[1]
        self.assertEqual(kwargs["action"], "lead_provisioned")
        self.assertEqual(kwargs["target_repr"], "tenant:demo")

    @patch("sales.audit.AdminAuditLog")
    def test_resolves_actor_from_request_user(self, AuditLogMock):
        user = SimpleNamespace(is_authenticated=True, id=7)
        req = self._make_request(user=user)
        log_admin_action(action="test_action", request=req)
        kwargs = AuditLogMock.objects.create.call_args[1]
        self.assertIs(kwargs["actor"], user)

    @patch("sales.audit.AdminAuditLog")
    def test_explicit_actor_overrides_request_user(self, AuditLogMock):
        explicit_actor = SimpleNamespace(is_authenticated=True, id=99)
        user = SimpleNamespace(is_authenticated=True, id=7)
        req = self._make_request(user=user)
        log_admin_action(action="test_action", request=req, actor=explicit_actor)
        kwargs = AuditLogMock.objects.create.call_args[1]
        self.assertIs(kwargs["actor"], explicit_actor)

    @patch("sales.audit.AdminAuditLog")
    def test_unauthenticated_user_not_set_as_actor(self, AuditLogMock):
        user = SimpleNamespace(is_authenticated=False, id=0)
        req = self._make_request(user=user)
        log_admin_action(action="test_action", request=req)
        kwargs = AuditLogMock.objects.create.call_args[1]
        self.assertIsNone(kwargs["actor"])

    @patch("sales.audit.AdminAuditLog")
    def test_ip_address_extracted_from_request(self, AuditLogMock):
        req = self._make_request(ip="203.0.113.99")
        log_admin_action(action="test_action", request=req)
        kwargs = AuditLogMock.objects.create.call_args[1]
        self.assertEqual(kwargs["ip_address"], "203.0.113.99")

    @patch("sales.audit.AdminAuditLog")
    def test_no_request_ip_is_none(self, AuditLogMock):
        log_admin_action(action="test_action")
        kwargs = AuditLogMock.objects.create.call_args[1]
        self.assertIsNone(kwargs["ip_address"])

    @patch("sales.audit.logger")
    @patch("sales.audit.AdminAuditLog")
    def test_does_not_raise_when_create_fails(self, AuditLogMock, logger_mock):
        """log_admin_action swallows exceptions to protect business flow."""
        AuditLogMock.objects.create.side_effect = Exception("db error")
        # Should not raise
        log_admin_action(action="test_action")
        logger_mock.exception.assert_called_once()

    @patch("sales.audit.AdminAuditLog")
    def test_default_metadata_is_empty_dict(self, AuditLogMock):
        log_admin_action(action="test_action")
        kwargs = AuditLogMock.objects.create.call_args[1]
        self.assertEqual(kwargs["metadata"], {})

    @patch("sales.audit.AdminAuditLog")
    def test_custom_metadata_stored(self, AuditLogMock):
        meta = {"status": "success", "reason": "approved"}
        log_admin_action(action="decision_made", metadata=meta)
        kwargs = AuditLogMock.objects.create.call_args[1]
        self.assertEqual(kwargs["metadata"], meta)
