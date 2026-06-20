"""
Unit tests for four pure-logic helpers on menu.views.TableLinkViewSet:

  _safe_filename_token(value, fallback="item")
    Sanitises a string for use as a filename token.

  _public_menu_base_url(request)
    Determines the public menu base URL from query param, setting, or request.

  _table_short_url(table, base_url)
    Returns "{base_url}/t/{table.slug}".

  _table_full_url(table, base_url)
    Returns "{base_url}/menu?table={quote_plus(table.label)}".

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from menu.views import TableLinkViewSet


def _vs():
    """Return a bare TableLinkViewSet instance (no HTTP context needed)."""
    return TableLinkViewSet()


def _table(slug="vip-table", label="VIP Table"):
    return SimpleNamespace(slug=slug, label=label)


def _request(*, menu_base_url=None, is_secure=False, host="testserver"):
    """Build a minimal mock request."""
    req = MagicMock()
    req.query_params.get.side_effect = lambda key, default="": (
        menu_base_url if key == "menu_base_url" else default
    )
    req.is_secure.return_value = is_secure
    req.get_host.return_value = host
    return req


# ══════════════════════════════════════════════════════════════════════════════
# _safe_filename_token
# ══════════════════════════════════════════════════════════════════════════════

class SafeFilenameTokenTests(SimpleTestCase):
    """_safe_filename_token sanitises values for safe file names."""

    # ── basic conversions ─────────────────────────────────────────────────────
    def test_alphanumeric_value_unchanged(self):
        self.assertEqual(_vs()._safe_filename_token("hello"), "hello")

    def test_uppercase_lowercased(self):
        self.assertEqual(_vs()._safe_filename_token("Hello"), "hello")

    def test_spaces_become_hyphens(self):
        result = _vs()._safe_filename_token("My Table")
        self.assertEqual(result, "my-table")

    def test_multiple_spaces_collapse_to_single_hyphen(self):
        result = _vs()._safe_filename_token("Table  Name")
        self.assertEqual(result, "table-name")

    def test_special_chars_replaced_with_hyphens(self):
        result = _vs()._safe_filename_token("table@#name!")
        self.assertEqual(result, "table-name")

    def test_leading_trailing_whitespace_stripped(self):
        result = _vs()._safe_filename_token("  menu  ")
        self.assertEqual(result, "menu")

    def test_leading_trailing_hyphens_removed(self):
        result = _vs()._safe_filename_token("-menu-")
        self.assertEqual(result, "menu")

    def test_underscores_preserved(self):
        result = _vs()._safe_filename_token("my_table")
        self.assertEqual(result, "my_table")

    def test_hyphens_preserved(self):
        result = _vs()._safe_filename_token("my-table")
        self.assertEqual(result, "my-table")

    # ── edge cases ────────────────────────────────────────────────────────────
    def test_none_returns_fallback(self):
        self.assertEqual(_vs()._safe_filename_token(None), "item")

    def test_empty_string_returns_fallback(self):
        self.assertEqual(_vs()._safe_filename_token(""), "item")

    def test_whitespace_only_returns_fallback(self):
        self.assertEqual(_vs()._safe_filename_token("   "), "item")

    def test_special_chars_only_returns_fallback(self):
        result = _vs()._safe_filename_token("@@@")
        self.assertEqual(result, "item")

    def test_custom_fallback_used(self):
        self.assertEqual(_vs()._safe_filename_token(None, fallback="table"), "table")

    def test_long_value_truncated_to_60_chars(self):
        long_value = "a" * 100
        result = _vs()._safe_filename_token(long_value)
        self.assertEqual(len(result), 60)

    def test_integer_value_converted(self):
        result = _vs()._safe_filename_token(42)
        self.assertEqual(result, "42")


# ══════════════════════════════════════════════════════════════════════════════
# _public_menu_base_url
# ══════════════════════════════════════════════════════════════════════════════

class PublicMenuBaseUrlTests(SimpleTestCase):
    """_public_menu_base_url: query param → setting → request-derived."""

    # ── query param takes precedence ─────────────────────────────────────────
    def test_explicit_query_param_returned(self):
        req = _request(menu_base_url="https://menu.example.com")
        result = _vs()._public_menu_base_url(req)
        self.assertEqual(result, "https://menu.example.com")

    def test_trailing_slash_stripped_from_query_param(self):
        req = _request(menu_base_url="https://menu.example.com/")
        result = _vs()._public_menu_base_url(req)
        self.assertEqual(result, "https://menu.example.com")

    # ── configured setting ────────────────────────────────────────────────────
    def test_configured_setting_used_when_no_query_param(self):
        req = _request(menu_base_url=None)
        with self.settings(PUBLIC_MENU_BASE_URL="https://configured.example.com"):
            result = _vs()._public_menu_base_url(req)
        self.assertEqual(result, "https://configured.example.com")

    def test_trailing_slash_stripped_from_setting(self):
        req = _request(menu_base_url=None)
        with self.settings(PUBLIC_MENU_BASE_URL="https://configured.example.com/"):
            result = _vs()._public_menu_base_url(req)
        self.assertEqual(result, "https://configured.example.com")

    # ── fallback to request host ──────────────────────────────────────────────
    def test_http_scheme_for_insecure_request(self):
        req = _request(menu_base_url=None, is_secure=False, host="example.com")
        with self.settings(PUBLIC_MENU_BASE_URL=""):
            result = _vs()._public_menu_base_url(req)
        self.assertEqual(result, "http://example.com")

    def test_https_scheme_for_secure_request(self):
        req = _request(menu_base_url=None, is_secure=True, host="example.com")
        with self.settings(PUBLIC_MENU_BASE_URL=""):
            result = _vs()._public_menu_base_url(req)
        self.assertEqual(result, "https://example.com")

    def test_localhost_port_8000_rewritten_to_5173(self):
        req = _request(menu_base_url=None, is_secure=False, host="localhost:8000")
        with self.settings(PUBLIC_MENU_BASE_URL=""):
            result = _vs()._public_menu_base_url(req)
        self.assertEqual(result, "http://localhost:5173")

    def test_subdomain_localhost_8000_rewritten(self):
        req = _request(menu_base_url=None, is_secure=False, host="demo.localhost:8000")
        with self.settings(PUBLIC_MENU_BASE_URL=""):
            result = _vs()._public_menu_base_url(req)
        self.assertEqual(result, "http://demo.localhost:5173")

    def test_non_8000_port_not_rewritten(self):
        req = _request(menu_base_url=None, is_secure=False, host="localhost:9000")
        with self.settings(PUBLIC_MENU_BASE_URL=""):
            result = _vs()._public_menu_base_url(req)
        self.assertEqual(result, "http://localhost:9000")


# ══════════════════════════════════════════════════════════════════════════════
# _table_short_url
# ══════════════════════════════════════════════════════════════════════════════

class TableShortUrlTests(SimpleTestCase):
    """_table_short_url: {base_url}/t/{table.slug}"""

    def test_basic_url_format(self):
        table = _table(slug="table-1")
        result = _vs()._table_short_url(table, "https://menu.example.com")
        self.assertEqual(result, "https://menu.example.com/t/table-1")

    def test_slug_appended_correctly(self):
        table = _table(slug="vip-table")
        result = _vs()._table_short_url(table, "https://example.com")
        self.assertIn("/t/vip-table", result)

    def test_base_url_preserved_exactly(self):
        table = _table(slug="t1")
        base = "http://localhost:5173"
        result = _vs()._table_short_url(table, base)
        self.assertTrue(result.startswith(base))

    def test_slug_with_numbers(self):
        table = _table(slug="table-42")
        result = _vs()._table_short_url(table, "https://example.com")
        self.assertEqual(result, "https://example.com/t/table-42")


# ══════════════════════════════════════════════════════════════════════════════
# _table_full_url
# ══════════════════════════════════════════════════════════════════════════════

class TableFullUrlTests(SimpleTestCase):
    """_table_full_url: {base_url}/menu?table={quote_plus(table.label)}"""

    def test_basic_url_format(self):
        table = _table(label="Table 1")
        result = _vs()._table_full_url(table, "https://menu.example.com")
        self.assertEqual(result, "https://menu.example.com/menu?table=Table+1")

    def test_label_url_encoded(self):
        table = _table(label="VIP Table & Bar")
        result = _vs()._table_full_url(table, "https://example.com")
        self.assertIn("VIP+Table+%26+Bar", result)

    def test_label_with_special_chars_encoded(self):
        table = _table(label="Table #5")
        result = _vs()._table_full_url(table, "https://example.com")
        self.assertNotIn("#", result)  # # must be encoded

    def test_plain_label_no_encoding_needed(self):
        table = _table(label="TableA")
        result = _vs()._table_full_url(table, "https://example.com")
        self.assertEqual(result, "https://example.com/menu?table=TableA")

    def test_base_url_preserved(self):
        table = _table(label="T")
        base = "http://localhost:5173"
        result = _vs()._table_full_url(table, base)
        self.assertTrue(result.startswith(base + "/menu?table="))
