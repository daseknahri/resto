"""
Unit tests for accounts/views.py OTP delivery helpers:
  - _send_otp_sms  (Twilio SMS, returns bool)
  - _send_otp      (dispatcher: DEBUG mode / production path)

All tests are unit-level (SimpleTestCase + mocks — no real network calls).
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from accounts.views import _send_otp, _send_otp_sms


# ══════════════════════════════════════════════════════════════════════════════
# _send_otp_sms
# ══════════════════════════════════════════════════════════════════════════════

class SendOtpSmsTests(SimpleTestCase):
    """_send_otp_sms: sends via Twilio stdlib http or returns False on error."""

    _CREDS = {
        "TWILIO_ACCOUNT_SID": "ACtest",
        "TWILIO_AUTH_TOKEN": "tok",
        "TWILIO_FROM_NUMBER": "+1555000",
    }

    # ── credentials missing → False ──────────────────────────────────────────
    @override_settings(TWILIO_ACCOUNT_SID="", TWILIO_AUTH_TOKEN="tok", TWILIO_FROM_NUMBER="+1")
    def test_missing_sid_returns_false(self):
        self.assertFalse(_send_otp_sms("+212600", "123456"))

    @override_settings(TWILIO_ACCOUNT_SID="ACtest", TWILIO_AUTH_TOKEN="", TWILIO_FROM_NUMBER="+1")
    def test_missing_token_returns_false(self):
        self.assertFalse(_send_otp_sms("+212600", "123456"))

    @override_settings(TWILIO_ACCOUNT_SID="ACtest", TWILIO_AUTH_TOKEN="tok", TWILIO_FROM_NUMBER="")
    def test_missing_from_number_returns_false(self):
        self.assertFalse(_send_otp_sms("+212600", "123456"))

    @override_settings(TWILIO_ACCOUNT_SID="", TWILIO_AUTH_TOKEN="", TWILIO_FROM_NUMBER="")
    def test_all_missing_returns_false(self):
        self.assertFalse(_send_otp_sms("+212600", "123456"))

    # ── successful send → True ────────────────────────────────────────────────
    @override_settings(**_CREDS)
    def test_successful_send_returns_true(self):
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=None)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_ctx) as mock_urlopen:
            result = _send_otp_sms("+212600000000", "654321")
        self.assertTrue(result)
        self.assertTrue(mock_urlopen.called)

    # ── exception swallowed → False ───────────────────────────────────────────
    @override_settings(**_CREDS)
    def test_network_error_returns_false(self):
        with patch("urllib.request.urlopen", side_effect=OSError("network error")):
            result = _send_otp_sms("+212600000000", "654321")
        self.assertFalse(result)

    @override_settings(**_CREDS)
    def test_unexpected_exception_returns_false(self):
        with patch("urllib.request.urlopen", side_effect=RuntimeError("unexpected")):
            result = _send_otp_sms("+212600000000", "654321")
        self.assertFalse(result)

    # ── request construction ─────────────────────────────────────────────────
    @override_settings(**_CREDS)
    def test_url_contains_account_sid(self):
        """The Twilio URL is built with the SID."""
        captured = []

        def _fake_urlopen(req, timeout=None):
            captured.append(req.full_url)
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=None)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
            _send_otp_sms("+212600000000", "111222")

        self.assertTrue(len(captured) == 1)
        self.assertIn("ACtest", captured[0])


# ══════════════════════════════════════════════════════════════════════════════
# _send_otp
# ══════════════════════════════════════════════════════════════════════════════

class SendOtpTests(SimpleTestCase):
    """_send_otp: in DEBUG mode just logs; in production calls _send_otp_sms."""

    # ── DEBUG mode ────────────────────────────────────────────────────────────
    @override_settings(DEBUG=True)
    def test_debug_mode_does_not_call_sms(self):
        with patch("accounts.views._send_otp_sms") as mock_sms:
            _send_otp("+212600000000", "123456")
        mock_sms.assert_not_called()

    @override_settings(DEBUG=True)
    def test_debug_mode_logs_code(self):
        with patch("accounts.views.logger") as mock_logger:
            _send_otp("+212600000000", "999888")
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        self.assertIn("999888", str(call_args))

    # ── production mode ───────────────────────────────────────────────────────
    @override_settings(DEBUG=False)
    def test_production_calls_send_otp_sms(self):
        with patch("accounts.views._send_otp_sms", return_value=True) as mock_sms:
            _send_otp("+212600000000", "123456")
        mock_sms.assert_called_once_with("+212600000000", "123456")

    @override_settings(DEBUG=False)
    def test_production_logs_warning_when_sms_fails(self):
        with patch("accounts.views._send_otp_sms", return_value=False):
            with patch("accounts.views.logger") as mock_logger:
                _send_otp("+212600000000", "123456")
        mock_logger.warning.assert_called_once()

    @override_settings(DEBUG=False)
    def test_production_no_warning_when_sms_succeeds(self):
        with patch("accounts.views._send_otp_sms", return_value=True):
            with patch("accounts.views.logger") as mock_logger:
                _send_otp("+212600000000", "123456")
        mock_logger.warning.assert_not_called()

    @override_settings(DEBUG=False)
    def test_short_phone_uses_asterisks_in_warning(self):
        """Phone shorter than 4 chars → '****' in warning, no IndexError."""
        with patch("accounts.views._send_otp_sms", return_value=False):
            with patch("accounts.views.logger") as mock_logger:
                _send_otp("+1", "123456")   # len < 4
        warning_args = str(mock_logger.warning.call_args)
        self.assertIn("****", warning_args)

    @override_settings(DEBUG=False)
    def test_long_phone_shows_last_four_digits_in_warning(self):
        """Phone >= 4 chars → last 4 chars shown in warning."""
        with patch("accounts.views._send_otp_sms", return_value=False):
            with patch("accounts.views.logger") as mock_logger:
                _send_otp("+212600001234", "999")
        warning_args = str(mock_logger.warning.call_args)
        self.assertIn("1234", warning_args)
