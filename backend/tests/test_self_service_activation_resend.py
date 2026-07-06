"""Tests for B1 — self-service activation resend, keyed by email.

Covers:
  - sales.services.resend_activation_for_email: known un-activated email
    reissues a token (via issue_activation); unknown email returns None;
    already-activated email returns None.
  - sales.views.SelfServiceResendActivationView: ALWAYS returns the same
    generic 200 response (no account enumeration) and uses the public-lead
    throttle scope.

All tests are unit-level (SimpleTestCase + mocks — no real DB), matching the
existing style in test_activation_resilience.py / test_admin_provision_error_handling.py.
"""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from sales.services import resend_activation_for_email
from sales.throttles import PublicLeadThrottle
from sales.views import SelfServiceResendActivationView


@contextmanager
def _noop_ctx(*args, **kwargs):
    yield


def _make_user_qs(user):
    qs = MagicMock()
    qs.select_related.return_value = qs
    qs.order_by.return_value = qs
    qs.first.return_value = user
    return qs


# ── sales.services.resend_activation_for_email ────────────────────────────────

class ResendActivationForEmailTests(SimpleTestCase):
    @patch("sales.services._log_provisioning_event")
    @patch("sales.services.issue_activation")
    @patch("sales.services.ActivationToken")
    @patch("sales.services.get_user_model")
    @patch("django_tenants.utils.schema_context", _noop_ctx)
    @patch("django.db.transaction.atomic", _noop_ctx)
    def test_known_unactivated_email_reissues_and_sends(
        self, get_user_model_mock, activation_token_mock, issue_activation_mock, log_event_mock,
    ):
        tenant = SimpleNamespace(id=7, slug="demo")
        user = SimpleNamespace(id=11, email="owner@example.com", tenant=tenant)
        User = MagicMock()
        User.objects.filter.return_value = _make_user_qs(user)
        get_user_model_mock.return_value = User

        # No used ActivationToken exists yet → not yet activated.
        activation_token_mock.objects.filter.return_value.exists.return_value = False

        activation = SimpleNamespace(token="fresh-token")
        issue_activation_mock.return_value = (
            activation,
            "https://demo/admin/",
            "https://demo/owner",
            "https://demo/signin",
            "https://demo",
            "https://demo/activate?token=fresh-token",
            "",
            "activation-message",
        )

        result = resend_activation_for_email("owner@example.com")

        self.assertIsNotNone(result)
        self.assertEqual(result.tenant, tenant)
        self.assertEqual(result.user, user)
        self.assertEqual(result.activation_token, activation)
        issue_activation_mock.assert_called_once_with(tenant, user, phone="")
        log_event_mock.assert_called_once()

    @patch("sales.services.get_user_model")
    @patch("django_tenants.utils.schema_context", _noop_ctx)
    @patch("django.db.transaction.atomic", _noop_ctx)
    def test_unknown_email_returns_none(self, get_user_model_mock):
        User = MagicMock()
        User.objects.filter.return_value = _make_user_qs(None)
        get_user_model_mock.return_value = User

        result = resend_activation_for_email("nobody@example.com")

        self.assertIsNone(result)

    @patch("sales.services.issue_activation")
    @patch("sales.services.ActivationToken")
    @patch("sales.services.get_user_model")
    @patch("django_tenants.utils.schema_context", _noop_ctx)
    @patch("django.db.transaction.atomic", _noop_ctx)
    def test_already_activated_email_does_not_reissue(
        self, get_user_model_mock, activation_token_mock, issue_activation_mock,
    ):
        tenant = SimpleNamespace(id=7, slug="demo")
        user = SimpleNamespace(id=11, email="owner@example.com", tenant=tenant)
        User = MagicMock()
        User.objects.filter.return_value = _make_user_qs(user)
        get_user_model_mock.return_value = User

        # A used ActivationToken exists → already activated.
        activation_token_mock.objects.filter.return_value.exists.return_value = True

        result = resend_activation_for_email("owner@example.com")

        self.assertIsNone(result)
        issue_activation_mock.assert_not_called()

    def test_blank_email_returns_none_without_query(self):
        result = resend_activation_for_email("   ")
        self.assertIsNone(result)


# ── sales.views.SelfServiceResendActivationView ───────────────────────────────

class SelfServiceResendActivationViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = SelfServiceResendActivationView.as_view()

    def test_throttle_scope_is_public_leads(self):
        self.assertIn(PublicLeadThrottle, SelfServiceResendActivationView.throttle_classes)
        self.assertEqual(PublicLeadThrottle.scope, "public_leads")

    def test_permission_is_allow_any(self):
        from rest_framework.permissions import AllowAny
        self.assertEqual(SelfServiceResendActivationView.permission_classes, [AllowAny])

    @patch("sales.views.resend_activation_for_email")
    def test_known_email_returns_generic_200(self, resend_mock):
        resend_mock.return_value = SimpleNamespace(tenant=SimpleNamespace(slug="demo"))
        request = self.factory.post("/api/resend-activation/", {"email": "owner@example.com"}, format="json")
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], SelfServiceResendActivationView.GENERIC_DETAIL)
        resend_mock.assert_called_once_with("owner@example.com")

    @patch("sales.views.resend_activation_for_email")
    def test_unknown_email_returns_same_generic_200(self, resend_mock):
        resend_mock.return_value = None
        request = self.factory.post("/api/resend-activation/", {"email": "nobody@example.com"}, format="json")
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], SelfServiceResendActivationView.GENERIC_DETAIL)
        resend_mock.assert_called_once_with("nobody@example.com")

    @patch("sales.views.resend_activation_for_email")
    def test_missing_email_returns_generic_200_without_calling_service(self, resend_mock):
        request = self.factory.post("/api/resend-activation/", {}, format="json")
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], SelfServiceResendActivationView.GENERIC_DETAIL)
        resend_mock.assert_not_called()

    @patch("sales.views.logger")
    @patch("sales.views.resend_activation_for_email", side_effect=RuntimeError("boom"))
    def test_unexpected_error_still_returns_generic_200(self, resend_mock, logger_mock):
        """Even an unexpected internal failure must not leak details or a non-200,
        which would otherwise reveal information via response-shape differences."""
        request = self.factory.post("/api/resend-activation/", {"email": "owner@example.com"}, format="json")
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], SelfServiceResendActivationView.GENERIC_DETAIL)
        logger_mock.exception.assert_called_once()
