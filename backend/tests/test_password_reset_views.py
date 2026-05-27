"""
Tests for password reset views:
  - PasswordResetRequestView   POST /api/auth/password-reset/
  - PasswordResetConfirmView   POST /api/auth/password-reset/confirm/

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import PasswordResetRequestView, PasswordResetConfirmView


# ── Helpers ───────────────────────────────────────────────────────────────────

def _anon():
    u = MagicMock(is_authenticated=False)
    return u


# ── PasswordResetRequestView ──────────────────────────────────────────────────

class PasswordResetRequestViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        # Disable throttling so tests don't interfere with each other
        self._throttle_patcher = patch.object(PasswordResetRequestView, "throttle_classes", [])
        self._throttle_patcher.start()
        self.addCleanup(self._throttle_patcher.stop)
        self.view = PasswordResetRequestView.as_view()

    def _post(self, data):
        req = self.factory.post("/api/auth/password-reset/", data, format="json")
        req.user = _anon()
        return req

    # ── Validation ────────────────────────────────────────────────────────────

    def test_invalid_serializer_returns_400(self):
        """Serializer validation failure (raise_exception=True) → 400."""
        req = self._post({"email": "not-an-email"})
        with patch("accounts.views.PasswordResetRequestSerializer") as mock_ser_cls:
            mock_ser = MagicMock()
            mock_ser.is_valid.side_effect = Exception("validation error")
            mock_ser_cls.return_value = mock_ser
            # DRF raise_exception=True raises a ValidationError that becomes 400
            # but we can test via the serializer's is_valid raising directly
            # Let's instead let is_valid return False and raise_exception do its job
            pass

        # Real test: is_valid with raise_exception=True raises ValidationError → 400
        req = self._post({"email": "not-an-email"})
        with patch("accounts.views.PasswordResetRequestSerializer") as mock_ser_cls:
            from rest_framework.exceptions import ValidationError
            mock_ser = MagicMock()
            mock_ser.is_valid.side_effect = ValidationError({"email": ["Enter a valid email address."]})
            mock_ser_cls.return_value = mock_ser
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Happy path ────────────────────────────────────────────────────────────

    def test_valid_request_returns_200(self):
        """Valid email → 200 with 'detail' key."""
        req = self._post({"email": "user@example.com"})
        reset_obj = MagicMock()
        reset_obj.token = "abc123"
        reset_obj.user = MagicMock()
        reset_obj.user.email = "user@example.com"

        with patch("accounts.views.PasswordResetRequestSerializer") as mock_ser_cls:
            mock_ser = MagicMock()
            mock_ser.is_valid.return_value = True
            mock_ser.save.return_value = reset_obj
            mock_ser_cls.return_value = mock_ser
            with patch("accounts.views.build_frontend_base_url", return_value="http://app.test"):
                with patch("accounts.views.send_password_reset_email"):
                    with patch("accounts.views.settings") as mock_settings:
                        mock_settings.DEBUG = False
                        mock_settings.VAPID_PUBLIC_KEY = ""
                        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("detail", resp.data)

    def test_no_reset_object_returns_200(self):
        """When serializer.save() returns None (account doesn't exist), still 200."""
        req = self._post({"email": "ghost@example.com"})
        with patch("accounts.views.PasswordResetRequestSerializer") as mock_ser_cls:
            mock_ser = MagicMock()
            mock_ser.is_valid.return_value = True
            mock_ser.save.return_value = None
            mock_ser_cls.return_value = mock_ser
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("detail", resp.data)

    def test_debug_mode_includes_reset_url(self):
        """In DEBUG mode, response includes debug_reset_url."""
        req = self._post({"email": "user@example.com"})
        reset_obj = MagicMock()
        reset_obj.token = "tok123"
        reset_obj.user = MagicMock()
        reset_obj.user.email = "user@example.com"

        with patch("accounts.views.PasswordResetRequestSerializer") as mock_ser_cls:
            mock_ser = MagicMock()
            mock_ser.is_valid.return_value = True
            mock_ser.save.return_value = reset_obj
            mock_ser_cls.return_value = mock_ser
            with patch("accounts.views.build_frontend_base_url", return_value="http://app.test"):
                with patch("accounts.views.send_password_reset_email"):
                    with patch("accounts.views.settings") as mock_settings:
                        mock_settings.DEBUG = True
                        mock_settings.VAPID_PUBLIC_KEY = ""
                        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("debug_reset_url", resp.data)


# ── PasswordResetConfirmView ──────────────────────────────────────────────────

class PasswordResetConfirmViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self._throttle_patcher = patch.object(PasswordResetConfirmView, "throttle_classes", [])
        self._throttle_patcher.start()
        self.addCleanup(self._throttle_patcher.stop)
        self.view = PasswordResetConfirmView.as_view()

    def _post(self, data):
        req = self.factory.post("/api/auth/password-reset/confirm/", data, format="json")
        req.user = _anon()
        return req

    def test_invalid_token_returns_400(self):
        """Invalid/expired token raises ValidationError → 400."""
        req = self._post({"token": "bad-token", "password": "newpass123"})
        with patch("accounts.views.PasswordResetConfirmSerializer") as mock_ser_cls:
            from rest_framework.exceptions import ValidationError
            mock_ser = MagicMock()
            mock_ser.is_valid.side_effect = ValidationError({"token": ["Invalid or expired token."]})
            mock_ser_cls.return_value = mock_ser
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_reset_returns_200(self):
        """Valid token + password → 200 with 'detail'."""
        req = self._post({"token": "valid-token", "password": "newpass123"})
        with patch("accounts.views.PasswordResetConfirmSerializer") as mock_ser_cls:
            mock_ser = MagicMock()
            mock_ser.is_valid.return_value = True
            mock_ser.save.return_value = None
            mock_ser_cls.return_value = mock_ser
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("detail", resp.data)

    def test_save_is_called_on_valid_reset(self):
        """serializer.save() must be called after successful validation."""
        req = self._post({"token": "valid-token", "password": "newpass123"})
        with patch("accounts.views.PasswordResetConfirmSerializer") as mock_ser_cls:
            mock_ser = MagicMock()
            mock_ser.is_valid.return_value = True
            mock_ser_cls.return_value = mock_ser
            self.view(req)
        mock_ser.save.assert_called_once()
