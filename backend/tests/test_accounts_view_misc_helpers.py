"""
Unit tests for remaining private helpers in accounts/views.py:
  - _serialize_address
  - build_frontend_base_url

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase, override_settings

from accounts.views import (
    _serialize_address,
    build_frontend_base_url,
)


# NOTE: the two-arg accounts.views._is_tenant_owner helper was deleted after the
# AUTHZ-1 call-site migration (owner-gating is now permission_classes=[IsTenantOwner]).
# Its owner-check semantics live in sales.permissions.user_owns_tenant_id, covered by
# tests/test_permissions.py::UserOwnsTenantIdTests.


# ══════════════════════════════════════════════════════════════════════════════
# _serialize_address
# ══════════════════════════════════════════════════════════════════════════════

class SerializeAddressTests(SimpleTestCase):
    def _addr(self, *, label="Home", location_url="", lat=None, lng=None):
        return SimpleNamespace(
            pk=42,
            label=label,
            address="123 Main Street",
            location_url=location_url,
            lat=lat,
            lng=lng,
            created_at=SimpleNamespace(isoformat=lambda: "2025-06-01T12:00:00"),
        )

    def test_required_keys_present(self):
        result = _serialize_address(self._addr())
        for key in ("id", "label", "address", "location_url", "lat", "lng", "created_at"):
            self.assertIn(key, result)

    def test_id_is_pk(self):
        result = _serialize_address(self._addr())
        self.assertEqual(result["id"], 42)

    def test_none_label_returns_empty_string(self):
        result = _serialize_address(self._addr(label=None))
        self.assertEqual(result["label"], "")

    def test_none_location_url_returns_empty_string(self):
        result = _serialize_address(self._addr(location_url=None))
        self.assertEqual(result["location_url"], "")

    def test_lat_lng_preserved(self):
        result = _serialize_address(self._addr(lat=33.5, lng=-7.6))
        self.assertEqual(result["lat"], 33.5)
        self.assertEqual(result["lng"], -7.6)

    def test_created_at_isoformat(self):
        result = _serialize_address(self._addr())
        self.assertEqual(result["created_at"], "2025-06-01T12:00:00")


# ══════════════════════════════════════════════════════════════════════════════
# build_frontend_base_url
# ══════════════════════════════════════════════════════════════════════════════

def _req(host="demo.example.com"):
    req = MagicMock()
    req.get_host.return_value = host
    return req


def _user_with_tenant(domain="demo.example.com"):
    primary = SimpleNamespace(domain=domain)
    domains_qs = MagicMock()
    domains_qs.filter.return_value.first.return_value = primary
    tenant = SimpleNamespace(domains=domains_qs)
    u = MagicMock()
    u.tenant = tenant
    return u


def _user_no_tenant():
    u = MagicMock()
    u.tenant = None
    return u


class BuildFrontendBaseUrlTests(SimpleTestCase):
    # OPS-5f: the no-tenant fallback no longer honours request.get_host() (it is
    # attacker-controlled → host-header poisoning of the password-reset link). It now
    # uses a server-authoritative canonical host (BRAND_DOMAIN / PUBLIC_MENU_BASE_URL /
    # TENANT_DOMAIN_SUFFIX, falling back to localhost in dev).

    @override_settings(BRAND_DOMAIN="app.kepoli.com", PUBLIC_MENU_BASE_URL="", TENANT_DOMAIN_SUFFIX="")
    def test_no_tenant_uses_brand_domain_not_request_host(self):
        # The request claims a spoofed host; the link must NOT use it.
        result = build_frontend_base_url(_req("evil.attacker.com"), _user_no_tenant())
        self.assertEqual(result, "https://app.kepoli.com")

    @override_settings(BRAND_DOMAIN="", PUBLIC_MENU_BASE_URL="https://menu.kepoli.com", TENANT_DOMAIN_SUFFIX="")
    def test_no_tenant_falls_back_to_public_menu_base_url(self):
        result = build_frontend_base_url(_req("evil.attacker.com"), _user_no_tenant())
        self.assertEqual(result, "https://menu.kepoli.com")

    @override_settings(BRAND_DOMAIN="", PUBLIC_MENU_BASE_URL="", TENANT_DOMAIN_SUFFIX="kepoli.app")
    def test_no_tenant_falls_back_to_tenant_domain_suffix(self):
        result = build_frontend_base_url(_req("evil.attacker.com"), _user_no_tenant())
        self.assertEqual(result, "https://kepoli.app")

    @override_settings(BRAND_DOMAIN="localhost", PUBLIC_MENU_BASE_URL="", TENANT_DOMAIN_SUFFIX="")
    def test_localhost_brand_uses_http_with_port_5173(self):
        result = build_frontend_base_url(_req("evil.attacker.com"), _user_no_tenant())
        self.assertEqual(result, "http://localhost:5173")

    def test_tenant_primary_domain_overrides_request_host(self):
        result = build_frontend_base_url(
            _req("api.example.com"),
            _user_with_tenant("demo.example.com"),
        )
        self.assertEqual(result, "https://demo.example.com")

    def test_tenant_localhost_domain_returns_http(self):
        result = build_frontend_base_url(
            _req("api.example.com"),
            _user_with_tenant("demo.localhost"),
        )
        self.assertEqual(result, "http://demo.localhost:5173")

    @override_settings(BRAND_DOMAIN="app.kepoli.com", PUBLIC_MENU_BASE_URL="", TENANT_DOMAIN_SUFFIX="")
    def test_no_primary_domain_uses_canonical_not_request_host(self):
        # Tenant exists but has no primary domain → still must NOT use the spoofable host.
        u = MagicMock()
        tenant = MagicMock()
        tenant.domains.filter.return_value.first.return_value = None
        u.tenant = tenant
        result = build_frontend_base_url(_req("evil.attacker.com"), u)
        self.assertEqual(result, "https://app.kepoli.com")
