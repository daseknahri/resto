"""
Unit tests for menu/sms.py private helpers:
  - _credentials()
  - _normalize_phone()

All tests are unit-level (SimpleTestCase + unittest.mock.patch — no real DB,
no network calls, no Twilio dependency).
"""
from unittest.mock import patch

from django.test import SimpleTestCase

from menu.sms import _credentials, _normalize_phone


# ══════════════════════════════════════════════════════════════════════════════
# _credentials
# ══════════════════════════════════════════════════════════════════════════════

class CredentialsTests(SimpleTestCase):
    """_credentials reads three env vars; returns a 3-tuple or None."""

    def _patch(self, sid="", token="", from_num=""):
        return patch.dict(
            "os.environ",
            {
                "TWILIO_ACCOUNT_SID": sid,
                "TWILIO_AUTH_TOKEN": token,
                "TWILIO_FROM_NUMBER": from_num,
            },
            clear=False,
        )

    def test_all_set_returns_tuple(self):
        with self._patch("ACxxx", "tok123", "+1555000"):
            result = _credentials()
        self.assertEqual(result, ("ACxxx", "tok123", "+1555000"))

    def test_missing_sid_returns_none(self):
        with self._patch(sid="", token="tok", from_num="+1"):
            self.assertIsNone(_credentials())

    def test_missing_token_returns_none(self):
        with self._patch(sid="ACxxx", token="", from_num="+1"):
            self.assertIsNone(_credentials())

    def test_missing_from_number_returns_none(self):
        with self._patch(sid="ACxxx", token="tok", from_num=""):
            self.assertIsNone(_credentials())

    def test_all_missing_returns_none(self):
        with self._patch():
            self.assertIsNone(_credentials())

    def test_whitespace_only_sid_returns_none(self):
        with self._patch(sid="   ", token="tok", from_num="+1"):
            self.assertIsNone(_credentials())

    def test_whitespace_stripped_from_values(self):
        """Leading/trailing whitespace is stripped before returning."""
        with self._patch(sid="  ACxxx  ", token="  tok  ", from_num="  +1555  "):
            result = _credentials()
        self.assertEqual(result, ("ACxxx", "tok", "+1555"))

    def test_unset_env_var_treated_as_missing(self):
        """Ensure env vars not present at all (removed) → None."""
        env = {"TWILIO_ACCOUNT_SID": "ACxxx", "TWILIO_AUTH_TOKEN": "tok"}
        # Explicitly remove TWILIO_FROM_NUMBER if it exists
        with patch("os.environ", {k: v for k, v in env.items()}):
            self.assertIsNone(_credentials())


# ══════════════════════════════════════════════════════════════════════════════
# _normalize_phone
# ══════════════════════════════════════════════════════════════════════════════

