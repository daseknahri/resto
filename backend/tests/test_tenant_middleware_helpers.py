"""
Unit tests for two static helpers on TenantAwareMainMiddleware
in config/middleware.py that are not covered elsewhere:

  _is_public_host(hostname)
    Checks if the hostname matches PUBLIC_SCHEMA_HOSTS setting.

  _not_found_response(request, *, detail, code, host, status_code)
    Returns a JSON response with CORS headers applied.

All tests are unit-level (SimpleTestCase — no real DB).
"""
import json
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from config.middleware import TenantAwareMainMiddleware


def _mw():
    return TenantAwareMainMiddleware.__new__(TenantAwareMainMiddleware)


def _request(origin="http://demo.localhost:5173"):
    req = MagicMock()
    req.META = {"HTTP_ORIGIN": origin}
    return req


# ══════════════════════════════════════════════════════════════════════════════
# TenantAwareMainMiddleware._is_public_host
# ══════════════════════════════════════════════════════════════════════════════

class IsPublicHostTests(SimpleTestCase):
    """_is_public_host: matches against PUBLIC_SCHEMA_HOSTS after normalisation."""

    def test_known_public_host_returns_true(self):
        with self.settings(PUBLIC_SCHEMA_HOSTS=["localhost", "127.0.0.1"]):
            self.assertTrue(TenantAwareMainMiddleware._is_public_host("localhost"))

    def test_known_public_host_with_port_stripped_returns_true(self):
        with self.settings(PUBLIC_SCHEMA_HOSTS=["localhost"]):
            self.assertTrue(TenantAwareMainMiddleware._is_public_host("localhost:8000"))

    def test_uppercase_host_normalised(self):
        with self.settings(PUBLIC_SCHEMA_HOSTS=["localhost"]):
            self.assertTrue(TenantAwareMainMiddleware._is_public_host("LOCALHOST"))

    def test_host_with_leading_whitespace_stripped(self):
        with self.settings(PUBLIC_SCHEMA_HOSTS=["localhost"]):
            self.assertTrue(TenantAwareMainMiddleware._is_public_host("  localhost  "))

    def test_unknown_host_returns_false(self):
        with self.settings(PUBLIC_SCHEMA_HOSTS=["localhost"]):
            self.assertFalse(TenantAwareMainMiddleware._is_public_host("demo.example.com"))

    def test_empty_string_returns_false(self):
        with self.settings(PUBLIC_SCHEMA_HOSTS=["localhost"]):
            self.assertFalse(TenantAwareMainMiddleware._is_public_host(""))

    def test_none_returns_false(self):
        with self.settings(PUBLIC_SCHEMA_HOSTS=["localhost"]):
            self.assertFalse(TenantAwareMainMiddleware._is_public_host(None))

    def test_empty_public_schema_hosts_always_false(self):
        with self.settings(PUBLIC_SCHEMA_HOSTS=[]):
            self.assertFalse(TenantAwareMainMiddleware._is_public_host("localhost"))

    def test_ip_address_in_list_recognised(self):
        with self.settings(PUBLIC_SCHEMA_HOSTS=["127.0.0.1"]):
            self.assertTrue(TenantAwareMainMiddleware._is_public_host("127.0.0.1"))

    def test_ip_address_with_port_stripped(self):
        with self.settings(PUBLIC_SCHEMA_HOSTS=["127.0.0.1"]):
            self.assertTrue(TenantAwareMainMiddleware._is_public_host("127.0.0.1:8000"))


# ══════════════════════════════════════════════════════════════════════════════
# TenantAwareMainMiddleware._not_found_response
# ══════════════════════════════════════════════════════════════════════════════

class NotFoundResponseTests(SimpleTestCase):
    """_not_found_response: returns JSON response with correct shape."""

    def _call(self, *, detail="Not found", code="not_found", host="demo.local", status_code=404):
        mw = _mw()
        req = _request()
        return mw._not_found_response(
            req,
            detail=detail,
            code=code,
            host=host,
            status_code=status_code,
        )

    def test_status_code_matches(self):
        resp = self._call(status_code=404)
        self.assertEqual(resp.status_code, 404)

    def test_custom_status_code_reflected(self):
        resp = self._call(status_code=423)
        self.assertEqual(resp.status_code, 423)

    def test_content_type_is_json(self):
        resp = self._call()
        self.assertIn("application/json", resp["Content-Type"])

    def test_response_contains_detail(self):
        resp = self._call(detail="Tenant not found")
        body = json.loads(resp.content)
        self.assertEqual(body["detail"], "Tenant not found")

    def test_response_contains_code(self):
        resp = self._call(code="tenant_not_found")
        body = json.loads(resp.content)
        self.assertEqual(body["code"], "tenant_not_found")

    def test_response_contains_host(self):
        resp = self._call(host="demo.bistro.com")
        body = json.loads(resp.content)
        self.assertEqual(body["host"], "demo.bistro.com")

    def test_response_contains_hint(self):
        resp = self._call()
        body = json.loads(resp.content)
        self.assertIn("hint", body)
        self.assertIn("Provision", body["hint"])
