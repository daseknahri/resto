"""
Tests for core session / authentication views:
  - ActivationView   POST /api/activate/
  - LoginView        POST /api/login/
  - LogoutView       POST /api/logout/
  - SessionView      GET  /api/session/

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import (
    ActivationView,
    LoginView,
    LogoutView,
    SessionView,
)
from accounts.models import User


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user(role=None, tenant=None):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.is_tenant_owner = True
    u.is_tenant_staff = False
    u.role = role or User.Roles.TENANT_OWNER
    u.id = 1
    u.username = "owner"
    u.email = "owner@example.com"
    u.tenant = tenant
    return u


def _anon():
    u = MagicMock()
    u.is_authenticated = False
    return u


def _session_data():
    return {"id": 1, "username": "owner", "email": "owner@example.com"}


# ── ActivationView ────────────────────────────────────────────────────────────

class ActivationViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = ActivationView.as_view()
        # Patch out throttle classes so tests don't hit the cache
        patcher = patch.object(ActivationView, "throttle_classes", [])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _post(self, data):
        req = self.factory.post("/api/activate/", data, format="json")
        req.user = _anon()
        return self.view(req)

    def test_invalid_token_returns_400(self):
        with patch("accounts.views.ActivationSerializer") as mock_ser:
            instance = mock_ser.return_value
            instance.is_valid.side_effect = Exception("invalid")
            # Validation error raised by is_valid(raise_exception=True)
            from rest_framework.exceptions import ValidationError
            instance.is_valid.side_effect = ValidationError({"token": "invalid"})
            resp = self._post({"token": "bad"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_token_activates_and_returns_200(self):
        user = _user()
        with patch("accounts.views.ActivationSerializer") as mock_ser:
            instance = mock_ser.return_value
            instance.is_valid.return_value = True
            instance.save.return_value = user
            with patch("accounts.views.login"):
                with patch("accounts.views.serialize_user_session", return_value=_session_data()):
                    resp = self._post({"token": "validtoken"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("user", resp.data)
        self.assertEqual(resp.data["detail"], "Account activated")


# ── LoginView ─────────────────────────────────────────────────────────────────

class LoginViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = LoginView.as_view()
        # Patch out throttle classes
        patcher = patch.object(LoginView, "throttle_classes", [])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _post(self, data):
        req = self.factory.post("/api/login/", data, format="json")
        req.user = _anon()
        return self.view(req)

    def test_invalid_credentials_returns_400(self):
        from rest_framework.exceptions import ValidationError
        with patch("accounts.views.LoginSerializer") as mock_ser:
            instance = mock_ser.return_value
            instance.is_valid.side_effect = ValidationError({"non_field_errors": "Invalid credentials"})
            resp = self._post({"email": "bad@e.com", "password": "wrong"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_credentials_returns_200_with_user(self):
        user = _user()
        with patch("accounts.views.LoginSerializer") as mock_ser:
            instance = mock_ser.return_value
            instance.is_valid.return_value = True
            instance.validated_data = {"user": user}
            with patch("accounts.views.login"):
                with patch("accounts.views.serialize_user_session", return_value=_session_data()):
                    resp = self._post({"email": "owner@example.com", "password": "pass"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["detail"], "Signed in")
        self.assertIn("user", resp.data)

    def test_login_calls_django_login(self):
        user = _user()
        with patch("accounts.views.LoginSerializer") as mock_ser:
            instance = mock_ser.return_value
            instance.is_valid.return_value = True
            instance.validated_data = {"user": user}
            with patch("accounts.views.login") as mock_login:
                with patch("accounts.views.serialize_user_session", return_value=_session_data()):
                    self._post({"email": "owner@example.com", "password": "pass"})
        mock_login.assert_called_once()


# ── LogoutView ────────────────────────────────────────────────────────────────

class LogoutViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = LogoutView.as_view()

    def _post(self, user=None):
        req = self.factory.post("/api/logout/")
        req.user = user or _user()
        return self.view(req)

    def test_unauthenticated_returns_403(self):
        resp = self._post(user=_anon())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_authenticated_user_returns_200(self):
        with patch("accounts.views.logout"):
            resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["detail"], "Signed out")

    def test_logout_calls_django_logout(self):
        with patch("accounts.views.logout") as mock_logout:
            self._post()
        mock_logout.assert_called_once()


# ── SessionView ───────────────────────────────────────────────────────────────

class SessionViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = SessionView.as_view()

    def _get(self, user=None):
        req = self.factory.get("/api/session/")
        req.user = user or _anon()
        return self.view(req)

    def test_unauthenticated_returns_false(self):
        resp = self._get(user=_anon())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["authenticated"])
        self.assertIsNone(resp.data["user"])

    def test_authenticated_returns_true(self):
        user = _user()
        with patch("accounts.views.serialize_user_session", return_value=_session_data()):
            resp = self._get(user=user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["authenticated"])
        self.assertIn("user", resp.data)

    def test_inactive_tenant_logs_out_and_returns_false(self):
        tenant = MagicMock()
        tenant.is_active = False
        tenant.lifecycle_status = "suspended"
        user = _user(tenant=tenant)
        with patch("accounts.views.logout") as mock_logout:
            resp = self._get(user=user)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["authenticated"])
        mock_logout.assert_called_once()
        self.assertIn("detail", resp.data)

    def test_active_tenant_does_not_logout(self):
        tenant = MagicMock()
        tenant.is_active = True
        user = _user(tenant=tenant)
        with patch("accounts.views.logout") as mock_logout:
            with patch("accounts.views.serialize_user_session", return_value=_session_data()):
                resp = self._get(user=user)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["authenticated"])
        mock_logout.assert_not_called()

    def test_no_tenant_still_returns_authenticated(self):
        user = _user(tenant=None)
        with patch("accounts.views.serialize_user_session", return_value=_session_data()):
            resp = self._get(user=user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["authenticated"])
