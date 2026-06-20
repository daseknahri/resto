"""
Tests for serializer utility functions in menu/serializers.py:
  - _normalize_local_media_url: HTTP→HTTPS upgrade and relative path handling
  - _normalize_locale: locale string validation and normalisation

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from menu.serializers import _normalize_local_media_url, _normalize_locale


# ══════════════════════════════════════════════════════════════════════════════
# _normalize_local_media_url
# ══════════════════════════════════════════════════════════════════════════════

def _req(host="demo.example.com", is_secure=True):
    req = MagicMock()
    req.get_host.return_value = host
    req.is_secure.return_value = is_secure
    return req


class NormalizeLocalMediaUrlTests(SimpleTestCase):
    def test_empty_value_returns_empty(self):
        self.assertEqual(_normalize_local_media_url("", _req()), "")

    def test_none_returns_empty(self):
        self.assertEqual(_normalize_local_media_url(None, _req()), "")

    def test_no_request_returns_value_unchanged(self):
        self.assertEqual(
            _normalize_local_media_url("http://demo.example.com/media/img.jpg", None),
            "http://demo.example.com/media/img.jpg",
        )

    def test_http_local_media_upgraded_to_https(self):
        req = _req(host="demo.example.com")
        result = _normalize_local_media_url(
            "http://demo.example.com/media/photo.jpg", req
        )
        self.assertEqual(result, "https://demo.example.com/media/photo.jpg")

    def test_http_local_media_with_query_string_preserved(self):
        req = _req(host="demo.example.com")
        result = _normalize_local_media_url(
            "http://demo.example.com/media/photo.jpg?v=2", req
        )
        self.assertEqual(result, "https://demo.example.com/media/photo.jpg?v=2")

    def test_https_url_returned_unchanged(self):
        req = _req(host="demo.example.com")
        url = "https://demo.example.com/media/photo.jpg"
        result = _normalize_local_media_url(url, req)
        self.assertEqual(result, url)

    def test_external_url_returned_unchanged(self):
        req = _req(host="demo.example.com")
        url = "https://cdn.other.com/images/photo.jpg"
        result = _normalize_local_media_url(url, req)
        self.assertEqual(result, url)

    def test_relative_media_path_made_absolute_https(self):
        req = _req(host="demo.example.com", is_secure=True)
        result = _normalize_local_media_url("/media/uploads/logo.png", req)
        self.assertEqual(result, "https://demo.example.com/media/uploads/logo.png")

    def test_relative_media_path_made_absolute_http_when_not_secure(self):
        req = _req(host="demo.localhost", is_secure=False)
        result = _normalize_local_media_url("/media/uploads/logo.png", req)
        self.assertEqual(result, "http://demo.localhost/media/uploads/logo.png")

    def test_non_media_path_returned_unchanged(self):
        req = _req(host="demo.example.com")
        url = "/static/js/app.js"
        result = _normalize_local_media_url(url, req)
        self.assertEqual(result, url)

    def test_http_non_media_absolute_url_returned_unchanged(self):
        """Only /media/ paths are upgraded; other paths left alone."""
        req = _req(host="demo.example.com")
        url = "http://demo.example.com/api/orders/"
        result = _normalize_local_media_url(url, req)
        self.assertEqual(result, url)


# ══════════════════════════════════════════════════════════════════════════════
# _normalize_locale
# ══════════════════════════════════════════════════════════════════════════════

class NormalizeLocaleTests(SimpleTestCase):
    def test_two_letter_code_accepted(self):
        self.assertEqual(_normalize_locale("fr"), "fr")

    def test_two_two_code_with_hyphen_accepted(self):
        self.assertEqual(_normalize_locale("fr-FR"), "fr-fr")

    def test_underscore_converted_to_hyphen(self):
        self.assertEqual(_normalize_locale("fr_FR"), "fr-fr")

    def test_lowercased(self):
        self.assertEqual(_normalize_locale("AR"), "ar")

    def test_empty_string_returns_empty(self):
        self.assertEqual(_normalize_locale(""), "")

    def test_none_returns_empty(self):
        self.assertEqual(_normalize_locale(None), "")

    def test_invalid_code_returns_empty(self):
        self.assertEqual(_normalize_locale("not-valid-code"), "")

    def test_single_letter_returns_empty(self):
        self.assertEqual(_normalize_locale("f"), "")

    def test_long_variant_truncated_to_two_letters(self):
        # "fr-Latn" matches r'^[a-z]{2}-[a-z]{4,}$' → truncated to "fr"
        self.assertEqual(_normalize_locale("fr-Latn"), "fr")

    def test_arabic_code_accepted(self):
        self.assertEqual(_normalize_locale("ar"), "ar")

    def test_whitespace_stripped(self):
        self.assertEqual(_normalize_locale("  fr  "), "fr")
