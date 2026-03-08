from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.exceptions import Throttled

from config import exceptions as app_exceptions


def _throttle_context():
    request = Mock()
    request.path = "/api/sign-in/"
    request.method = "POST"
    request.META = {"REMOTE_ADDR": "203.0.113.42"}
    request.user = SimpleNamespace(is_authenticated=True, username="owner-demo")
    view = SimpleNamespace(throttle_scope="auth_sign_in")
    return {"request": request, "view": view}


class ExceptionHandlerTests(SimpleTestCase):
    def test_throttle_does_not_send_sentry_event_when_disabled(self):
        sentry_mock = Mock()
        with (
            patch.object(app_exceptions, "SENTRY_CAPTURE_THROTTLE", False),
            patch.object(app_exceptions, "SENTRY_THROTTLE_MIN_WAIT_SECONDS", 0.0),
            patch.object(app_exceptions, "sentry_sdk", sentry_mock),
        ):
            response = app_exceptions.exception_handler(Throttled(wait=60), _throttle_context())

        self.assertEqual(response.status_code, 429)
        sentry_mock.push_scope.assert_not_called()
        sentry_mock.capture_message.assert_not_called()

    def test_throttle_sends_sentry_event_when_enabled_and_wait_exceeds_threshold(self):
        sentry_mock = Mock()
        scope_mock = Mock()
        cm = Mock()
        cm.__enter__ = Mock(return_value=scope_mock)
        cm.__exit__ = Mock(return_value=False)
        sentry_mock.push_scope.return_value = cm

        with (
            patch.object(app_exceptions, "SENTRY_CAPTURE_THROTTLE", True),
            patch.object(app_exceptions, "SENTRY_THROTTLE_MIN_WAIT_SECONDS", 30.0),
            patch.object(app_exceptions, "sentry_sdk", sentry_mock),
        ):
            response = app_exceptions.exception_handler(Throttled(wait=60), _throttle_context())

        self.assertEqual(response.status_code, 429)
        sentry_mock.capture_message.assert_called_once_with("security.throttle.blocked", level="warning")
        scope_mock.set_tag.assert_any_call("security_event", "throttle_blocked")
        scope_mock.set_tag.assert_any_call("throttle_scope", "auth_sign_in")

        context_name, context_payload = scope_mock.set_context.call_args[0]
        self.assertEqual(context_name, "throttle")
        self.assertEqual(context_payload["scope"], "auth_sign_in")
        self.assertEqual(context_payload["wait_seconds"], 60.0)
        self.assertEqual(context_payload["user"], "owner-demo")
