"""
Unit tests for:
  accounts.management.commands.email_delivery_drill
    - _normalize_base_url
    - _normalize_sent_count
  tenancy.serializers
    - _normalize_local_media_url   (distinct from menu.serializers version;
                                    adds DisallowedHost exception handling)

All tests are unit-level (SimpleTestCase — no real DB).
"""
from unittest.mock import MagicMock

from django.core.management.base import CommandError
from django.test import SimpleTestCase

from accounts.management.commands.email_delivery_drill import (
    _normalize_base_url,
    _normalize_sent_count,
)
from tenancy.serializers import _normalize_local_media_url


# ══════════════════════════════════════════════════════════════════════════════
# _normalize_base_url
# ══════════════════════════════════════════════════════════════════════════════

class NormalizeBaseUrlTests(SimpleTestCase):
    """_normalize_base_url: adds scheme, strips trailing slash, raises on bad input."""

    # ── empty / missing input → raises ───────────────────────────────────────
    def test_empty_string_raises(self):
        with self.assertRaises(CommandError):
            _normalize_base_url("")

    def test_none_raises(self):
        with self.assertRaises(CommandError):
            _normalize_base_url(None)

    def test_whitespace_only_raises(self):
        with self.assertRaises(CommandError):
            _normalize_base_url("   ")

    # ── invalid URL structure → raises ────────────────────────────────────────
    def test_invalid_scheme_raises(self):
        with self.assertRaises(CommandError):
            _normalize_base_url("://bad-url")

    def test_ftp_scheme_raises(self):
        with self.assertRaises(CommandError):
            _normalize_base_url("ftp://example.com")

    # ── scheme injection ──────────────────────────────────────────────────────
    def test_host_without_scheme_gets_https(self):
        result = _normalize_base_url("menu.example.com")
        self.assertEqual(result, "https://menu.example.com")

    def test_host_without_scheme_with_path_gets_https(self):
        result = _normalize_base_url("demo.example.com/menu")
        self.assertEqual(result, "https://demo.example.com/menu")

    # ── accepted schemes ──────────────────────────────────────────────────────
    def test_https_scheme_preserved(self):
        result = _normalize_base_url("https://menu.example.com")
        self.assertEqual(result, "https://menu.example.com")

    def test_http_scheme_preserved(self):
        result = _normalize_base_url("http://localhost:8000")
        self.assertEqual(result, "http://localhost:8000")

    # ── trailing slash stripped ───────────────────────────────────────────────
    def test_trailing_slash_stripped(self):
        result = _normalize_base_url("https://menu.example.com/")
        self.assertEqual(result, "https://menu.example.com")

    def test_multiple_trailing_slashes_stripped(self):
        result = _normalize_base_url("https://menu.example.com///")
        self.assertEqual(result, "https://menu.example.com")

    # ── surrounding whitespace stripped ──────────────────────────────────────
    def test_surrounding_whitespace_stripped(self):
        result = _normalize_base_url("  https://menu.example.com  ")
        self.assertEqual(result, "https://menu.example.com")

    # ── localhost accepted ────────────────────────────────────────────────────
    def test_localhost_accepted(self):
        result = _normalize_base_url("localhost")
        self.assertEqual(result, "https://localhost")


# ══════════════════════════════════════════════════════════════════════════════
# _normalize_sent_count
# ══════════════════════════════════════════════════════════════════════════════

class NormalizeSentCountTests(SimpleTestCase):
    """_normalize_sent_count coerces to int, returns 0 on error."""

    def test_integer_one_returned(self):
        self.assertEqual(_normalize_sent_count(1), 1)

    def test_integer_zero_returned(self):
        self.assertEqual(_normalize_sent_count(0), 0)

    def test_string_integer_coerced(self):
        self.assertEqual(_normalize_sent_count("3"), 3)

    def test_none_returns_zero(self):
        self.assertEqual(_normalize_sent_count(None), 0)

    def test_empty_string_returns_zero(self):
        self.assertEqual(_normalize_sent_count(""), 0)

    def test_non_numeric_string_returns_zero(self):
        self.assertEqual(_normalize_sent_count("not-a-number"), 0)

    def test_float_truncated_to_int(self):
        """int(2.9) = 2 — truncation, not rounding."""
        self.assertEqual(_normalize_sent_count(2.9), 2)

    def test_large_integer_preserved(self):
        self.assertEqual(_normalize_sent_count(999), 999)


