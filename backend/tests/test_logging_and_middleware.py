"""
Tests for config/logging_utils.py and RequestLoggingMiddleware
in config/middleware.py.

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
import json
import logging
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, RequestFactory

from config.logging_utils import JsonFormatter
from config.middleware import RequestLoggingMiddleware


# ══════════════════════════════════════════════════════════════════════════════
# JsonFormatter
# ══════════════════════════════════════════════════════════════════════════════

class JsonFormatterTests(SimpleTestCase):
    def setUp(self):
        self.formatter = JsonFormatter()

    def _record(self, message="hello", level=logging.INFO, structured=None):
        record = logging.LogRecord(
            name="test.logger",
            level=level,
            pathname="test.py",
            lineno=1,
            msg=message,
            args=(),
            exc_info=None,
        )
        if structured is not None:
            record.structured = structured
        return record

    def _parse(self, record):
        raw = self.formatter.format(record)
        return json.loads(raw)

    def test_basic_fields_present(self):
        data = self._parse(self._record("hello"))
        for field in ("timestamp", "level", "logger", "message"):
            self.assertIn(field, data)

    def test_message_is_correct(self):
        data = self._parse(self._record("hello world"))
        self.assertEqual(data["message"], "hello world")

    def test_level_name_is_correct(self):
        data = self._parse(self._record(level=logging.WARNING))
        self.assertEqual(data["level"], "WARNING")

    def test_structured_extra_fields_merged(self):
        structured = {"event": "order_placed", "tenant_id": 42}
        data = self._parse(self._record(structured=structured))
        self.assertEqual(data["event"], "order_placed")
        self.assertEqual(data["tenant_id"], 42)

    def test_structured_key_collision_prefixed_with_context(self):
        """If structured key collides with top-level key, it becomes context_<key>."""
        structured = {"message": "conflict", "level": "collision"}
        data = self._parse(self._record(structured=structured))
        self.assertEqual(data["context_message"], "conflict")
        self.assertEqual(data["context_level"], "collision")
        # original top-level fields preserved
        self.assertEqual(data["message"], "hello")

    def test_non_dict_structured_is_ignored(self):
        record = self._record()
        record.structured = "not a dict"
        data = self._parse(record)
        self.assertNotIn("structured", data)

    def test_output_is_valid_json(self):
        data = self._parse(self._record("test message"))
        self.assertIsInstance(data, dict)

    def test_exception_info_included_when_present(self):
        try:
            raise ValueError("oops")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        record = self._record()
        record.exc_info = exc_info
        data = self._parse(record)
        self.assertIn("exception", data)
        self.assertIn("ValueError", data["exception"])


# ══════════════════════════════════════════════════════════════════════════════
# RequestLoggingMiddleware
# ══════════════════════════════════════════════════════════════════════════════

class RequestLoggingMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _make_response(self, status=200):
        resp = MagicMock()
        resp.status_code = status
        resp.__setitem__ = MagicMock()
        return resp

    def _middleware(self, response=None):
        if response is None:
            response = self._make_response()
        get_response = MagicMock(return_value=response)
        mw = RequestLoggingMiddleware(get_response)
        return mw, get_response

    def test_response_passes_through(self):
        fake_resp = self._make_response(200)
        mw, get_response = self._middleware(fake_resp)
        request = self.factory.get("/api/menu/")
        request.tenant = None
        request.user = MagicMock(is_authenticated=False)

        with patch("config.middleware.request_logger") as mock_logger:
            result = mw(request)

        self.assertIs(result, fake_resp)

    def test_x_request_id_set_on_response(self):
        fake_resp = self._make_response(200)
        mw, _ = self._middleware(fake_resp)
        request = self.factory.get("/api/menu/")
        request.tenant = None
        request.user = MagicMock(is_authenticated=False)

        with patch("config.middleware.request_logger"):
            mw(request)

        fake_resp.__setitem__.assert_called()
        set_keys = [call_args[0][0] for call_args in fake_resp.__setitem__.call_args_list]
        self.assertIn("X-Request-ID", set_keys)

    def test_uses_x_request_id_from_headers_if_present(self):
        fake_resp = self._make_response(200)
        mw, _ = self._middleware(fake_resp)
        request = self.factory.get("/api/menu/", HTTP_X_REQUEST_ID="custom-req-id-123")
        request.tenant = None
        request.user = MagicMock(is_authenticated=False)

        with patch("config.middleware.request_logger"):
            mw(request)

        self.assertEqual(request.request_id, "custom-req-id-123")

    def test_generates_request_id_when_not_in_headers(self):
        fake_resp = self._make_response(200)
        mw, _ = self._middleware(fake_resp)
        request = self.factory.get("/api/menu/")
        request.tenant = None
        request.user = MagicMock(is_authenticated=False)

        with patch("config.middleware.request_logger"):
            mw(request)

        self.assertTrue(len(request.request_id) > 0)

    def test_logs_info_for_200(self):
        fake_resp = self._make_response(200)
        mw, _ = self._middleware(fake_resp)
        request = self.factory.get("/api/menu/")
        request.tenant = SimpleNamespace(id=1, slug="demo", schema_name="demo")
        request.user = MagicMock(is_authenticated=True, id=5, role="tenant_owner")

        with patch("config.middleware.request_logger") as mock_logger:
            mw(request)

        log_call = mock_logger.log.call_args
        self.assertEqual(log_call[0][0], logging.INFO)

    def test_logs_warning_for_400(self):
        fake_resp = self._make_response(400)
        mw, _ = self._middleware(fake_resp)
        request = self.factory.get("/api/missing/")
        request.tenant = None
        request.user = MagicMock(is_authenticated=False)

        with patch("config.middleware.request_logger") as mock_logger:
            mw(request)

        log_call = mock_logger.log.call_args
        self.assertEqual(log_call[0][0], logging.WARNING)

    def test_logs_error_for_500(self):
        fake_resp = self._make_response(500)
        mw, _ = self._middleware(fake_resp)
        request = self.factory.get("/api/error/")
        request.tenant = None
        request.user = MagicMock(is_authenticated=False)

        with patch("config.middleware.request_logger") as mock_logger:
            mw(request)

        log_call = mock_logger.log.call_args
        self.assertEqual(log_call[0][0], logging.ERROR)

    def test_re_raises_exceptions_from_downstream(self):
        get_response = MagicMock(side_effect=RuntimeError("crash"))
        mw = RequestLoggingMiddleware(get_response)
        request = self.factory.get("/api/boom/")
        request.tenant = None
        request.user = MagicMock(is_authenticated=False)

        with patch("config.middleware.request_logger"):
            with self.assertRaises(RuntimeError):
                mw(request)

    def test_structured_log_includes_tenant_and_user(self):
        fake_resp = self._make_response(200)
        mw, _ = self._middleware(fake_resp)
        request = self.factory.get("/api/orders/")
        request.tenant = SimpleNamespace(id=7, slug="bistro", schema_name="bistro")
        request.user = MagicMock(is_authenticated=True, id=42, role="tenant_owner")

        with patch("config.middleware.request_logger") as mock_logger:
            mw(request)

        extra = mock_logger.log.call_args[1]["extra"]["structured"]
        self.assertEqual(extra["tenant_id"], 7)
        self.assertEqual(extra["tenant_slug"], "bistro")
        self.assertEqual(extra["user_id"], 42)
        self.assertEqual(extra["user_role"], "tenant_owner")

    def test_client_ip_uses_x_forwarded_for(self):
        """_client_ip uses rightmost-trusted XFF entry (OPS-5b IP-trust hardening).

        With TRUSTED_PROXY_COUNT=1 (default) and XFF "203.0.113.1, 10.0.0.1",
        the middleware skips 1 proxy hop from the right and returns "10.0.0.1"
        (the IP our Nginx actually saw), ignoring the spoofable leading entry.
        """
        fake_resp = self._make_response(200)
        mw, _ = self._middleware(fake_resp)
        request = self.factory.get(
            "/api/orders/",
            HTTP_X_FORWARDED_FOR="203.0.113.1, 10.0.0.1",
        )
        request.tenant = None
        request.user = MagicMock(is_authenticated=False)

        with patch("config.middleware.request_logger") as mock_logger:
            mw(request)

        extra = mock_logger.log.call_args[1]["extra"]["structured"]
        self.assertEqual(extra["client_ip"], "10.0.0.1")
