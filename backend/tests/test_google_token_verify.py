"""
Unit tests for accounts/views._verify_google_token.

This function calls Google's tokeninfo endpoint and validates the response.
It returns the decoded payload dict on success, None on any failure.

All tests are unit-level (SimpleTestCase + mocks — no real network calls).
"""
import json
import urllib.error
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from accounts.views import _verify_google_token


# ── mock helpers ──────────────────────────────────────────────────────────────

def _urlopen_returning(payload: dict):
    """Context-manager mock for urlopen that returns a JSON-encoded payload."""
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=response)
    ctx.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=ctx)


def _urlopen_raising(exc):
    """urlopen mock that raises the given exception on call."""
    return MagicMock(side_effect=exc)


# ══════════════════════════════════════════════════════════════════════════════
# _verify_google_token
# ══════════════════════════════════════════════════════════════════════════════

class VerifyGoogleTokenTests(SimpleTestCase):
    """_verify_google_token: validates against Google tokeninfo endpoint."""

    # ── successful verification ───────────────────────────────────────────────
    def test_valid_token_no_client_id_returns_payload(self):
        """When client_id is empty, audience check is skipped."""
        payload = {"sub": "1234567890", "email": "user@example.com", "aud": "any-audience"}
        with patch("urllib.request.urlopen", _urlopen_returning(payload)):
            result = _verify_google_token("valid-credential", client_id="")
        self.assertEqual(result, payload)

    def test_valid_token_matching_client_id_returns_payload(self):
        """When client_id is set and matches aud → returns the payload."""
        payload = {"sub": "123", "aud": "my-client-id.apps.googleusercontent.com"}
        with patch("urllib.request.urlopen", _urlopen_returning(payload)):
            result = _verify_google_token("valid-credential", client_id="my-client-id.apps.googleusercontent.com")
        self.assertEqual(result, payload)

    # ── audience mismatch ─────────────────────────────────────────────────────
    def test_mismatched_client_id_returns_none(self):
        """client_id set but aud doesn't match → None."""
        payload = {"sub": "123", "aud": "wrong-client-id"}
        with patch("urllib.request.urlopen", _urlopen_returning(payload)):
            result = _verify_google_token("credential", client_id="expected-client-id")
        self.assertIsNone(result)

    # ── missing sub ───────────────────────────────────────────────────────────
    def test_missing_sub_claim_returns_none(self):
        """Response without a 'sub' field is invalid."""
        payload = {"email": "user@example.com", "aud": "client-id"}
        with patch("urllib.request.urlopen", _urlopen_returning(payload)):
            result = _verify_google_token("credential", client_id="")
        self.assertIsNone(result)

    def test_empty_sub_claim_returns_none(self):
        """Empty 'sub' is treated as missing."""
        payload = {"sub": "", "aud": "client-id"}
        with patch("urllib.request.urlopen", _urlopen_returning(payload)):
            result = _verify_google_token("credential", client_id="")
        self.assertIsNone(result)

    # ── network / parsing errors ──────────────────────────────────────────────
    def test_url_error_returns_none(self):
        with patch("urllib.request.urlopen", _urlopen_raising(urllib.error.URLError("network down"))):
            result = _verify_google_token("credential", client_id="")
        self.assertIsNone(result)

    def test_json_decode_error_returns_none(self):
        """Malformed response body → None (not a crash)."""
        response = MagicMock()
        response.read.return_value = b"not-json"
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=response)
        ctx.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", MagicMock(return_value=ctx)):
            result = _verify_google_token("credential", client_id="")
        self.assertIsNone(result)

    def test_generic_exception_returns_none(self):
        """Any unexpected exception is swallowed."""
        with patch("urllib.request.urlopen", _urlopen_raising(RuntimeError("unexpected"))):
            result = _verify_google_token("credential", client_id="")
        self.assertIsNone(result)

    # ── URL construction ──────────────────────────────────────────────────────
    def test_credential_appears_in_request_url(self):
        """The credential is URL-encoded into the tokeninfo request."""
        payload = {"sub": "abc", "aud": "cid"}
        captured_urls = []

        def _fake_urlopen(url, timeout=None):
            captured_urls.append(url)
            response = MagicMock()
            response.read.return_value = json.dumps(payload).encode()
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=response)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
            _verify_google_token("my-id-token", client_id="")

        self.assertEqual(len(captured_urls), 1)
        self.assertIn("my-id-token", captured_urls[0])
        self.assertIn("tokeninfo", captured_urls[0])
