"""
Tests for provisioning utility functions in sales/services.py:
  - mask_secret
  - _is_local_suffix
  - is_reserved_slug
  - _base_slug_for_lead
  - _build_next_slug
  - _availability
  - preview_lead_provision (slug resolution loop)

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from sales.services import (
    mask_secret,
    _is_local_suffix,
    is_reserved_slug,
    _base_slug_for_lead,
    _build_next_slug,
    _availability,
    preview_lead_provision,
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

    # M3: generic mailboxes must not auto-generate a platform-host / system-schema slug,
    # but one-click provisioning must still work (a suffix is appended).
    def test_reserved_email_local_part_gets_a_suffix(self):
        for local_part in ("admin", "menu", "www", "api", "app", "mail", "public", "static", "media"):
            with self.subTest(local_part=local_part):
                result = _base_slug_for_lead(self._lead(email=f"{local_part}@pizzeria.ma"))
                self.assertEqual(result, f"{local_part}-2")
                self.assertFalse(is_reserved_slug(result))

    def test_reserved_name_gets_a_suffix(self):
        self.assertEqual(_base_slug_for_lead(self._lead(name="Public")), "public-2")
        self.assertEqual(_base_slug_for_lead(self._lead(name="Admin")), "admin-2")

    def test_pg_prefix_is_neutralised(self):
        result = _base_slug_for_lead(self._lead(email="pg_toast@example.com"))
        self.assertEqual(result, "pg-toast")
        self.assertFalse(is_reserved_slug(result))


# ══════════════════════════════════════════════════════════════════════════════
# is_reserved_slug
# ══════════════════════════════════════════════════════════════════════════════

class IsReservedSlugTests(SimpleTestCase):
    def test_reserved_names(self):
        for slug in ("public", "www", "admin", "api", "app", "menu", "static", "media", "mail",
                     "information_schema", "pg_catalog", "pg_toast", "pg_anything", "ADMIN", " www "):
            with self.subTest(slug=slug):
                self.assertTrue(is_reserved_slug(slug))

    def test_ordinary_names(self):
        for slug in ("mybistro", "admin-2", "menus", "pg-foo", "daseknahri", "apiary"):
            with self.subTest(slug=slug):
                self.assertFalse(is_reserved_slug(slug))


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

@patch("sales.services.schema_exists", return_value=False)
class AvailabilityTests(SimpleTestCase):
    @patch("sales.services.Domain")
    @patch("sales.services.Tenant")
    def test_both_available(self, TenantMock, DomainMock, _schema_exists):
        TenantMock.objects.filter.return_value.exists.return_value = False
        DomainMock.objects.filter.return_value.exists.return_value = False
        result = _availability("mybistro", "example.com")
        self.assertTrue(result["slug_available"])
        self.assertTrue(result["domain_available"])
        self.assertTrue(result["schema_available"])
        self.assertFalse(result["reserved"])
        self.assertTrue(result["available"])
        self.assertEqual(result["slug"], "mybistro")
        self.assertEqual(result["domain"], "mybistro.example.com")

    @patch("sales.services.Domain")
    @patch("sales.services.Tenant")
    def test_slug_taken(self, TenantMock, DomainMock, _schema_exists):
        TenantMock.objects.filter.return_value.exists.return_value = True
        DomainMock.objects.filter.return_value.exists.return_value = False
        result = _availability("mybistro", "example.com")
        self.assertFalse(result["slug_available"])
        self.assertFalse(result["available"])

    @patch("sales.services.Domain")
    @patch("sales.services.Tenant")
    def test_domain_taken(self, TenantMock, DomainMock, _schema_exists):
        TenantMock.objects.filter.return_value.exists.return_value = False
        DomainMock.objects.filter.return_value.exists.return_value = True
        result = _availability("mybistro", "example.com")
        self.assertTrue(result["slug_available"])
        self.assertFalse(result["domain_available"])
        self.assertFalse(result["available"])

    @patch("sales.services.Domain")
    @patch("sales.services.Tenant")
    def test_domain_format_is_slug_dot_suffix(self, TenantMock, DomainMock, _schema_exists):
        TenantMock.objects.filter.return_value.exists.return_value = False
        DomainMock.objects.filter.return_value.exists.return_value = False
        result = _availability("bistro-demo", "menu.example.com")
        self.assertEqual(result["domain"], "bistro-demo.menu.example.com")

    # H3: a stray schema (orphan of a failed build) blocks the slug instead of being adopted.
    @patch("sales.services.Domain")
    @patch("sales.services.Tenant")
    def test_existing_postgres_schema_blocks_slug(self, TenantMock, DomainMock, schema_exists_mock):
        TenantMock.objects.filter.return_value.exists.return_value = False
        DomainMock.objects.filter.return_value.exists.return_value = False
        schema_exists_mock.return_value = True
        result = _availability("mybistro", "example.com")
        schema_exists_mock.assert_called_once_with("mybistro")
        self.assertFalse(result["schema_available"])
        self.assertFalse(result["available"])

    # M3: reserved slugs and platform hosts are never available.
    @patch("sales.services.Domain")
    @patch("sales.services.Tenant")
    def test_reserved_slug_is_unavailable(self, TenantMock, DomainMock, _schema_exists):
        TenantMock.objects.filter.return_value.exists.return_value = False
        DomainMock.objects.filter.return_value.exists.return_value = False
        for slug in ("admin", "menu", "www", "information_schema", "pg_catalog"):
            with self.subTest(slug=slug):
                result = _availability(slug, "example.com")
                self.assertTrue(result["reserved"])
                self.assertFalse(result["available"])

    @override_settings(
        PUBLIC_SCHEMA_HOSTS=["localhost", "127.0.0.1", "kepoli.example.com"],
        BRAND_DOMAIN="brand.example.com",
        PUBLIC_MENU_BASE_URL="https://go.example.com",
    )
    @patch("sales.services.Domain")
    @patch("sales.services.Tenant")
    def test_domain_equal_to_a_platform_host_is_unavailable(self, TenantMock, DomainMock, _schema_exists):
        TenantMock.objects.filter.return_value.exists.return_value = False
        DomainMock.objects.filter.return_value.exists.return_value = False
        for slug in ("kepoli", "brand", "go"):
            with self.subTest(slug=slug):
                result = _availability(slug, "example.com")
                self.assertTrue(result["reserved"])
                self.assertFalse(result["available"])
        # The same labels under a different suffix are ordinary tenant domains.
        self.assertTrue(_availability("kepoli", "menus.example.com")["available"])


# ══════════════════════════════════════════════════════════════════════════════
# preview_lead_provision — slug resolution loop
# ══════════════════════════════════════════════════════════════════════════════

def _noop_cm():
    cm = Mock()
    cm.__enter__ = Mock(return_value=None)
    cm.__exit__ = Mock(return_value=False)
    return cm


@patch("sales.services.schema_exists", return_value=False)
@patch("sales.services.schema_context", return_value=_noop_cm())
@patch("sales.services.Domain")
@patch("sales.services.Tenant")
class PreviewSlugResolutionTests(SimpleTestCase):
    def _lead(self, email="owner@example.com"):
        return SimpleNamespace(id=9, email=email, name="", phone="")

    def _free(self, TenantMock, DomainMock):
        TenantMock.objects.filter.return_value.exists.return_value = False
        DomainMock.objects.filter.return_value.exists.return_value = False

    def test_auto_slug_for_generic_mailbox_resolves_without_collision(self, TenantMock, DomainMock, *_):
        self._free(TenantMock, DomainMock)
        preview = preview_lead_provision(self._lead("menu@pizzeria.ma"), domain_suffix="example.com")
        self.assertEqual(preview["input_slug"], "menu-2")
        self.assertFalse(preview["collision"])
        self.assertEqual(preview["resolved_slug"], "menu-2")
        self.assertEqual(preview["resolved_domain"], "menu-2.example.com")

    def test_requested_reserved_slug_is_flagged_and_suffixed(self, TenantMock, DomainMock, *_):
        self._free(TenantMock, DomainMock)
        preview = preview_lead_provision(self._lead(), domain_suffix="example.com", requested_slug="admin")
        self.assertTrue(preview["input_reserved"])
        self.assertTrue(preview["collision"])
        self.assertEqual(preview["resolved_slug"], "admin-2")

    def test_requested_pg_prefixed_slug_terminates(self, TenantMock, DomainMock, *_):
        # Suffixing alone can never clear a `pg_` prefix — the loop must still terminate.
        self._free(TenantMock, DomainMock)
        preview = preview_lead_provision(self._lead(), domain_suffix="example.com", requested_slug="pg_foo")
        self.assertTrue(preview["collision"])
        self.assertEqual(preview["resolved_slug"], "pg-foo-2")
        self.assertFalse(is_reserved_slug(preview["resolved_slug"]))

    def test_resolution_is_bounded(self, TenantMock, DomainMock, *_):
        TenantMock.objects.filter.return_value.exists.return_value = True  # everything taken
        DomainMock.objects.filter.return_value.exists.return_value = False
        with patch("sales.services.SLUG_MAX_ATTEMPTS", 5):
            with self.assertRaisesMessage(ValueError, "Could not find an available tenant slug"):
                preview_lead_provision(self._lead(), domain_suffix="example.com")
