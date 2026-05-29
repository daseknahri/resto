"""
Unit tests for the private helpers in
accounts/management/commands/email_delivery_drill.py:

  _normalize_base_url(raw)
    - Empty / None → raises CommandError
    - URL without scheme → prepends "https://"
    - http:// URL accepted unchanged (minus trailing slash)
    - Invalid URL (bad scheme) → raises CommandError

  _normalize_sent_count(value)
    - Integer → returned as-is
    - Numeric string → converted to int
    - None → 0
    - Non-numeric string → 0

All tests are unit-level (SimpleTestCase — no management-command overhead).
"""
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from accounts.management.commands.email_delivery_drill import (
    _normalize_base_url,
    _normalize_sent_count,
)


# ══════════════════════════════════════════════════════════════════════════════
# _normalize_base_url
# ══════════════════════════════════════════════════════════════════════════════

class NormalizeBaseUrlTests(SimpleTestCase):

    def test_empty_string_raises(self):
        with self.assertRaises(CommandError):
            _normalize_base_url("")

    def test_none_raises(self):
        with self.assertRaises(CommandError):
            _normalize_base_url(None)

    def test_whitespace_only_raises(self):
        with self.assertRaises(CommandError):
            _normalize_base_url("   ")

    def test_url_without_scheme_gets_https_prefix(self):
        result = _normalize_base_url("menu.example.com")
        self.assertTrue(result.startswith("https://"))
        self.assertIn("menu.example.com", result)

    def test_https_url_accepted(self):
        result = _normalize_base_url("https://menu.example.com")
        self.assertEqual(result, "https://menu.example.com")

    def test_http_url_accepted(self):
        result = _normalize_base_url("http://localhost:5173")
        self.assertEqual(result, "http://localhost:5173")

    def test_trailing_slash_stripped(self):
        result = _normalize_base_url("https://menu.example.com/")
        self.assertFalse(result.endswith("/"))

    def test_invalid_scheme_raises(self):
        with self.assertRaises(CommandError):
            _normalize_base_url("ftp://menu.example.com")

    def test_scheme_only_raises(self):
        with self.assertRaises(CommandError):
            _normalize_base_url("://bad")


# ══════════════════════════════════════════════════════════════════════════════
# _normalize_sent_count
# ══════════════════════════════════════════════════════════════════════════════

class NormalizeSentCountTests(SimpleTestCase):

    def test_integer_passed_through(self):
        self.assertEqual(_normalize_sent_count(1), 1)

    def test_zero_integer_passed_through(self):
        self.assertEqual(_normalize_sent_count(0), 0)

    def test_numeric_string_converted(self):
        self.assertEqual(_normalize_sent_count("3"), 3)

    def test_none_returns_zero(self):
        self.assertEqual(_normalize_sent_count(None), 0)

    def test_empty_string_returns_zero(self):
        self.assertEqual(_normalize_sent_count(""), 0)

    def test_non_numeric_string_returns_zero(self):
        self.assertEqual(_normalize_sent_count("bad"), 0)

    def test_float_string_returns_int(self):
        # int("1.5") raises ValueError → returns 0
        self.assertEqual(_normalize_sent_count("1.5"), 0)
