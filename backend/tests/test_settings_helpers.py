"""
Unit tests for pure-logic helper functions defined at the top of
config/settings.py:

  parse_csv_env(var_name, default)
    Reads an env var and splits by comma; filters empty items.

  parse_bool_env(var_name, default=False)
    Reads an env var and coerces to bool.

  hostname_from_url(value)
    Extracts the bare hostname from a URL string, stripping www prefix.

  normalize_cookie_domain(value)
    Normalises a cookie-domain string (prepends dot for non-localhost).

All tests are unit-level (SimpleTestCase — no real DB or network).
"""
from unittest.mock import patch

from django.test import SimpleTestCase

from config.settings import (
    hostname_from_url,
    normalize_cookie_domain,
    parse_bool_env,
    parse_csv_env,
)


# ══════════════════════════════════════════════════════════════════════════════
# parse_csv_env
# ══════════════════════════════════════════════════════════════════════════════

class ParseCsvEnvTests(SimpleTestCase):
    """parse_csv_env returns a list of stripped, non-empty items."""

    def test_returns_default_when_var_not_set(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("_TEST_CSV_VAR", None)
            result = parse_csv_env("_TEST_CSV_VAR", "a,b,c")
        self.assertEqual(result, ["a", "b", "c"])

    def test_splits_env_var_by_comma(self):
        with patch.dict("os.environ", {"_TEST_CSV": "x,y,z"}):
            result = parse_csv_env("_TEST_CSV", "")
        self.assertEqual(result, ["x", "y", "z"])

    def test_strips_whitespace_from_items(self):
        with patch.dict("os.environ", {"_TEST_CSV": " a , b , c "}):
            result = parse_csv_env("_TEST_CSV", "")
        self.assertEqual(result, ["a", "b", "c"])

    def test_filters_empty_items(self):
        with patch.dict("os.environ", {"_TEST_CSV": "a,,b, ,c"}):
            result = parse_csv_env("_TEST_CSV", "")
        self.assertEqual(result, ["a", "b", "c"])

    def test_single_item(self):
        with patch.dict("os.environ", {"_TEST_CSV": "localhost"}):
            result = parse_csv_env("_TEST_CSV", "")
        self.assertEqual(result, ["localhost"])

    def test_empty_string_env_var_falls_back_to_default(self):
        # Coolify forwards unset compose vars as "" — empty/whitespace must use the
        # DEFAULT, not produce an empty list (see project_prod_deploy_env memory note).
        with patch.dict("os.environ", {"_TEST_CSV": ""}):
            self.assertEqual(parse_csv_env("_TEST_CSV", "fallback"), ["fallback"])
            # An empty default still yields an empty list.
            self.assertEqual(parse_csv_env("_TEST_CSV", ""), [])


# ══════════════════════════════════════════════════════════════════════════════
# parse_bool_env
# ══════════════════════════════════════════════════════════════════════════════

class ParseBoolEnvTests(SimpleTestCase):
    """parse_bool_env coerces an env var to bool."""

    def test_returns_default_when_var_absent(self):
        import os
        os.environ.pop("_TEST_BOOL", None)
        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("_TEST_BOOL", None)
            self.assertFalse(parse_bool_env("_TEST_BOOL"))
            self.assertTrue(parse_bool_env("_TEST_BOOL", default=True))

    def test_truthy_values(self):
        for val in ("1", "true", "True", "TRUE", "yes", "YES", "on", "ON"):
            with self.subTest(val=val):
                with patch.dict("os.environ", {"_TEST_BOOL": val}):
                    self.assertTrue(parse_bool_env("_TEST_BOOL"))

    def test_falsy_values(self):
        for val in ("0", "false", "no", "off", "FALSE", "NO"):
            with self.subTest(val=val):
                with patch.dict("os.environ", {"_TEST_BOOL": val}):
                    self.assertFalse(parse_bool_env("_TEST_BOOL"))

    def test_whitespace_trimmed_before_comparison(self):
        with patch.dict("os.environ", {"_TEST_BOOL": "  true  "}):
            self.assertTrue(parse_bool_env("_TEST_BOOL"))


# ══════════════════════════════════════════════════════════════════════════════
# hostname_from_url
# ══════════════════════════════════════════════════════════════════════════════

class HostnameFromUrlTests(SimpleTestCase):
    """hostname_from_url strips scheme, path, port, and www prefix."""

    def test_empty_string_returns_empty(self):
        self.assertEqual(hostname_from_url(""), "")

    def test_none_returns_empty(self):
        self.assertEqual(hostname_from_url(None), "")

    def test_whitespace_only_returns_empty(self):
        self.assertEqual(hostname_from_url("   "), "")

    def test_full_https_url(self):
        self.assertEqual(hostname_from_url("https://menu.example.com"), "menu.example.com")

    def test_full_http_url(self):
        self.assertEqual(hostname_from_url("http://demo.example.com"), "demo.example.com")

    def test_url_with_path(self):
        self.assertEqual(hostname_from_url("https://menu.example.com/path/here"), "menu.example.com")

    def test_url_with_port(self):
        self.assertEqual(hostname_from_url("http://localhost:5173"), "localhost")

    def test_www_prefix_stripped(self):
        self.assertEqual(hostname_from_url("https://www.example.com"), "example.com")

    def test_no_scheme_gets_https_prefix(self):
        self.assertEqual(hostname_from_url("menu.example.com"), "menu.example.com")

    def test_lowercase_normalisation(self):
        self.assertEqual(hostname_from_url("https://MENU.Example.Com"), "menu.example.com")

    def test_localhost_returned_as_is(self):
        self.assertEqual(hostname_from_url("http://localhost"), "localhost")


# ══════════════════════════════════════════════════════════════════════════════
# normalize_cookie_domain
# ══════════════════════════════════════════════════════════════════════════════

class NormalizeCookieDomainTests(SimpleTestCase):
    """normalize_cookie_domain prepends a dot for non-local domains."""

    def test_none_returns_none(self):
        self.assertIsNone(normalize_cookie_domain(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(normalize_cookie_domain(""))

    def test_whitespace_only_returns_none(self):
        self.assertIsNone(normalize_cookie_domain("   "))

    def test_localhost_unchanged(self):
        self.assertEqual(normalize_cookie_domain("localhost"), "localhost")

    def test_loopback_unchanged(self):
        self.assertEqual(normalize_cookie_domain("127.0.0.1"), "127.0.0.1")

    def test_domain_already_with_dot_unchanged(self):
        self.assertEqual(normalize_cookie_domain(".example.com"), ".example.com")

    def test_bare_domain_gets_dot_prefix(self):
        self.assertEqual(normalize_cookie_domain("example.com"), ".example.com")

    def test_subdomain_gets_dot_prefix(self):
        self.assertEqual(normalize_cookie_domain("menu.ibnbatoutaweb.com"), ".menu.ibnbatoutaweb.com")
