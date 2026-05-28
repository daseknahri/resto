"""
Unit tests for messaging functions without dedicated coverage:
  accounts.messaging
    - send_otp_email
  sales.messaging
    - send_activation_whatsapp

All tests are unit-level (SimpleTestCase + mocks — no real email/network).
"""
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from accounts.messaging import send_otp_email
from sales.messaging import send_activation_whatsapp


# ══════════════════════════════════════════════════════════════════════════════
# send_otp_email
# ══════════════════════════════════════════════════════════════════════════════

class SendOtpEmailTests(SimpleTestCase):
    """send_otp_email wraps send_mail; returns send count and logs on failure."""

    # ── sends to the correct recipient ───────────────────────────────────────
    @override_settings(EMAIL_FAIL_SILENTLY=True)
    @patch("accounts.messaging.send_mail", return_value=1)
    def test_email_sent_to_recipient(self, mock_send):
        send_otp_email("user@example.com", "998877")
        mock_send.assert_called_once()
        args, _ = mock_send.call_args
        # send_mail(subject, message, from_email, recipient_list, ...)
        self.assertIn("user@example.com", args[3])

    # ── subject contains keyword ──────────────────────────────────────────────
    @override_settings(EMAIL_FAIL_SILENTLY=True)
    @patch("accounts.messaging.send_mail", return_value=1)
    def test_subject_mentions_verification(self, mock_send):
        send_otp_email("user@example.com", "998877")
        args, _ = mock_send.call_args
        self.assertIn("verification", args[0].lower())

    # ── body contains the OTP code ────────────────────────────────────────────
    @override_settings(EMAIL_FAIL_SILENTLY=True)
    @patch("accounts.messaging.send_mail", return_value=1)
    def test_body_contains_otp_code(self, mock_send):
        send_otp_email("user@example.com", "112233")
        args, _ = mock_send.call_args
        self.assertIn("112233", args[1])

    # ── returns the count from send_mail ─────────────────────────────────────
    @override_settings(EMAIL_FAIL_SILENTLY=True)
    @patch("accounts.messaging.send_mail", return_value=1)
    def test_returns_sent_count(self, mock_send):
        result = send_otp_email("user@example.com", "000000")
        self.assertEqual(result, 1)

    # ── fail_silently reflects setting ───────────────────────────────────────
    @override_settings(EMAIL_FAIL_SILENTLY=False)
    @patch("accounts.messaging.send_mail", return_value=1)
    def test_fail_silently_false_respected(self, mock_send):
        send_otp_email("user@example.com", "000000")
        _, kw = mock_send.call_args
        self.assertFalse(kw["fail_silently"])

    @override_settings(EMAIL_FAIL_SILENTLY=True)
    @patch("accounts.messaging.send_mail", return_value=1)
    def test_fail_silently_true_respected(self, mock_send):
        send_otp_email("user@example.com", "000000")
        _, kw = mock_send.call_args
        self.assertTrue(kw["fail_silently"])

    # ── warning logged when not sent ─────────────────────────────────────────
    @override_settings(EMAIL_FAIL_SILENTLY=True)
    @patch("accounts.messaging.logger")
    @patch("accounts.messaging.send_mail", return_value=0)
    def test_logs_warning_when_not_sent(self, mock_send, mock_logger):
        send_otp_email("user@example.com", "000000")
        mock_logger.warning.assert_called_once()

    @override_settings(EMAIL_FAIL_SILENTLY=True)
    @patch("accounts.messaging.logger")
    @patch("accounts.messaging.send_mail", return_value=1)
    def test_no_warning_when_sent_successfully(self, mock_send, mock_logger):
        send_otp_email("user@example.com", "000000")
        mock_logger.warning.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# send_activation_whatsapp
# ══════════════════════════════════════════════════════════════════════════════

class SendActivationWhatsappTests(SimpleTestCase):
    """send_activation_whatsapp builds a wa.me URL — no network calls needed."""

    _URLS = dict(
        workspace_url="https://demo.example.com/owner",
        signin_url="https://demo.example.com/signin",
        activation_url="https://demo.example.com/activate?token=abc",
        onboarding_url="https://demo.example.com/owner/onboarding",
        public_menu_url="https://demo.example.com/menu",
        token="abc",
    )

    def test_empty_phone_returns_empty_string(self):
        result = send_activation_whatsapp("", **self._URLS)
        self.assertEqual(result, "")

    def test_none_phone_returns_empty_string(self):
        result = send_activation_whatsapp(None, **self._URLS)
        self.assertEqual(result, "")

    def test_result_starts_with_wa_me(self):
        result = send_activation_whatsapp("+212600000001", **self._URLS)
        self.assertTrue(result.startswith("https://wa.me/"))

    def test_phone_digits_included_in_url(self):
        result = send_activation_whatsapp("+212600000001", **self._URLS)
        self.assertIn("212600000001", result)

    def test_phone_without_plus_stripped_to_digits(self):
        """Non-digit, non-'+' characters are stripped from the phone number."""
        result = send_activation_whatsapp("0600-00-00-01", **self._URLS)
        # Digits extracted from "0600-00-00-01": "0600000001" (10 digits)
        self.assertIn("0600000001", result)

    def test_result_contains_url_encoded_text_param(self):
        result = send_activation_whatsapp("+212600000001", **self._URLS)
        self.assertIn("?text=", result)

    def test_result_contains_activation_url_encoded(self):
        """The activation URL should appear in the encoded message body."""
        result = send_activation_whatsapp("+212600000001", **self._URLS)
        # URL-encoded '/' → '%2F', ':' → '%3A', etc.
        self.assertIn("activate", result)

    def test_plus_sign_preserved_in_phone(self):
        result = send_activation_whatsapp("+212600000001", **self._URLS)
        # '+' is kept in the sanitized number
        self.assertIn("+212600000001", result)
