"""
Additional unit tests for config.exceptions.exception_handler covering
edge cases not addressed by test_exception_handler.py:

  - Non-Throttled exception → delegates to DRF handler, no special logging
  - Anonymous user (not authenticated) → username shown as "anonymous"
  - Sentry enabled but wait below threshold → capture_message NOT called
  - Missing request (context without 'request') → no crash
  - Wait below Sentry threshold → no Sentry event even when SENTRY_CAPTURE_THROTTLE=True
"""
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.exceptions import NotFound, Throttled

from config import exceptions as app_exceptions


def _context(request=None, view=None):
    return {
        "request": request or _request(),
        "view": view or SimpleNamespace(throttle_scope="test_scope"),
    }


def _request(*, authenticated=True, username="owner"):
    req = Mock()
    req.path = "/api/test/"
    req.method = "GET"
    req.META = {"REMOTE_ADDR": "10.0.0.1"}
    user = SimpleNamespace(is_authenticated=authenticated, username=username)
    req.user = user
    return req


class ExceptionHandlerEdgeCasesTests(SimpleTestCase):

    # ── non-throttle exception ────────────────────────────────────────────────
    def test_non_throttle_exception_returns_drf_response(self):
        """Non-Throttled exception is passed straight to DRF handler."""
        sentry_mock = Mock()
        with patch.object(app_exceptions, "sentry_sdk", sentry_mock):
            response = app_exceptions.exception_handler(NotFound("Not found"), _context())
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 404)
        sentry_mock.push_scope.assert_not_called()

    def test_non_throttle_exception_does_not_trigger_sentry(self):
        sentry_mock = Mock()
        with (
            patch.object(app_exceptions, "SENTRY_CAPTURE_THROTTLE", True),
            patch.object(app_exceptions, "sentry_sdk", sentry_mock),
        ):
            app_exceptions.exception_handler(NotFound(), _context())
        sentry_mock.capture_message.assert_not_called()

    # ── anonymous user ────────────────────────────────────────────────────────
    def test_anonymous_user_logged_as_anonymous(self):
        """When user is not authenticated, 'anonymous' is logged (no crash)."""
        sentry_mock = Mock()
        anon_request = _request(authenticated=False)
        with (
            patch.object(app_exceptions, "SENTRY_CAPTURE_THROTTLE", False),
            patch.object(app_exceptions, "sentry_sdk", sentry_mock),
        ):
            response = app_exceptions.exception_handler(
                Throttled(wait=60),
                _context(request=anon_request),
            )
        self.assertEqual(response.status_code, 429)

    def test_sentry_context_shows_anonymous_for_unauthenticated(self):
        """Sentry context payload uses 'anonymous' as user string when unauthenticated."""
        sentry_mock = Mock()
        scope_mock = Mock()
        cm = Mock()
        cm.__enter__ = Mock(return_value=scope_mock)
        cm.__exit__ = Mock(return_value=False)
        sentry_mock.push_scope.return_value = cm

        anon_request = _request(authenticated=False)
        with (
            patch.object(app_exceptions, "SENTRY_CAPTURE_THROTTLE", True),
            patch.object(app_exceptions, "SENTRY_THROTTLE_MIN_WAIT_SECONDS", 0.0),
            patch.object(app_exceptions, "sentry_sdk", sentry_mock),
        ):
            app_exceptions.exception_handler(
                Throttled(wait=60),
                _context(request=anon_request),
            )

        context_payload = scope_mock.set_context.call_args[0][1]
        self.assertEqual(context_payload["user"], "anonymous")

    # ── Sentry not triggered below threshold ──────────────────────────────────
    def test_sentry_not_triggered_when_wait_below_threshold(self):
        """Even with SENTRY_CAPTURE_THROTTLE=True, wait < threshold → no capture."""
        sentry_mock = Mock()
        with (
            patch.object(app_exceptions, "SENTRY_CAPTURE_THROTTLE", True),
            patch.object(app_exceptions, "SENTRY_THROTTLE_MIN_WAIT_SECONDS", 60.0),
            patch.object(app_exceptions, "sentry_sdk", sentry_mock),
        ):
            app_exceptions.exception_handler(
                Throttled(wait=30),   # 30 < 60 threshold
                _context(),
            )
        sentry_mock.capture_message.assert_not_called()

    # ── missing context keys ──────────────────────────────────────────────────
    def test_missing_request_in_context_does_not_crash(self):
        """context without 'request' → no crash, returns 429."""
        sentry_mock = Mock()
        with patch.object(app_exceptions, "sentry_sdk", sentry_mock):
            response = app_exceptions.exception_handler(
                Throttled(wait=60),
                {"view": SimpleNamespace(throttle_scope="test"), "request": None},
            )
        self.assertEqual(response.status_code, 429)

    def test_missing_view_in_context_does_not_crash(self):
        """context without 'view' → no crash."""
        sentry_mock = Mock()
        with patch.object(app_exceptions, "sentry_sdk", sentry_mock):
            response = app_exceptions.exception_handler(
                Throttled(wait=60),
                {"request": _request(), "view": None},
            )
        self.assertEqual(response.status_code, 429)
