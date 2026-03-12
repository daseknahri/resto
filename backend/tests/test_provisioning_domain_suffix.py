from django.test import SimpleTestCase, override_settings

from sales.services import normalize_domain_suffix


class ProvisioningDomainSuffixTests(SimpleTestCase):
    @override_settings(TENANT_DOMAIN_SUFFIX="menu.kepoli.com", PUBLIC_MENU_BASE_URL="https://kepoli.com")
    def test_prefers_explicit_tenant_domain_suffix(self):
        self.assertEqual(normalize_domain_suffix(None), "menu.kepoli.com")
        self.assertEqual(normalize_domain_suffix(""), "menu.kepoli.com")
        self.assertEqual(normalize_domain_suffix("localhost"), "menu.kepoli.com")

    @override_settings(PUBLIC_MENU_BASE_URL="https://kepoli.com")
    def test_uses_public_menu_base_domain_when_suffix_missing(self):
        self.assertEqual(normalize_domain_suffix(None), "kepoli.com")
        self.assertEqual(normalize_domain_suffix(""), "kepoli.com")

    @override_settings(PUBLIC_MENU_BASE_URL="https://kepoli.com")
    def test_overrides_localhost_suffix_in_production_context(self):
        self.assertEqual(normalize_domain_suffix("localhost"), "kepoli.com")
        self.assertEqual(normalize_domain_suffix("127.0.0.1"), "kepoli.com")

    @override_settings(PUBLIC_MENU_BASE_URL="http://demo.localhost:5173")
    def test_keeps_localhost_for_local_setup(self):
        self.assertEqual(normalize_domain_suffix("localhost"), "localhost")
        self.assertEqual(normalize_domain_suffix(None), "demo.localhost")

    @override_settings(PUBLIC_MENU_BASE_URL="https://kepoli.com")
    def test_keeps_explicit_non_local_suffix(self):
        self.assertEqual(normalize_domain_suffix("menus.kepoli.net"), "menus.kepoli.net")
        self.assertEqual(normalize_domain_suffix(".kepoli.com"), "kepoli.com")
