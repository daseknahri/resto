"""
Tests for provisioning utility functions in sales/services.py:
  - mask_secret
  - _is_local_suffix
  - _base_slug_for_lead
  - _build_next_slug
  - _availability

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from sales.services import (
    mask_secret,
    _is_local_suffix,
    _base_slug_for_lead,
    _build_next_slug,
    _availability,
)


# ══════════════════════════════════════════════════════════════════════════════
# mask_secret
# ══════════════════════════════════════════════════════════════════════════════

class MaskSecretTests(SimpleTestCase):
    def test_empty_string_returns_empty(self):
        self.assertEqual(mask_secret(""), "")

    def test_none_returns_empty(self):
        self.assertEqual(mask_secret(None), "")

    def test_short_secret_fully_masked(self):
        # keep_start=6 + keep_end=4 = 10; "abc" is shorter → all stars
        self.assertEqual(mask_secret("abc"), "***")

    def test_long_secret_shows_start_and_end(self):
        result = mask_secret("sk-abcdefghijklmnopqrstuvwxyz", keep_start=6, keep_end=4)
        self.assertTrue(result.startswith("sk-abc"))
        self.assertTrue(result.endswith("wxyz"))
        self.assertIn("...", result)

    def test_custom_keep_lengths(self):
        result = mask_secret("0123456789ABCDEF", keep_start=3, keep_end=3)
        self.assertEqual(result, "012...DEF")

    def test_exactly_at_boundary_is_fully_masked(self):
        # 10 chars with default keep_start=6 keep_end=4 → exactly at boundary → all stars
        result = mask_secret("1234567890")
        self.assertEqual(result, "**********")


# ══════════════════════════════════════════════════════════════════════════════
# _is_local_suffix
# ══════════════════════════════════════════════════════════════════════════════

class IsLocalSuffixTests(SimpleTestCase):
    def test_localhost_is_local(self):
        self.assertTrue(_is_local_suffix("localhost"))

    def test_127_0_0_1_is_local(self):
        self.assertTrue(_is_local_suffix("127.0.0.1"))

    def test_subdomain_of_localhost_is_local(self):
        self.assertTrue(_is_local_suffix("demo.localhost"))

    def test_production_domain_is_not_local(self):
        self.assertFalse(_is_local_suffix("example.com"))

    def test_empty_string_is_not_local(self):
        self.assertFalse(_is_local_suffix(""))

    def test_whitespace_stripped(self):
        self.assertTrue(_is_local_suffix("  localhost  "))

    def test_case_insensitive(self):
        self.assertTrue(_is_local_suffix("LOCALHOST"))


# ══════════════════════════════════════════════════════════════════════════════
# _base_slug_for_lead
# ══════════════════════════════════════════════════════════════════════════════

class BaseSlugForLeadTests(SimpleTestCase):
    def _lead(self, email=None, name=None, phone=None, lead_id=1):
        return SimpleNamespace(id=lead_id, email=email or "", name=name or "", phone=phone or "")

    def test_uses_email_local_part_first(self):
        lead = self._lead(email="john.doe@example.com", name="John Doe", phone="+33600000001")
        result = _base_slug_for_lead(lead)
        self.assertEqual(result, "johndoe")

    def test_falls_back_to_name_when_no_email(self):
        lead = self._lead(name="Café Madeleine", phone="+33600000001")
        result = _base_slug_for_lead(lead)
        self.assertIn("caf", result)  # slugified

    def test_falls_back_to_phone_when_no_email_or_name(self):
        lead = self._lead(phone="+33600000001")
        result = _base_slug_for_lead(lead)
        self.assertTrue(len(result) > 0)

    def test_falls_back_to_tenant_id_when_all_empty(self):
        lead = self._lead(lead_id=42)
        result = _base_slug_for_lead(lead)
        self.assertEqual(result, "tenant-42")

    def test_slug_respects_max_length(self):
        lead = self._lead(email="a" * 100 + "@example.com")
        result = _base_slug_for_lead(lead)
        from sales.services import SLUG_MAX_LENGTH
        self.assertLessEqual(len(result), SLUG_MAX_LENGTH)


# ══════════════════════════════════════════════════════════════════════════════
# _build_next_slug
# ══════════════════════════════════════════════════════════════════════════════

class BuildNextSlugTests(SimpleTestCase):
    def test_index_1_returns_base_slug(self):
        self.assertEqual(_build_next_slug("mybistro", 1), "mybistro")

    def test_index_0_returns_base_slug(self):
        self.assertEqual(_build_next_slug("mybistro", 0), "mybistro")

    def test_index_2_appends_suffix(self):
        self.assertEqual(_build_next_slug("mybistro", 2), "mybistro-2")

    def test_index_10_appends_suffix(self):
        self.assertEqual(_build_next_slug("mybistro", 10), "mybistro-10")

    def test_long_base_slug_trimmed_to_fit_max_length(self):
        base = "a" * 60  # longer than typical SLUG_MAX_LENGTH
        result = _build_next_slug(base, 5)
        from sales.services import SLUG_MAX_LENGTH
        self.assertLessEqual(len(result), SLUG_MAX_LENGTH)
        self.assertTrue(result.endswith("-5"))


# ══════════════════════════════════════════════════════════════════════════════
# _availability
# ══════════════════════════════════════════════════════════════════════════════

class AvailabilityTests(SimpleTestCase):
    @patch("sales.services.Domain")
    @patch("sales.services.Tenant")
    def test_both_available(self, TenantMock, DomainMock):
        TenantMock.objects.filter.return_value.exists.return_value = False
        DomainMock.objects.filter.return_value.exists.return_value = False
        result = _availability("mybistro", "example.com")
        self.assertTrue(result["slug_available"])
        self.assertTrue(result["domain_available"])
        self.assertTrue(result["available"])
        self.assertEqual(result["slug"], "mybistro")
        self.assertEqual(result["domain"], "mybistro.example.com")

    @patch("sales.services.Domain")
    @patch("sales.services.Tenant")
    def test_slug_taken(self, TenantMock, DomainMock):
        TenantMock.objects.filter.return_value.exists.return_value = True
        DomainMock.objects.filter.return_value.exists.return_value = False
        result = _availability("mybistro", "example.com")
        self.assertFalse(result["slug_available"])
        self.assertFalse(result["available"])

    @patch("sales.services.Domain")
    @patch("sales.services.Tenant")
    def test_domain_taken(self, TenantMock, DomainMock):
        TenantMock.objects.filter.return_value.exists.return_value = False
        DomainMock.objects.filter.return_value.exists.return_value = True
        result = _availability("mybistro", "example.com")
        self.assertTrue(result["slug_available"])
        self.assertFalse(result["domain_available"])
        self.assertFalse(result["available"])

    @patch("sales.services.Domain")
    @patch("sales.services.Tenant")
    def test_domain_format_is_slug_dot_suffix(self, TenantMock, DomainMock):
        TenantMock.objects.filter.return_value.exists.return_value = False
        DomainMock.objects.filter.return_value.exists.return_value = False
        result = _availability("bistro-demo", "menu.example.com")
        self.assertEqual(result["domain"], "bistro-demo.menu.example.com")
