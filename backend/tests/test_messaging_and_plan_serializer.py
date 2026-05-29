"""
Unit tests covering untested branches in:

  sales.messaging
    - primary_domain_for_tenant: no primary domain → slug.localhost fallback
    - primary_domain_for_tenant: primary exists but domain is falsy → fallback
    - build_tenant_frontend_url: *.localhost domain → http://...:5173
    - build_tenant_frontend_url: domain == "localhost" → http://localhost:5173
    - build_admin_url: *.localhost domain → http://...:8000/admin/
    - build_admin_url: domain == "localhost" → http://localhost:8000/admin/

  tenancy.serializers.PlanSerializer
    - get_tier_code: delegates to external_plan_code
    - get_tier_name: delegates to plan_display_name with fallback

All tests are unit-level (SimpleTestCase — no real DB).
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from sales.messaging import (
    build_admin_url,
    build_tenant_frontend_url,
    primary_domain_for_tenant,
)
from tenancy.serializers import PlanSerializer


# ── helpers ───────────────────────────────────────────────────────────────────

def _tenant(domain=None, slug="demo"):
    """Build a fake tenant whose domains queryset returns *domain*."""
    if domain is not None:
        primary = SimpleNamespace(domain=domain)
    else:
        primary = None

    qs = SimpleNamespace(first=lambda: primary)
    domains = SimpleNamespace(filter=lambda **kwargs: qs)
    return SimpleNamespace(slug=slug, domains=domains)


# ══════════════════════════════════════════════════════════════════════════════
# primary_domain_for_tenant
# ══════════════════════════════════════════════════════════════════════════════

class PrimaryDomainForTenantTests(SimpleTestCase):

    def test_no_primary_domain_returns_slug_localhost(self):
        """When domains queryset returns None, falls back to slug.localhost."""
        tenant = _tenant(domain=None, slug="bistro")
        self.assertEqual(primary_domain_for_tenant(tenant), "bistro.localhost")

    def test_primary_domain_falsy_string_returns_slug_localhost(self):
        """When primary.domain is an empty string, falls back."""
        primary = SimpleNamespace(domain="")
        qs = SimpleNamespace(first=lambda: primary)
        tenant = SimpleNamespace(
            slug="bistro",
            domains=SimpleNamespace(filter=lambda **kwargs: qs),
        )
        self.assertEqual(primary_domain_for_tenant(tenant), "bistro.localhost")

    def test_real_domain_returned(self):
        tenant = _tenant(domain="demo.example.com", slug="demo")
        self.assertEqual(primary_domain_for_tenant(tenant), "demo.example.com")


# ══════════════════════════════════════════════════════════════════════════════
# build_tenant_frontend_url  — localhost branches
# ══════════════════════════════════════════════════════════════════════════════

class BuildTenantFrontendUrlLocalhostTests(SimpleTestCase):

    def test_dot_localhost_domain_uses_http_and_port_5173(self):
        tenant = _tenant(domain="demo.localhost", slug="demo")
        self.assertEqual(build_tenant_frontend_url(tenant), "http://demo.localhost:5173")

    def test_bare_localhost_uses_http_and_port_5173(self):
        tenant = _tenant(domain="localhost", slug="demo")
        self.assertEqual(build_tenant_frontend_url(tenant), "http://localhost:5173")

    def test_slug_localhost_fallback_uses_http_and_port_5173(self):
        """No primary domain → slug.localhost fallback → http with port 5173."""
        tenant = _tenant(domain=None, slug="myplace")
        self.assertEqual(build_tenant_frontend_url(tenant), "http://myplace.localhost:5173")


# ══════════════════════════════════════════════════════════════════════════════
# build_admin_url  — localhost branches
# ══════════════════════════════════════════════════════════════════════════════

class BuildAdminUrlLocalhostTests(SimpleTestCase):

    def test_dot_localhost_domain_uses_http_and_port_8000(self):
        tenant = _tenant(domain="demo.localhost", slug="demo")
        self.assertEqual(build_admin_url(tenant), "http://demo.localhost:8000/admin/")

    def test_bare_localhost_uses_http_and_port_8000(self):
        tenant = _tenant(domain="localhost", slug="demo")
        self.assertEqual(build_admin_url(tenant), "http://localhost:8000/admin/")

    def test_slug_localhost_fallback_uses_http_and_port_8000(self):
        tenant = _tenant(domain=None, slug="myplace")
        self.assertEqual(build_admin_url(tenant), "http://myplace.localhost:8000/admin/")

    def test_production_domain_uses_https(self):
        tenant = _tenant(domain="demo.example.com", slug="demo")
        self.assertEqual(build_admin_url(tenant), "https://demo.example.com/admin/")


# ══════════════════════════════════════════════════════════════════════════════
# PlanSerializer.get_tier_code / get_tier_name
# ══════════════════════════════════════════════════════════════════════════════

class PlanSerializerTierFieldsTests(SimpleTestCase):

    def _s(self):
        return PlanSerializer.__new__(PlanSerializer)

    def test_get_tier_code_maps_starter_to_basic(self):
        """starter is the internal code; external alias is 'basic'."""
        obj = SimpleNamespace(code="starter", name="Basic Plan")
        self.assertEqual(self._s().get_tier_code(obj), "basic")

    def test_get_tier_code_growth_unchanged(self):
        obj = SimpleNamespace(code="growth", name="Growth Plan")
        self.assertEqual(self._s().get_tier_code(obj), "growth")

    def test_get_tier_code_no_code_returns_empty(self):
        obj = SimpleNamespace(name="Unknown")  # no code attr
        # external_plan_code("") → ""
        self.assertEqual(self._s().get_tier_code(obj), "")

    def test_get_tier_name_uses_display_name(self):
        """plan_display_name for 'starter' is 'Basic'."""
        obj = SimpleNamespace(code="starter", name="Starter Plan")
        self.assertEqual(self._s().get_tier_name(obj), "Basic")

    def test_get_tier_name_unknown_code_falls_back_to_obj_name(self):
        """Unknown code → plan_display_name returns fallback → obj.name used."""
        obj = SimpleNamespace(code="unknown_code", name="Custom Plan")
        result = self._s().get_tier_name(obj)
        self.assertEqual(result, "Custom Plan")

    def test_get_tier_name_no_code_no_name_returns_plan_fallback(self):
        """plan_display_name ultimate fallback is the string 'Plan'."""
        obj = SimpleNamespace()  # no code, no name
        result = self._s().get_tier_name(obj)
        self.assertEqual(result, "Plan")