# ══════════════════════════════════════════════════════════════════════════════
# tenancy.serializers._normalize_local_media_url
# ══════════════════════════════════════════════════════════════════════════════

def _req(host="demo.example.com", is_secure=True, raise_disallowed=False):
    """Return a mock request."""
    req = MagicMock()
    if raise_disallowed:
        from django.core.exceptions import DisallowedHost
        req.get_host.side_effect = DisallowedHost("bad host")
        # DisallowedHost branch falls back to META HTTP_HOST
        req.META = {"HTTP_HOST": host}
    else:
        req.get_host.return_value = host
    req.is_secure.return_value = is_secure
    return req


class TenancyNormalizeLocalMediaUrlTests(SimpleTestCase):
    """Tests for the tenancy.serializers version of _normalize_local_media_url.
    The tenancy version adds a DisallowedHost fallback that the menu version lacks."""

    # ── edge cases ────────────────────────────────────────────────────────────
    def test_empty_value_returns_empty(self):
        self.assertEqual(_normalize_local_media_url("", _req()), "")

    def test_none_value_returns_empty(self):
        self.assertEqual(_normalize_local_media_url(None, _req()), "")

    def test_none_request_returns_raw(self):
        url = "http://demo.example.com/media/logo.png"
        self.assertEqual(_normalize_local_media_url(url, None), url)

    def test_empty_host_returns_raw(self):
        req = MagicMock()
        req.get_host.return_value = ""
        url = "http://demo.example.com/media/logo.png"
        self.assertEqual(_normalize_local_media_url(url, req), url)

    # ── absolute http → https upgrade ────────────────────────────────────────
    def test_http_same_host_media_url_upgraded_to_https(self):
        url = "http://demo.example.com/media/uploads/logo.png"
        result = _normalize_local_media_url(url, _req("demo.example.com"))
        self.assertEqual(result, "https://demo.example.com/media/uploads/logo.png")

    def test_http_same_host_media_url_preserves_query_string(self):
        url = "http://demo.example.com/media/dish.jpg?v=2"
        result = _normalize_local_media_url(url, _req("demo.example.com"))
        self.assertEqual(result, "https://demo.example.com/media/dish.jpg?v=2")

    def test_https_url_returned_unchanged(self):
        url = "https://demo.example.com/media/logo.png"
        result = _normalize_local_media_url(url, _req("demo.example.com"))
        self.assertEqual(result, url)

    def test_different_host_url_returned_unchanged(self):
        url = "http://cdn.other.com/media/logo.png"
        result = _normalize_local_media_url(url, _req("demo.example.com"))
        self.assertEqual(result, url)

    def test_non_media_path_returned_unchanged(self):
        url = "http://demo.example.com/static/logo.png"
        result = _normalize_local_media_url(url, _req("demo.example.com"))
        self.assertEqual(result, url)

    # ── relative /media/ path → prepend scheme://host ────────────────────────
    def test_relative_media_path_https_request(self):
        result = _normalize_local_media_url(
            "/media/uploads/logo.png", _req("demo.example.com", is_secure=True)
        )
        self.assertEqual(result, "https://demo.example.com/media/uploads/logo.png")

    def test_relative_media_path_http_request(self):
        result = _normalize_local_media_url(
            "/media/uploads/logo.png", _req("demo.localhost", is_secure=False)
        )
        self.assertEqual(result, "http://demo.localhost/media/uploads/logo.png")

    def test_non_media_relative_path_returned_unchanged(self):
        url = "/static/img/logo.png"
        self.assertEqual(_normalize_local_media_url(url, _req()), url)

    # ── DisallowedHost fallback (tenancy-version-specific) ───────────────────
    def test_disallowed_host_falls_back_to_meta_http_host(self):
        """When get_host() raises DisallowedHost, falls back to META HTTP_HOST."""
        req = _req(host="demo.example.com", raise_disallowed=True)
        url = "http://demo.example.com/media/logo.png"
        result = _normalize_local_media_url(url, req)
        # should still upgrade http → https since host matches
        self.assertEqual(result, "https://demo.example.com/media/logo.png")

    def test_disallowed_host_empty_meta_returns_raw(self):
        """When DisallowedHost fires AND META HTTP_HOST is absent → returns raw."""
        from django.core.exceptions import DisallowedHost
        req = MagicMock()
        req.get_host.side_effect = DisallowedHost("bad")
        req.META = {}  # no HTTP_HOST
        url = "http://demo.example.com/media/logo.png"
        result = _normalize_local_media_url(url, req)
        self.assertEqual(result, url)