class NormalizePhoneTests(SimpleTestCase):
    """_normalize_phone strips non-digit/non-'+' chars, ensures '+' prefix,
    returns '' for empty or too-short results."""

    # ── empty / None input ────────────────────────────────────────────────────
    def test_none_returns_empty(self):
        self.assertEqual(_normalize_phone(None), "")  # type: ignore[arg-type]

    def test_empty_string_returns_empty(self):
        self.assertEqual(_normalize_phone(""), "")

    def test_only_spaces_returns_empty(self):
        self.assertEqual(_normalize_phone("   "), "")

    def test_only_dashes_returns_empty(self):
        self.assertEqual(_normalize_phone("---"), "")

    # ── too-short results ─────────────────────────────────────────────────────
    def test_six_digits_returns_empty(self):
        """Fewer than 8 chars (incl. '+') → empty string."""
        self.assertEqual(_normalize_phone("123456"), "")

    def test_seven_chars_with_plus_returns_empty(self):
        """'+' + 6 digits = 7 chars < 8 → empty string."""
        self.assertEqual(_normalize_phone("+123456"), "")

    # ── valid normalisation ───────────────────────────────────────────────────
    def test_plus_prefixed_number_returned_unchanged(self):
        self.assertEqual(_normalize_phone("+212600000000"), "+212600000000")

    def test_digits_only_gets_plus_prefix(self):
        self.assertEqual(_normalize_phone("212600000000"), "+212600000000")

    def test_spaces_stripped(self):
        self.assertEqual(_normalize_phone("+212 600 000 000"), "+212600000000")

    def test_dashes_stripped(self):
        self.assertEqual(_normalize_phone("+212-600-000-000"), "+212600000000")

    def test_mixed_spaces_and_dashes_stripped(self):
        self.assertEqual(_normalize_phone("0 6-00-00-00-00"), "+0600000000")

    def test_parentheses_stripped(self):
        """Parentheses are not digits or '+' → stripped."""
        self.assertEqual(_normalize_phone("(0600) 000000"), "+0600000000")

    def test_exactly_eight_chars_accepted(self):
        """Boundary: '+' + 7 digits = 8 chars → accepted."""
        self.assertEqual(_normalize_phone("+1234567"), "+1234567")

    def test_preserves_multiple_plus_signs_as_is(self):
        """Multiple '+' are kept because '+' passes the filter; result is still
        returned if total length >= 8.  The function does not validate E.164."""
        result = _normalize_phone("++1234567")
        # Must be at least 8 chars to not be discarded
        self.assertGreaterEqual(len(result), 8)

    def test_letters_stripped_entirely(self):
        """Letters are filtered out; only digits and '+' survive."""
        self.assertEqual(_normalize_phone("ABC12345678"), "+12345678")


# ══════════════════════════════════════════════════════════════════════════════
# send_sms — generic transactional sender (best-effort, never raises)
# ══════════════════════════════════════════════════════════════════════════════

class SendSmsTests(SimpleTestCase):
    """menu.sms.send_sms: generic body, non-raising, records every outcome."""

    @patch("accounts.notifications.record_notification")
    @patch("menu.sms._credentials", return_value=None)
    def test_no_credentials_returns_false_and_records_skipped(self, _creds, mock_rec):
        from menu.sms import send_sms
        ok = send_sms("+212600000000", "hi", event="recipient.track.dispatched", reference="9")
        self.assertFalse(ok)
        self.assertEqual(mock_rec.call_args.kwargs["status"], "skipped")
        self.assertEqual(mock_rec.call_args.kwargs["event"], "recipient.track.dispatched")

    @patch("accounts.notifications.record_notification")
    @patch("menu.sms._credentials", return_value=("AC", "tok", "+1555"))
    def test_invalid_phone_returns_false_and_records_skipped(self, _creds, mock_rec):
        from menu.sms import send_sms
        ok = send_sms("123", "hi", event="recipient.track.dispatched")
        self.assertFalse(ok)
        self.assertEqual(mock_rec.call_args.kwargs["status"], "skipped")

    @patch("accounts.notifications.record_notification")
    @patch("menu.sms._credentials", return_value=("AC", "tok", "+1555"))
    def test_success_posts_body_and_returns_true(self, _creds, mock_rec):
        from menu.sms import send_sms
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            ok = send_sms("+212600000000", "track: https://x/track/abc",
                          event="recipient.track.dispatched", reference="9")
        self.assertTrue(ok)
        # body forwarded verbatim to Twilio
        self.assertEqual(mock_post.call_args.kwargs["data"]["Body"], "track: https://x/track/abc")
        self.assertEqual(mock_rec.call_args.kwargs["status"], "sent")

    @patch("accounts.notifications.record_notification")
    @patch("menu.sms._credentials", return_value=("AC", "tok", "+1555"))
    def test_transient_failure_returns_false_without_raising(self, _creds, mock_rec):
        """Unlike send_order_ready_sms, send_sms swallows provider errors (no retry)."""
        from menu.sms import send_sms
        with patch("requests.post", side_effect=RuntimeError("network down")):
            ok = send_sms("+212600000000", "hi", event="recipient.track.in_progress")
        self.assertFalse(ok)
        self.assertEqual(mock_rec.call_args.kwargs["status"], "failed")
