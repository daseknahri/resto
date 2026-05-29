"""
Unit tests for sales.services._default_domain_suffix.

Three code paths that are NOT exercised by the higher-level
normalize_domain_suffix tests:

  1. Both TENANT_DOMAIN_SUFFIX and PUBLIC_MENU_BASE_URL are absent/empty
     → falls back to "localhost"

  2. PUBLIC_MENU_BASE_URL contains a www. prefix
     → the www. prefix is stripped and the bare hostname is returned

  3. PUBLIC_MENU_BASE_URL is set but its hostname cannot be parsed
     (e.g. the string starts with "://" so urlparse sees no netloc)
     → falls back to "localhost"

All tests are unit-level (SimpleTestCase — no real DB).
"""
from django.test import SimpleTestCase, override_settings

from sales.services import _default_domain_suffix


class DefaultDomainSuffixTests(SimpleTestCase):

    # ── both settings absent → localhost ─────────────────────────────────────

    @override_settings(TENANT_DOMAIN_SUFFIX="", PUBLIC_MENU_BASE_URL="")
    def test_both_settings_empty_returns_localhost(self):
        self.assertEqual(_default_domain_suffix(), "localhost")

    @override_settings(TENANT_DOMAIN_SUFFIX="", PUBLIC_MENU_BASE_URL="   ")
    def test_whitespace_only_base_url_returns_localhost(self):
        """Whitespace-only PUBLIC_MENU_BASE_URL is treated as absent."""
        self.assertEqual(_default_domain_suffix(), "localhost")

    # ── TENANT_DOMAIN_SUFFIX takes precedence ─────────────────────────────────

    @override_settings(TENANT_DOMAIN_SUFFIX="menus.example.com", PUBLIC_MENU_BASE_URL="")
    def test_explicit_suffix_returned_directly(self):
        self.assertEqual(_default_domain_suffix(), "menus.example.com")

    @override_settings(TENANT_DOMAIN_SUFFIX=".menus.example.com", PUBLIC_MENU_BASE_URL="")
    def test_leading_dot_stripped_from_explicit_suffix(self):
        """The function lstrip-s the leading dot from TENANT_DOMAIN_SUFFIX."""
        self.assertEqual(_default_domain_suffix(), "menus.example.com")

    # ── www. prefix stripped from PUBLIC_MENU_BASE_URL ────────────────────────

    @override_settings(TENANT_DOMAIN_SUFFIX="", PUBLIC_MENU_BASE_URL="https://www.example.com")
    def test_www_prefix_stripped_from_https_url(self):
        self.assertEqual(_default_domain_suffix(), "example.com")

    @override_settings(TENANT_DOMAIN_SUFFIX="", PUBLIC_MENU_BASE_URL="http://www.demo.example.com")
    def test_www_prefix_stripped_from_http_url(self):
        self.assertEqual(_default_domain_suffix(), "demo.example.com")

    @override_settings(TENANT_DOMAIN_SUFFIX="", PUBLIC_MENU_BASE_URL="https://app.example.com")
    def test_non_www_hostname_returned_unchanged(self):
        """Only a www. prefix is stripped; other subdomains are kept."""
        self.assertEqual(_default_domain_suffix(), "app.example.com")

    # ── unparseable / scheme-only URL → localhost fallback ───────────────────

    @override_settings(TENANT_DOMAIN_SUFFIX="", PUBLIC_MENU_BASE_URL="://bad-url")
    def test_unparseable_url_falls_back_to_localhost(self):
        """A URL that starts with :// has no hostname — falls back to localhost."""
        self.assertEqual(_default_domain_suffix(), "localhost")

    # ── schemeless URL gets https:// prepended before parsing ────────────────

    @override_settings(TENANT_DOMAIN_SUFFIX="", PUBLIC_MENU_BASE_URL="app.example.com")
    def test_schemeless_base_url_parsed_correctly(self):
        """A bare hostname without a scheme is prepended with https:// before parsing."""
        self.assertEqual(_default_domain_suffix(), "app.example.com")

    @override_settings(TENANT_DOMAIN_SUFFIX="", PUBLIC_MENU_BASE_URL="www.example.com")
    def test_schemeless_www_url_stripped(self):
        """Even a schemeless www-prefixed hostname has the www. stripped."""
        self.assertEqual(_default_domain_suffix(), "example.com")
