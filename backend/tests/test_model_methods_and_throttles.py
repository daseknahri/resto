"""
Tests for:
  - accounts.throttles._IPThrottle.get_cache_key  (+ concrete subclasses)
  - menu.throttles._IPThrottle.get_cache_key  (+ concrete subclasses)
  - accounts.models.PasswordResetToken.is_valid / mark_used
  - sales.models.ActivationToken.is_valid / mark_used
  - sales.models.ProvisioningJob.append_log

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

from django.test import SimpleTestCase
from django.utils import timezone

from accounts.throttles import (
    _IPThrottle as AccountsIPThrottle,
    LoginBurstThrottle,
    LoginSustainedThrottle,
    ActivationThrottle,
    PasswordResetRequestThrottle,
    PasswordResetConfirmThrottle,
    CustomerOtpRequestThrottle,
)
from menu.throttles import (
    _IPThrottle as MenuIPThrottle,
    OrderHandoffThrottle,
    CheckoutIntentThrottle,
    PlaceOrderThrottle,
)
from accounts.models import PasswordResetToken
from sales.models import ActivationToken, ProvisioningJob


# ── Helpers ───────────────────────────────────────────────────────────────────

def _request(ip="1.2.3.4"):
    req = SimpleNamespace(META={"REMOTE_ADDR": ip})
    return req


# ══════════════════════════════════════════════════════════════════════════════
# accounts.throttles._IPThrottle.get_cache_key
# ══════════════════════════════════════════════════════════════════════════════

class AccountsIPThrottleGetCacheKeyTests(SimpleTestCase):
    """Direct tests for _IPThrottle.get_cache_key in accounts.throttles."""

    def _throttle_with_scope(self, throttle_class):
        """Return an instance with a real scope and mocked get_ident."""
        t = throttle_class()
        t.get_ident = MagicMock(return_value="1.2.3.4")
        return t

    def test_cache_key_uses_scope_and_ident(self):
        t = self._throttle_with_scope(LoginBurstThrottle)
        key = t.get_cache_key(_request(), view=None)
        self.assertIn("auth_login_burst", key)
        self.assertIn("1.2.3.4", key)

    def test_login_burst_scope(self):
        t = LoginBurstThrottle()
        self.assertEqual(t.scope, "auth_login_burst")

    def test_login_sustained_scope(self):
        t = LoginSustainedThrottle()
        self.assertEqual(t.scope, "auth_login_sustained")

    def test_activation_scope(self):
        t = ActivationThrottle()
        self.assertEqual(t.scope, "auth_activation")

    def test_password_reset_request_scope(self):
        t = PasswordResetRequestThrottle()
        self.assertEqual(t.scope, "auth_password_reset_request")

    def test_password_reset_confirm_scope(self):
        t = PasswordResetConfirmThrottle()
        self.assertEqual(t.scope, "auth_password_reset_confirm")

    def test_get_ident_is_only_a_fallback(self):
        """OPS-5d: accounts _IPThrottle now keys on the trusted-proxy-aware
        get_request_ip (REMOTE_ADDR here), not the spoofable get_ident. get_ident
        is consulted ONLY when get_request_ip returns falsy."""
        t = self._throttle_with_scope(LoginBurstThrottle)
        req = _request("5.6.7.8")
        key = t.get_cache_key(req, view=None)
        t.get_ident.assert_not_called()
        self.assertIn("5.6.7.8", key)

    def test_get_ident_fallback_when_no_remote_addr(self):
        """No REMOTE_ADDR and no XFF → get_request_ip None → fall back to get_ident
        (so the bucket key is never the literal 'None')."""
        t = LoginBurstThrottle()
        t.get_ident = MagicMock(return_value="fallback")
        req = SimpleNamespace(META={})
        key = t.get_cache_key(req, view=None)
        t.get_ident.assert_called_once_with(req)
        self.assertIn("fallback", key)

    def test_different_ips_produce_different_keys(self):
        # Key now derives from get_request_ip (REMOTE_ADDR), so distinct clients
        # must carry distinct REMOTE_ADDR (not merely distinct get_ident mocks).
        t1 = LoginBurstThrottle()
        t2 = LoginBurstThrottle()
        key1 = t1.get_cache_key(_request("10.0.0.1"), view=None)
        key2 = t2.get_cache_key(_request("10.0.0.2"), view=None)
        self.assertNotEqual(key1, key2)

    def test_different_scopes_produce_different_keys(self):
        t1 = LoginBurstThrottle()
        t1.get_ident = MagicMock(return_value="1.2.3.4")
        t2 = LoginSustainedThrottle()
        t2.get_ident = MagicMock(return_value="1.2.3.4")
        key1 = t1.get_cache_key(_request(), view=None)
        key2 = t2.get_cache_key(_request(), view=None)
        self.assertNotEqual(key1, key2)

    def test_customer_otp_scope(self):
        t = CustomerOtpRequestThrottle()
        self.assertEqual(t.scope, "customer_otp_request")


# ══════════════════════════════════════════════════════════════════════════════
# menu.throttles._IPThrottle.get_cache_key
# ══════════════════════════════════════════════════════════════════════════════

class MenuIPThrottleGetCacheKeyTests(SimpleTestCase):
    """Direct tests for _IPThrottle.get_cache_key in menu.throttles."""

    def _throttle_with_scope(self, throttle_class):
        t = throttle_class()
        t.get_ident = MagicMock(return_value="9.9.9.9")
        return t

    def test_cache_key_uses_scope_and_trusted_proxy_ip(self):
        """OPS-5d C: _IPThrottle now keys on get_request_ip (the real client IP
        our proxy saw), not get_ident.  With no XFF, get_request_ip falls back to
        REMOTE_ADDR, so the key embeds REMOTE_ADDR — NOT the mocked get_ident."""
        t = self._throttle_with_scope(OrderHandoffThrottle)
        key = t.get_cache_key(_request("5.5.5.5"), view=None)
        self.assertIn("order_handoff", key)
        self.assertIn("5.5.5.5", key)
        # get_ident must NOT be consulted when get_request_ip yields a value.
        self.assertNotIn("9.9.9.9", key)

    def test_order_handoff_scope(self):
        t = OrderHandoffThrottle()
        self.assertEqual(t.scope, "order_handoff")

    def test_checkout_intent_scope(self):
        t = CheckoutIntentThrottle()
        self.assertEqual(t.scope, "checkout_intent")

    def test_place_order_scope(self):
        t = PlaceOrderThrottle()
        self.assertEqual(t.scope, "place_order")

    def test_get_ident_is_only_a_fallback(self):
        """OPS-5d C: get_ident is consulted ONLY when get_request_ip returns
        falsy (no REMOTE_ADDR, no usable XFF).  When REMOTE_ADDR is present,
        get_request_ip wins and get_ident is never called."""
        t = self._throttle_with_scope(CheckoutIntentThrottle)
        req = _request("2.2.2.2")
        key = t.get_cache_key(req, view=None)
        t.get_ident.assert_not_called()
        self.assertIn("2.2.2.2", key)

    def test_get_ident_fallback_when_no_remote_addr(self):
        """No REMOTE_ADDR and no XFF → get_request_ip returns None → fall back to
        get_ident (so the bucket key is never the literal 'None')."""
        t = CheckoutIntentThrottle()
        t.get_ident = MagicMock(return_value="fallback")
        req = SimpleNamespace(META={})
        key = t.get_cache_key(req, view=None)
        t.get_ident.assert_called_once_with(req)
        self.assertIn("fallback", key)

    def test_different_ips_different_keys(self):
        t1 = PlaceOrderThrottle()
        t1.get_ident = MagicMock(return_value="1.1.1.1")
        t2 = PlaceOrderThrottle()
        t2.get_ident = MagicMock(return_value="2.2.2.2")
        key1 = t1.get_cache_key(_request(), view=None)
        key2 = t2.get_cache_key(_request(), view=None)
        self.assertNotEqual(key1, key2)


# ══════════════════════════════════════════════════════════════════════════════
# accounts.models.PasswordResetToken  — is_valid / mark_used
# ══════════════════════════════════════════════════════════════════════════════

class PasswordResetTokenIsValidTests(SimpleTestCase):
    def _token(self, used_at=None, expires_at=None):
        tok = PasswordResetToken.__new__(PasswordResetToken)
        tok.used_at = used_at
        tok.expires_at = expires_at or (timezone.now() + timedelta(hours=1))
        return tok

    def test_valid_unused_unexpired(self):
        self.assertTrue(self._token().is_valid())

    def test_invalid_when_used(self):
        tok = self._token(used_at=timezone.now() - timedelta(minutes=5))
        self.assertFalse(tok.is_valid())

    def test_invalid_when_expired(self):
        tok = self._token(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertFalse(tok.is_valid())

    def test_invalid_when_used_and_expired(self):
        tok = self._token(
            used_at=timezone.now() - timedelta(hours=2),
            expires_at=timezone.now() - timedelta(hours=1),
        )
        self.assertFalse(tok.is_valid())

    def test_just_expired_is_invalid(self):
        """expires_at == now() should be invalid (strict less-than)."""
        now = timezone.now()
        tok = self._token(expires_at=now - timedelta(microseconds=1))
        self.assertFalse(tok.is_valid())


class PasswordResetTokenMarkUsedTests(SimpleTestCase):
    def _token(self):
        tok = PasswordResetToken.__new__(PasswordResetToken)
        tok.used_at = None
        tok.save = MagicMock()
        return tok

    def test_mark_used_sets_used_at(self):
        tok = self._token()
        before = timezone.now()
        tok.mark_used()
        self.assertIsNotNone(tok.used_at)
        self.assertGreaterEqual(tok.used_at, before)

    def test_mark_used_calls_save_with_correct_fields(self):
        tok = self._token()
        tok.mark_used()
        tok.save.assert_called_once_with(update_fields=["used_at"])

    def test_mark_used_makes_is_valid_false(self):
        tok = self._token()
        tok.expires_at = timezone.now() + timedelta(hours=1)
        tok.save = MagicMock()
        tok.mark_used()
        self.assertFalse(tok.is_valid())


# ══════════════════════════════════════════════════════════════════════════════
# sales.models.ActivationToken — is_valid / mark_used
# ══════════════════════════════════════════════════════════════════════════════

class ActivationTokenIsValidTests(SimpleTestCase):
    def _token(self, used_at=None, expires_at=None):
        tok = ActivationToken.__new__(ActivationToken)
        tok.used_at = used_at
        tok.expires_at = expires_at or (timezone.now() + timedelta(hours=24))
        return tok

    def test_valid_unused_unexpired(self):
        self.assertTrue(self._token().is_valid())

    def test_invalid_when_used(self):
        tok = self._token(used_at=timezone.now() - timedelta(minutes=10))
        self.assertFalse(tok.is_valid())

    def test_invalid_when_expired(self):
        tok = self._token(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertFalse(tok.is_valid())

    def test_invalid_when_both_used_and_expired(self):
        tok = self._token(
            used_at=timezone.now() - timedelta(hours=1),
            expires_at=timezone.now() - timedelta(minutes=30),
        )
        self.assertFalse(tok.is_valid())

    def test_just_expired_is_invalid(self):
        tok = self._token(expires_at=timezone.now() - timedelta(microseconds=1))
        self.assertFalse(tok.is_valid())


class ActivationTokenMarkUsedTests(SimpleTestCase):
    def _token(self):
        tok = ActivationToken.__new__(ActivationToken)
        tok.used_at = None
        tok.expires_at = timezone.now() + timedelta(hours=24)
        tok.save = MagicMock()
        return tok

    def test_mark_used_sets_used_at(self):
        tok = self._token()
        before = timezone.now()
        tok.mark_used()
        self.assertIsNotNone(tok.used_at)
        self.assertGreaterEqual(tok.used_at, before)

    def test_mark_used_calls_save_with_correct_fields(self):
        tok = self._token()
        tok.mark_used()
        tok.save.assert_called_once_with(update_fields=["used_at"])

    def test_mark_used_makes_is_valid_false(self):
        tok = self._token()
        tok.mark_used()
        self.assertFalse(tok.is_valid())


# ══════════════════════════════════════════════════════════════════════════════
# sales.models.ProvisioningJob.append_log
# ══════════════════════════════════════════════════════════════════════════════

class ProvisioningJobAppendLogTests(SimpleTestCase):
    def _job(self, log=""):
        job = ProvisioningJob.__new__(ProvisioningJob)
        job.log = log
        job.save = MagicMock()
        return job

    def test_append_adds_message_to_log(self):
        job = self._job()
        job.append_log("Tenant created")
        self.assertIn("Tenant created", job.log)

    def test_append_includes_timestamp(self):
        job = self._job()
        job.append_log("Step done")
        # ISO timestamp format contains 'T' separator
        self.assertRegex(job.log, r"\d{4}-\d{2}-\d{2}T")

    def test_append_calls_save_with_fields(self):
        job = self._job()
        job.append_log("anything")
        job.save.assert_called_once_with(update_fields=["log", "updated_at"])

    def test_append_multiple_times_accumulates(self):
        job = self._job()
        job.append_log("First")
        job.append_log("Second")
        self.assertIn("First", job.log)
        self.assertIn("Second", job.log)

    def test_append_to_existing_log(self):
        job = self._job(log="[existing] Old entry\n")
        job.append_log("New entry")
        self.assertIn("Old entry", job.log)
        self.assertIn("New entry", job.log)

    def test_none_log_handled(self):
        """log=None (e.g., DB default before first save) should not raise."""
        job = self._job(log=None)
        job.append_log("First message")
        self.assertIn("First message", job.log)

    def test_each_append_ends_with_newline(self):
        job = self._job()
        job.append_log("Final step")
        self.assertTrue(job.log.endswith("\n"))
